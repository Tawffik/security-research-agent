"""
Gate 5.2 — Capability exposure tracking + failure taxonomy.

required → available → exposed → used → outcome

Does not grant execution permission. Tracks whether the agent can actually
use a capability, separately from whether ScopeGuard would allow it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class FailureClass(str, Enum):
    PLANNING_ERROR = "planning_error"
    PRECONDITION_MISSING = "precondition_missing"
    TOOL_FAILURE = "tool_failure"
    AUTH_STATE_MISSING = "auth_state_missing"
    CAPABILITY_NOT_EXPOSED = "capability_not_exposed"
    OBSERVATION_FAILURE = "observation_failure"
    INTERPRETATION_ERROR = "interpretation_error"
    DISCRIMINATION_FAILURE = "discrimination_failure"
    VERIFICATION_FAILURE = "verification_failure"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    SCOPE_BLOCK = "scope_block"
    ENVIRONMENT_FAILURE = "environment_failure"
    AUTHORIZATION_DENIED = "authorization_denied"
    UNKNOWN = "unknown"


class CapabilityPhase(str, Enum):
    REQUIRED = "required"
    AVAILABLE = "available"
    EXPOSED = "exposed"
    USED = "used"
    OUTCOME = "outcome"


@dataclass
class CapabilityRecord:
    capability_id: str
    name: str
    phase: str
    available: bool = False
    exposed: bool = False
    used: bool = False
    outcome: str = ""  # success | failure | denied | skipped
    failure_class: str = ""
    failure_detail: str = ""
    experiment_id: str = ""
    request_id: str = ""
    timestamp: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureRecord:
    failure_id: str
    failure_class: str
    detail: str
    capability_name: str = ""
    experiment_id: str = ""
    request_id: str = ""
    recoverable: bool = True
    suggested_action: str = ""  # fix | backtrack | defer | block | try_alternative
    timestamp: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapabilityTracker:
    """Tracks capability lifecycle for an engagement (offline-safe)."""

    def __init__(self, engagement_id: str = ""):
        self.engagement_id = engagement_id
        self.records: list[CapabilityRecord] = []
        self.failures: list[FailureRecord] = []
        self._required: set[str] = set()
        self._available: set[str] = set()
        self._exposed: set[str] = set()

    def require(self, name: str, *, experiment_id: str = "") -> CapabilityRecord:
        self._required.add(name)
        rec = CapabilityRecord(
            capability_id=f"cap-{uuid4().hex[:10]}",
            name=name,
            phase=CapabilityPhase.REQUIRED.value,
            experiment_id=experiment_id,
            timestamp=_ts(),
        )
        self.records.append(rec)
        return rec

    def mark_available(self, name: str) -> CapabilityRecord:
        self._available.add(name)
        rec = CapabilityRecord(
            capability_id=f"cap-{uuid4().hex[:10]}",
            name=name,
            phase=CapabilityPhase.AVAILABLE.value,
            available=True,
            timestamp=_ts(),
        )
        self.records.append(rec)
        return rec

    def mark_exposed(self, name: str) -> CapabilityRecord:
        if name not in self._available:
            # Cannot expose what is not available
            fail = self.record_failure(
                FailureClass.CAPABILITY_NOT_EXPOSED,
                detail=f"cannot expose {name}: not available",
                capability_name=name,
                suggested_action="fix",
            )
            rec = CapabilityRecord(
                capability_id=f"cap-{uuid4().hex[:10]}",
                name=name,
                phase=CapabilityPhase.EXPOSED.value,
                available=False,
                exposed=False,
                outcome="failure",
                failure_class=FailureClass.CAPABILITY_NOT_EXPOSED.value,
                failure_detail=fail.detail,
                timestamp=_ts(),
            )
            self.records.append(rec)
            return rec
        self._exposed.add(name)
        rec = CapabilityRecord(
            capability_id=f"cap-{uuid4().hex[:10]}",
            name=name,
            phase=CapabilityPhase.EXPOSED.value,
            available=True,
            exposed=True,
            timestamp=_ts(),
        )
        self.records.append(rec)
        return rec

    def mark_used(
        self,
        name: str,
        *,
        outcome: str,
        request_id: str = "",
        experiment_id: str = "",
        failure_class: str = "",
        failure_detail: str = "",
    ) -> CapabilityRecord:
        if name not in self._exposed:
            self.record_failure(
                FailureClass.CAPABILITY_NOT_EXPOSED,
                detail=f"used {name} without exposure",
                capability_name=name,
                request_id=request_id,
                experiment_id=experiment_id,
                suggested_action="backtrack",
            )
        rec = CapabilityRecord(
            capability_id=f"cap-{uuid4().hex[:10]}",
            name=name,
            phase=CapabilityPhase.USED.value
            if outcome in ("success", "denied", "skipped")
            else CapabilityPhase.OUTCOME.value,
            available=name in self._available,
            exposed=name in self._exposed,
            used=True,
            outcome=outcome,
            failure_class=failure_class,
            failure_detail=failure_detail,
            experiment_id=experiment_id,
            request_id=request_id,
            timestamp=_ts(),
        )
        self.records.append(rec)
        return rec

    def record_failure(
        self,
        failure_class: FailureClass | str,
        *,
        detail: str,
        capability_name: str = "",
        experiment_id: str = "",
        request_id: str = "",
        recoverable: bool = True,
        suggested_action: str = "try_alternative",
        provenance: dict[str, Any] | None = None,
    ) -> FailureRecord:
        fc = failure_class.value if isinstance(failure_class, FailureClass) else str(failure_class)
        rec = FailureRecord(
            failure_id=f"fail-{uuid4().hex[:10]}",
            failure_class=fc,
            detail=detail,
            capability_name=capability_name,
            experiment_id=experiment_id,
            request_id=request_id,
            recoverable=recoverable,
            suggested_action=suggested_action,
            timestamp=_ts(),
            provenance=dict(provenance or {}),
        )
        self.failures.append(rec)
        return rec

    def classify_denial_reason(self, reason: str) -> FailureClass:
        r = (reason or "").lower()
        if "scope" in r or "missing_scope" in r:
            return FailureClass.SCOPE_BLOCK
        if "auth" in r or "approval" in r or "ambiguous" in r:
            return FailureClass.AUTHORIZATION_DENIED
        if "unknown_action" in r or "invalid_contract" in r:
            return FailureClass.CAPABILITY_NOT_EXPOSED
        if "live_http" in r:
            return FailureClass.ENVIRONMENT_FAILURE
        if "budget" in r:
            return FailureClass.BUDGET_EXHAUSTION
        return FailureClass.AUTHORIZATION_DENIED

    def summary(self) -> dict[str, Any]:
        return {
            "engagement_id": self.engagement_id,
            "required": sorted(self._required),
            "available": sorted(self._available),
            "exposed": sorted(self._exposed),
            "n_records": len(self.records),
            "n_failures": len(self.failures),
            "failure_classes": sorted({f.failure_class for f in self.failures}),
        }


@dataclass
class CapabilityAuthorityRecord:
    """
    Declared vs observed capability differential.
    LLM decision / skill metadata ≠ authorization.
    """

    capability_name: str
    declared_available: bool = False
    observed_available: bool = False
    declared_exposed: bool = False
    observed_exposed: bool = False
    used: bool = False
    outcome: str = ""
    authorization_required: bool = True
    scope_checked: bool = False
    scope_allowed: bool = False
    differential: str = ""  # match | declared_only | observed_only | mismatch
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capability_differential(
    *,
    name: str,
    declared_available: bool,
    observed_available: bool,
    declared_exposed: bool = False,
    observed_exposed: bool = False,
    used: bool = False,
    outcome: str = "",
    scope_checked: bool = False,
    scope_allowed: bool = False,
) -> CapabilityAuthorityRecord:
    if declared_available == observed_available and declared_exposed == observed_exposed:
        diff = "match"
    elif declared_available and not observed_available:
        diff = "declared_only"
    elif observed_available and not declared_available:
        diff = "observed_only"
    else:
        diff = "mismatch"
    notes: list[str] = []
    if not scope_checked:
        notes.append("scope_not_checked_cannot_execute")
    if scope_checked and not scope_allowed:
        notes.append("scope_denied")
    notes.append("skill_metadata_neq_execution_permission")
    notes.append("llm_decision_neq_authorization")
    return CapabilityAuthorityRecord(
        capability_name=name,
        declared_available=declared_available,
        observed_available=observed_available,
        declared_exposed=declared_exposed,
        observed_exposed=observed_exposed,
        used=used,
        outcome=outcome,
        scope_checked=scope_checked,
        scope_allowed=scope_allowed,
        differential=diff,
        notes=notes,
    )
