"""
Action Regret (§60).

Compare expected vs actual research value of an action:
  information gain, belief change, evidence created, redundancy, cost, risk.

Used to prefer discriminating experiments and stop low-value repeats.
Lab-oriented scores from ClosedLoopResult + AdaptiveStepResult.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ActionRegretRecord:
    action_id: str
    engagement_id: str
    action_type: str
    expected_information_gain: float
    actual_information_gain: float
    belief_change: float
    evidence_created: int
    redundant: bool
    cost: float
    risk: float
    regret: float  # max(0, expected - actual) + redundancy penalty
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActionRegretTracker:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0
        self._records: list[ActionRegretRecord] = []

    def record_closed_loop(
        self,
        closed: Any,
        *,
        expected_information_gain: float = 0.75,
        cost: float = 0.3,
        risk: float = 0.25,
    ) -> ActionRegretRecord:
        """
        Score primary lab experiment outcome.
        High actual gain: confirmed with evidence OR clean reject with evidence.
        Low gain: incomplete, no evidence, or scope-only without learning.
        """
        self._n += 1
        evidence_n = len(getattr(closed, "evidence_ids", None) or [])
        accepted = bool(getattr(closed, "referee_accepted", False))
        status = getattr(closed, "final_status", None) or ""
        scope_ok = bool(getattr(closed, "scope_allowed", True))

        notes: list[str] = []
        if not scope_ok:
            actual = 0.1
            belief = 0.0
            notes.append("scope blocked — little research information")
        elif accepted and evidence_n:
            actual = min(1.0, 0.55 + 0.15 * min(evidence_n, 3))
            belief = 0.7
            notes.append("confirmed with evidence — high actual gain")
        elif status == "rejected" and evidence_n:
            actual = min(0.85, 0.5 + 0.1 * min(evidence_n, 3))
            belief = 0.6
            notes.append("rejected with negative evidence — useful (avoids FP)")
        elif evidence_n:
            actual = 0.35
            belief = 0.25
            notes.append("evidence without decisive referee outcome")
        else:
            actual = 0.05
            belief = 0.0
            notes.append("no evidence — low actual gain")

        redundant = False
        regret = max(0.0, expected_information_gain - actual)
        if redundant:
            regret += 0.2

        rec = ActionRegretRecord(
            action_id=f"AR-{self._n:03d}",
            engagement_id=self.engagement_id,
            action_type="closed_loop_experiment",
            expected_information_gain=expected_information_gain,
            actual_information_gain=round(actual, 4),
            belief_change=belief,
            evidence_created=evidence_n,
            redundant=redundant,
            cost=cost,
            risk=risk,
            regret=round(regret, 4),
            notes=notes,
        )
        self._records.append(rec)
        return rec

    def record_adaptive(
        self,
        adaptive: Any,
        *,
        expected_information_gain: float = 0.4,
        cost: float = 0.2,
        risk: float = 0.2,
    ) -> ActionRegretRecord:
        """Score adaptive decision: STOP with good reason can be low regret."""
        self._n += 1
        stop = bool(getattr(adaptive, "stop", True))
        reason = getattr(adaptive, "stop_reason", "") or ""
        notes: list[str] = []

        if stop and reason in (
            "hypothesis_disproven",
            "sufficient_evidence",
            "scope_blocked",
        ):
            actual = 0.5  # intelligent stop = valuable
            notes.append(f"intelligent stop ({reason}) — avoids wasted actions")
            regret = max(0.0, expected_information_gain - actual)
        elif stop and reason in ("information_gain_too_low", "jev_stop"):
            actual = 0.45
            notes.append("stop due to low gain policy")
            regret = max(0.0, expected_information_gain - actual)
        elif not stop and getattr(adaptive, "next_experiment", None):
            actual = 0.35  # planned continue — gain realized only after execute
            notes.append("continue planned; actual gain deferred to next execution")
            regret = max(0.0, expected_information_gain - actual)
        else:
            actual = 0.2
            notes.append("ambiguous adaptive outcome")
            regret = max(0.0, expected_information_gain - actual)

        rec = ActionRegretRecord(
            action_id=f"AR-{self._n:03d}",
            engagement_id=self.engagement_id,
            action_type="adaptive_decision",
            expected_information_gain=expected_information_gain,
            actual_information_gain=round(actual, 4),
            belief_change=0.2 if stop else 0.1,
            evidence_created=0,
            redundant=False,
            cost=cost,
            risk=risk,
            regret=round(regret, 4),
            notes=notes,
        )
        self._records.append(rec)
        return rec

    def list_all(self) -> list[ActionRegretRecord]:
        return list(self._records)

    def mean_regret(self) -> float:
        if not self._records:
            return 0.0
        return round(sum(r.regret for r in self._records) / len(self._records), 4)
