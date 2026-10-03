"""
Gate 5.1 — Authorized Execution Boundary.

Research logic requests actions through this boundary only.
Knowledge / hypothesis / experiment existence NEVER grants execution.

Fail-closed: missing/ambiguous authorization → DENY.
No live HTTP in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from agent_core.scope.guard import Decision as ScopeDecision, RiskTier, ScopeGuard
from agent_core.tools.contracts import ToolContract, ToolAuthorizationResult
from agent_core.tools.capability import CapabilityTracker, FailureClass


@dataclass
class ActionRequest:
    """Research-facing request to perform a tool action."""

    tool_name: str
    purpose: str = ""
    host: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    experiment_id: str = ""
    hypothesis_id: str = ""
    engagement_id: str = ""
    risk_tier: str = "active_safe"
    approval_token: Optional[str] = None
    live_mode: bool = False
    contract_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionDecision:
    allowed: bool
    reason: str
    request_id: str = ""
    tool_name: str = ""
    contract_version: str = ""
    experiment_id: str = ""
    hypothesis_id: str = ""
    scope_decision: str = ""
    authorization_decision: str = ""  # ALLOW | DENY | REQUIRES_APPROVAL
    result_ref: str = ""  # never populated with live data here
    timestamp: str = ""
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionBoundary:
    """
    Single auditable choke point for tool/action execution requests.

    Does NOT perform network I/O. Authorization only.
    """

    def __init__(
        self,
        guard: ScopeGuard,
        contracts: dict[str, ToolContract] | None = None,
    ):
        self.guard = guard
        self.contracts: dict[str, ToolContract] = dict(contracts or {})
        self.audit_log: list[ExecutionDecision] = []
        self.capabilities = CapabilityTracker()

    def register(self, contract: ToolContract) -> None:
        if not contract or not contract.name:
            raise ValueError("invalid_contract")
        self.contracts[contract.name] = contract
        self.capabilities.mark_available(contract.name)

    def request_execution(self, request: ActionRequest) -> ExecutionDecision:
        rid = f"exec-{uuid4().hex[:12]}"
        ts = datetime.now(timezone.utc).isoformat()

        def deny(reason: str, **extra: Any) -> ExecutionDecision:
            d = ExecutionDecision(
                allowed=False,
                reason=reason,
                request_id=rid,
                tool_name=request.tool_name,
                contract_version=request.contract_version,
                experiment_id=request.experiment_id,
                hypothesis_id=request.hypothesis_id,
                scope_decision=extra.get("scope_decision", ""),
                authorization_decision=extra.get("authorization_decision", "DENY"),
                timestamp=ts,
                audit={
                    "request": request.to_dict(),
                    "decision": "DENY",
                    "reason": reason,
                    **{k: v for k, v in extra.items() if k not in ("scope_decision", "authorization_decision")},
                },
            )
            self.audit_log.append(d)
            fc = self.capabilities.classify_denial_reason(reason)
            self.capabilities.record_failure(
                fc,
                detail=reason,
                capability_name=request.tool_name,
                experiment_id=request.experiment_id,
                request_id=rid,
                provenance={"audit": d.audit},
            )
            self.capabilities.mark_used(
                request.tool_name or "unknown",
                outcome="denied",
                request_id=rid,
                experiment_id=request.experiment_id,
                failure_class=fc.value,
                failure_detail=reason,
            )
            return d

        # --- Fail-closed checks ---
        if not request.tool_name or not str(request.tool_name).strip():
            return deny("unknown_action", detail="empty tool_name")

        contract = self.contracts.get(request.tool_name)
        if contract is None:
            return deny("unknown_action", detail=f"no contract for {request.tool_name}")

        if not isinstance(contract, ToolContract) or not contract.name:
            return deny("invalid_contract")

        if contract.authorization_required is not True and contract.authorization_required is not False:
            return deny("ambiguous_authorization", detail="authorization_required flag invalid")

        if not request.host or not str(request.host).strip():
            return deny("missing_scope", detail="host required for scope adjudication")

        # Experiment/hypothesis alone never grant permission — checked by requiring
        # explicit ScopeGuard ALLOW (below). No short-circuit on experiment_id.

        if request.live_mode and not contract.live_http_allowed:
            return deny(
                "live_http_not_enabled_on_contract",
                authorization_decision="DENY",
            )

        if not contract.authorization_required:
            # Explicitly non-auth tools still need scope host in-scope for safety
            decision = self.guard.authorize(
                host=request.host,
                risk_tier=RiskTier.PASSIVE,
                action_description=request.purpose or contract.purpose,
            )
            if decision != ScopeDecision.ALLOW:
                return deny(
                    f"scope_{decision.value}",
                    scope_decision=decision.value,
                    authorization_decision=decision.value,
                )
        else:
            # Map risk
            rt = (request.risk_tier or "").lower()
            if rt in ("destructive",):
                tier = RiskTier.DESTRUCTIVE
            elif contract.side_effects in ("write", "state_change") or rt in ("active_risky",):
                tier = RiskTier.ACTIVE_RISKY
            else:
                tier = RiskTier.ACTIVE_SAFE

            decision = self.guard.authorize(
                host=request.host,
                risk_tier=tier,
                action_description=request.purpose or contract.purpose,
                approval_token=request.approval_token,
            )
            if decision == ScopeDecision.DENY:
                return deny(
                    "scope_deny",
                    scope_decision=decision.value,
                    authorization_decision=decision.value,
                )
            if decision == ScopeDecision.REQUIRES_APPROVAL:
                # Fail-closed: approval required but not granted
                return deny(
                    "ambiguous_authorization",
                    scope_decision=decision.value,
                    authorization_decision=decision.value,
                    detail="REQUIRES_APPROVAL without valid token",
                )
            if decision != ScopeDecision.ALLOW:
                return deny(
                    f"scope_{decision.value}",
                    scope_decision=str(decision),
                    authorization_decision=str(decision),
                )

        allowed = ExecutionDecision(
            allowed=True,
            reason="authorized",
            request_id=rid,
            tool_name=request.tool_name,
            contract_version=request.contract_version or "1.0",
            experiment_id=request.experiment_id,
            hypothesis_id=request.hypothesis_id,
            scope_decision=ScopeDecision.ALLOW.value,
            authorization_decision=ScopeDecision.ALLOW.value,
            result_ref="",  # no live result in Gate 5.1
            timestamp=ts,
            audit={
                "request": request.to_dict(),
                "decision": "ALLOW",
                "contract": contract.to_dict(),
                "scope_decision": ScopeDecision.ALLOW.value,
            },
        )
        self.audit_log.append(allowed)
        if request.tool_name not in self.capabilities._exposed:
            self.capabilities.mark_exposed(request.tool_name)
        self.capabilities.mark_used(
            request.tool_name,
            outcome="success",
            request_id=rid,
            experiment_id=request.experiment_id,
        )
        return allowed

    def attempt_bypass_direct_tool(self, tool_name: str, host: str) -> ExecutionDecision:
        """
        Adversarial helper: research logic that skips ActionRequest fields.
        Must still DENY when required fields missing.
        """
        return self.request_execution(
            ActionRequest(tool_name=tool_name, host=host, experiment_id="bypass-attempt")
        )
