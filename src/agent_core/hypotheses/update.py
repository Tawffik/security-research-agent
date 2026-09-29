"""
Hypothesis portfolio update from evidence polarity (Gate 3).

Negative evidence weakens hypotheses; positive supports — never auto-finding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent_core.schemas.research import Hypothesis, HypothesisStatus


@dataclass
class HypothesisUpdateRecord:
    hypothesis_id: str
    previous_status: str
    new_status: str
    reason: str
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_evidence_to_hypotheses(
    hypotheses: list[Hypothesis],
    *,
    polarity: str,
    evidence_ids: list[str] | None = None,
    competing_notes: list[str] | None = None,
) -> list[HypothesisUpdateRecord]:
    """
    polarity: positive | negative | neutral | insufficient
    """
    records: list[HypothesisUpdateRecord] = []
    pol = (polarity or "neutral").lower()
    evid = list(evidence_ids or [])

    for h in hypotheses:
        prev = h.status.value if hasattr(h.status, "value") else str(h.status)
        new_status = h.status
        reason = "no_change"

        if pol in ("negative", "rejected", "secure"):
            # Weaken primary claims; null hypothesis may strengthen
            stmt = (h.statement or "").lower()
            if "null" in stmt or "not a vulnerability" in stmt or "intended" in stmt:
                new_status = HypothesisStatus.SUPPORTED
                reason = "negative_evidence_supports_null"
            elif h.status == HypothesisStatus.OPEN:
                # Retain OPEN but record negative pressure (no silent secure)
                new_status = HypothesisStatus.OPEN
                reason = "negative_evidence_noted_open_retained"
        elif pol in ("positive", "confirmed"):
            stmt = (h.statement or "").lower()
            if "null" in stmt or "not a vulnerability" in stmt:
                new_status = HypothesisStatus.REJECTED
                reason = "positive_evidence_rejects_null"
            elif h.status == HypothesisStatus.OPEN:
                new_status = HypothesisStatus.SUPPORTED
                reason = "positive_evidence_supports_claim"

        if competing_notes and pol in ("negative", "neutral"):
            reason = reason + "|competitors=" + ",".join(competing_notes[:2])

        if new_status != h.status:
            h.status = new_status
        records.append(
            HypothesisUpdateRecord(
                hypothesis_id=h.hypothesis_id,
                previous_status=prev,
                new_status=h.status.value if hasattr(h.status, "value") else str(h.status),
                reason=reason,
                evidence_ids=evid,
            )
        )
    return records
