"""
Finding lifecycle (§54).

candidate → investigating → evidence_ready → skeptic_review → referee
  → confirmed | rejected | needs_more_evidence

Never jump hypothesis → confirmed without evidence path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class FindingLifecycleState(str, Enum):
    CANDIDATE = "candidate"
    INVESTIGATING = "investigating"
    EVIDENCE_READY = "evidence_ready"
    SKEPTIC_REVIEW = "skeptic_review"
    REFEREE = "referee"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


ALLOWED: dict[FindingLifecycleState, set[FindingLifecycleState]] = {
    FindingLifecycleState.CANDIDATE: {
        FindingLifecycleState.INVESTIGATING,
        FindingLifecycleState.REJECTED,
    },
    FindingLifecycleState.INVESTIGATING: {
        FindingLifecycleState.EVIDENCE_READY,
        FindingLifecycleState.NEEDS_MORE_EVIDENCE,
        FindingLifecycleState.REJECTED,
    },
    FindingLifecycleState.EVIDENCE_READY: {
        FindingLifecycleState.SKEPTIC_REVIEW,
        FindingLifecycleState.NEEDS_MORE_EVIDENCE,
    },
    FindingLifecycleState.SKEPTIC_REVIEW: {
        FindingLifecycleState.REFEREE,
        FindingLifecycleState.NEEDS_MORE_EVIDENCE,
        FindingLifecycleState.REJECTED,
    },
    FindingLifecycleState.REFEREE: {
        FindingLifecycleState.CONFIRMED,
        FindingLifecycleState.REJECTED,
        FindingLifecycleState.NEEDS_MORE_EVIDENCE,
    },
    FindingLifecycleState.CONFIRMED: set(),
    FindingLifecycleState.REJECTED: set(),
    FindingLifecycleState.NEEDS_MORE_EVIDENCE: {
        FindingLifecycleState.INVESTIGATING,
        FindingLifecycleState.EVIDENCE_READY,
    },
}


@dataclass
class FindingLifecycle:
    finding_ref: str
    state: FindingLifecycleState = FindingLifecycleState.CANDIDATE
    history: list[str] = field(default_factory=list)

    def can_transition(self, new: FindingLifecycleState) -> bool:
        return new in ALLOWED.get(self.state, set())

    def transition(self, new: FindingLifecycleState, note: str = "") -> bool:
        if not self.can_transition(new):
            return False
        self.history.append(f"{self.state.value}→{new.value}:{note}")
        self.state = new
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_ref": self.finding_ref,
            "state": self.state.value,
            "history": list(self.history),
        }


def lifecycle_from_closed_loop(closed: Any) -> FindingLifecycle:
    """Map closed-loop outcome onto lifecycle (lab)."""
    ref = closed.finding_id or "candidate"
    lc = FindingLifecycle(finding_ref=ref)
    lc.transition(FindingLifecycleState.INVESTIGATING, "closed_loop_start")
    if closed.evidence_ids:
        lc.transition(FindingLifecycleState.EVIDENCE_READY, f"n={len(closed.evidence_ids)}")
        lc.transition(FindingLifecycleState.SKEPTIC_REVIEW, "skeptic")
        lc.transition(FindingLifecycleState.REFEREE, "referee")
        if closed.referee_accepted:
            lc.transition(FindingLifecycleState.CONFIRMED, closed.final_status or "confirmed")
        elif closed.final_status == "rejected":
            lc.transition(FindingLifecycleState.REJECTED, closed.stop_reason or "rejected")
        else:
            lc.transition(FindingLifecycleState.NEEDS_MORE_EVIDENCE, closed.final_status or "")
    else:
        if not closed.scope_allowed:
            lc.transition(FindingLifecycleState.REJECTED, "scope")
        else:
            lc.transition(FindingLifecycleState.NEEDS_MORE_EVIDENCE, "no_evidence")
    return lc
