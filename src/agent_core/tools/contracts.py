"""
Tool execution contracts (M12) — metadata + ScopeGuard gate, not live HTTP by default.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent_core.scope.guard import Decision as ScopeDecision, RiskTier, ScopeGuard


@dataclass
class ToolContract:
    name: str
    purpose: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    cost: float = 0.2
    risk: float = 0.3
    side_effects: str = "none"  # none | read | write | state_change
    scope: str = "in_scope_hosts_only"
    timeout_sec: float = 10.0
    evidence_value: float = 0.5
    required_skill: str = ""
    authorization_required: bool = True
    live_http_allowed: bool = False  # default fail-closed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


AUTHENTICATED_HTTP_READ = ToolContract(
    name="authenticated_http_request",
    purpose="Authorized read of an in-scope URL under an explicit identity",
    inputs=["method", "url", "identity", "headers"],
    outputs=["status", "body_excerpt", "headers"],
    cost=0.25,
    risk=0.35,
    side_effects="read",
    evidence_value=0.7,
    required_skill="authz-idor-analysis",
    authorization_required=True,
    live_http_allowed=False,
)


@dataclass
class ToolAuthorizationResult:
    allowed: bool
    reason: str
    scope_decision: str = ""
    contract_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def authorize_tool(
    contract: ToolContract,
    *,
    guard: ScopeGuard,
    host: str,
    action_description: str,
    live_mode: bool = False,
) -> ToolAuthorizationResult:
    """ScopeGuard + contract.live_http_allowed — never bypass risk policy."""
    if live_mode and not contract.live_http_allowed:
        return ToolAuthorizationResult(
            allowed=False,
            reason="live_http_not_enabled_on_contract",
            contract_name=contract.name,
        )
    if not host or not str(host).strip():
        return ToolAuthorizationResult(
            allowed=False,
            reason="missing_scope",
            contract_name=contract.name,
        )
    if contract.authorization_required:
        decision = guard.authorize(
            host=host,
            risk_tier=RiskTier.ACTIVE_SAFE if contract.side_effects == "read" else RiskTier.ACTIVE_RISKY,
            action_description=action_description,
        )
        # Gate 5.1: only explicit ALLOW — REQUIRES_APPROVAL is not permission
        if decision != ScopeDecision.ALLOW:
            return ToolAuthorizationResult(
                allowed=False,
                reason=f"scope_{decision.value}",
                scope_decision=decision.value,
                contract_name=contract.name,
            )
        return ToolAuthorizationResult(
            allowed=True,
            reason="scope_ok_contract_ok",
            scope_decision=decision.value,
            contract_name=contract.name,
        )
    return ToolAuthorizationResult(
        allowed=False,
        reason="authorization_required",
        contract_name=contract.name,
    )
