"""
Gate 5.4 — Structured stop / termination semantics.

NO_EVIDENCE must never map to SECURE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class StopReason(str, Enum):
    VERIFIED = "verified"
    DISPROVED = "disproved"
    INCONCLUSIVE_EXHAUSTED = "inconclusive_exhausted"
    PRECONDITION_BLOCKED = "precondition_blocked"
    SCOPE_BLOCKED = "scope_blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DUPLICATE = "duplicate"
    NO_DISCRIMINATING_EXPERIMENT = "no_discriminating_experiment"
    EVIDENCE_SUFFICIENT = "evidence_sufficient"
    AUTHORIZATION_DENIED = "authorization_denied"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    CONTINUE = "continue"


# Explicit: these must NEVER be treated as "target is secure"
NON_SECURE_STOPS = {
    StopReason.INCONCLUSIVE_EXHAUSTED,
    StopReason.PRECONDITION_BLOCKED,
    StopReason.SCOPE_BLOCKED,
    StopReason.BUDGET_EXHAUSTED,
    StopReason.NO_DISCRIMINATING_EXPERIMENT,
    StopReason.AUTHORIZATION_DENIED,
    StopReason.CAPABILITY_UNAVAILABLE,
}


@dataclass
class TerminationRecord:
    stop_reason: str
    secure_claim_allowed: bool
    explanation: str
    evidence_ids: list[str] = field(default_factory=list)
    finding_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_stop(
    reason: StopReason | str,
    *,
    has_positive_evidence: bool = False,
    has_negative_evidence: bool = False,
    finding_id: str | None = None,
) -> TerminationRecord:
    sr = reason if isinstance(reason, StopReason) else StopReason(str(reason))
    # NEVER map no-evidence / blocked / exhausted to secure
    if sr in NON_SECURE_STOPS:
        return TerminationRecord(
            stop_reason=sr.value,
            secure_claim_allowed=False,
            explanation=f"{sr.value}: does not establish security of target",
            finding_id=None,
        )
    if sr == StopReason.DISPROVED:
        return TerminationRecord(
            stop_reason=sr.value,
            secure_claim_allowed=False,  # disproved claim ≠ prove secure
            explanation="claim disproved; target security not globally established",
            finding_id=None,
        )
    if sr in (StopReason.VERIFIED, StopReason.EVIDENCE_SUFFICIENT):
        if not has_positive_evidence:
            return TerminationRecord(
                stop_reason=StopReason.INCONCLUSIVE_EXHAUSTED.value,
                secure_claim_allowed=False,
                explanation="verified requested without positive evidence → inconclusive",
                finding_id=None,
            )
        return TerminationRecord(
            stop_reason=sr.value,
            secure_claim_allowed=False,  # verified finding ≠ whole target secure
            explanation="finding verified for specific claim only",
            finding_id=finding_id,
            evidence_ids=[],
        )
    return TerminationRecord(
        stop_reason=sr.value,
        secure_claim_allowed=False,
        explanation="continue or unstructured stop; no secure claim",
        finding_id=None,
    )
