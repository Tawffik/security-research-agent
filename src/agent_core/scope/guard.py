"""
ScopeGuard — the hard authorization boundary described in MASTER SPEC §1.

Every single outbound action the agent ever takes (HTTP request, tool call,
browser navigation, subprocess exec against a host) MUST pass through
ScopeGuard.authorize() first. There is no code path in this framework that
is allowed to skip it.

Design principles:
  - Fail closed: anything not explicitly in scope is denied.
  - No implicit wildcards: "*.example.com" must be written explicitly,
    it is never inferred from "example.com".
  - Explicit deny beats explicit allow: exclusions always win.
  - Destructive / high-risk action classes require a human approval token,
    which is itself logged and expires.
  - Every decision (allow AND deny) is logged. The log is the audit trail.
"""

from __future__ import annotations

import fnmatch
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RiskTier(str, Enum):
    PASSIVE = "passive"          # read-only recon, no state change on target
    ACTIVE_SAFE = "active_safe"  # e.g. sending a benign probe request
    ACTIVE_RISKY = "active_risky"  # e.g. auth bypass attempt, injection probe
    DESTRUCTIVE = "destructive"  # anything that could modify/delete data,
                                  # DoS-adjacent, or touch production write paths


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class ScopeRule:
    pattern: str          # fnmatch-style, e.g. "*.example.com", "api.example.com"
    allow: bool           # True = allow, False = explicit exclude
    max_risk_tier: RiskTier = RiskTier.ACTIVE_SAFE
    note: str = ""


@dataclass
class ApprovalToken:
    token_id: str
    granted_by: str
    reason: str
    issued_at: float
    expires_at: float
    action_pattern: str  # what this approval actually covers

    def is_valid(self, action_description: str) -> bool:
        if time.time() > self.expires_at:
            return False
        return fnmatch.fnmatch(action_description, self.action_pattern)


@dataclass
class ScopeDecisionLog:
    entries: list = field(default_factory=list)

    def record(self, **kwargs) -> None:
        entry = {"ts": time.time(), "id": str(uuid.uuid4()), **kwargs}
        self.entries.append(entry)

    def dump(self, path: Path) -> None:
        path.write_text(json.dumps(self.entries, indent=2))


class ScopeGuard:
    """
    Loads an authorized program scope and adjudicates every action against it.

    Usage:
        guard = ScopeGuard.from_scope_file("programs/acme-2026.yaml")
        decision = guard.authorize(host="api.acme.com", risk_tier=RiskTier.ACTIVE_SAFE)
        if decision is not Decision.ALLOW:
            raise ScopeViolation(...)
    """

    def __init__(
        self,
        rules: list[ScopeRule],
        program_name: str,
        rate_limit_per_host_per_min: int = 60,
        concurrency_limit_per_host: int = 4,
    ):
        self.rules = rules
        self.program_name = program_name
        self.rate_limit_per_host_per_min = rate_limit_per_host_per_min
        self.concurrency_limit_per_host = concurrency_limit_per_host
        self.log = ScopeDecisionLog()
        self._approvals: dict[str, ApprovalToken] = {}
        self._recent_hits: dict[str, list[float]] = {}

    @classmethod
    def from_scope_file(cls, path: str | Path) -> "ScopeGuard":
        import yaml

        data = yaml.safe_load(Path(path).read_text())
        rules = []
        for entry in data.get("in_scope", []):
            rules.append(
                ScopeRule(
                    pattern=entry["pattern"],
                    allow=True,
                    max_risk_tier=RiskTier(entry.get("max_risk_tier", "active_safe")),
                    note=entry.get("note", ""),
                )
            )
        for entry in data.get("excluded", []):
            rules.append(ScopeRule(pattern=entry["pattern"], allow=False, note=entry.get("note", "")))

        return cls(
            rules=rules,
            program_name=data.get("program_name", "unnamed-program"),
            rate_limit_per_host_per_min=data.get("rate_limit_per_host_per_min", 60),
            concurrency_limit_per_host=data.get("concurrency_limit_per_host", 4),
        )

    def grant_approval(self, granted_by: str, reason: str, action_pattern: str, ttl_seconds: int = 3600) -> ApprovalToken:
        token = ApprovalToken(
            token_id=str(uuid.uuid4()),
            granted_by=granted_by,
            reason=reason,
            issued_at=time.time(),
            expires_at=time.time() + ttl_seconds,
            action_pattern=action_pattern,
        )
        self._approvals[token.token_id] = token
        self.log.record(event="approval_granted", token_id=token.token_id, reason=reason, pattern=action_pattern)
        return token

    def _matching_rules(self, host: str) -> list[ScopeRule]:
        return [r for r in self.rules if fnmatch.fnmatch(host, r.pattern)]

    def _rate_check(self, host: str) -> bool:
        now = time.time()
        window = self._recent_hits.setdefault(host, [])
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= self.rate_limit_per_host_per_min:
            return False
        window.append(now)
        return True

    def authorize(
        self,
        host: str,
        risk_tier: RiskTier = RiskTier.PASSIVE,
        action_description: str = "",
        approval_token: Optional[str] = None,
    ) -> Decision:
        """
        The single choke point. Returns ALLOW, DENY, or REQUIRES_APPROVAL.
        Never raises — callers must check the return value explicitly, which
        forces every call site to handle the deny case instead of assuming success.
        """
        matches = self._matching_rules(host)

        # Explicit exclusion always wins, regardless of any allow rule.
        if any(not r.allow for r in matches):
            self.log.record(event="deny", host=host, reason="explicit_exclusion", risk_tier=risk_tier.value)
            return Decision.DENY

        allow_rules = [r for r in matches if r.allow]
        if not allow_rules:
            self.log.record(event="deny", host=host, reason="not_in_scope", risk_tier=risk_tier.value)
            return Decision.DENY

        if not self._rate_check(host):
            self.log.record(event="deny", host=host, reason="rate_limit_exceeded", risk_tier=risk_tier.value)
            return Decision.DENY

        max_allowed = max(allow_rules, key=lambda r: list(RiskTier).index(r.max_risk_tier))
        allowed_tier_index = list(RiskTier).index(max_allowed.max_risk_tier)
        requested_tier_index = list(RiskTier).index(risk_tier)

        if requested_tier_index <= allowed_tier_index:
            self.log.record(event="allow", host=host, risk_tier=risk_tier.value)
            return Decision.ALLOW

        # Requested risk exceeds what the program scope pre-authorizes.
        if approval_token and approval_token in self._approvals:
            token = self._approvals[approval_token]
            if token.is_valid(action_description):
                self.log.record(
                    event="allow_via_approval", host=host, risk_tier=risk_tier.value, token_id=approval_token
                )
                return Decision.ALLOW

        self.log.record(
            event="requires_approval",
            host=host,
            risk_tier=risk_tier.value,
            note="risk tier exceeds pre-authorized scope; human approval required",
        )
        return Decision.REQUIRES_APPROVAL


class ScopeViolation(RuntimeError):
    """Raised by higher-level tool wrappers when a caller ignores a DENY."""
