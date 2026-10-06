"""Evidence sufficiency ladder: candidate → likely → confirmed → rejected.

Model confidence never promotes a finding. Promotion requires evidence
structure, polarity, and independent verification signals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

from agent_core.evidence.store import Evidence, EvidencePolarity, FindingStatus


class SufficiencyLevel(str, Enum):
    CANDIDATE = "candidate"
    LIKELY = "likely"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INSUFFICIENT = "insufficient"


@dataclass
class SufficiencyReport:
    level: str
    can_confirm: bool
    reasons: list[str] = field(default_factory=list)
    positive_count: int = 0
    negative_count: int = 0
    ambiguous_count: int = 0
    verification_accepted: bool = False
    disproof_attempted: bool = False
    reproducibility_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_evidence_sufficiency(
    evidence: Sequence[Evidence],
    *,
    disproof_attempted: bool = False,
    verification_accepted: bool = False,
    min_positive_for_likely: int = 1,
    min_positive_for_confirm: int = 2,
    require_disproof_for_confirm: bool = True,
    reproducibility_signal: bool = False,
) -> SufficiencyReport:
    pos = neg = amb = 0
    for ev in evidence:
        pol = getattr(ev, "polarity", None)
        val = pol.value if hasattr(pol, "value") else str(pol or "").lower()
        if val == "positive":
            pos += 1
        elif val == "negative":
            neg += 1
        else:
            amb += 1

    reasons: list[str] = []
    # Rejected: dominant negative evidence
    if neg > 0 and neg >= pos and pos == 0:
        reasons.append("negative_evidence_without_support")
        return SufficiencyReport(
            level=SufficiencyLevel.REJECTED.value,
            can_confirm=False,
            reasons=reasons,
            positive_count=pos,
            negative_count=neg,
            ambiguous_count=amb,
            verification_accepted=verification_accepted,
            disproof_attempted=disproof_attempted,
            reproducibility_signal=reproducibility_signal,
        )

    if pos == 0:
        reasons.append("no_positive_evidence")
        return SufficiencyReport(
            level=SufficiencyLevel.INSUFFICIENT.value,
            can_confirm=False,
            reasons=reasons,
            positive_count=pos,
            negative_count=neg,
            ambiguous_count=amb,
            verification_accepted=verification_accepted,
            disproof_attempted=disproof_attempted,
            reproducibility_signal=reproducibility_signal,
        )

    # Interesting but not enough
    if pos < min_positive_for_likely:
        reasons.append("below_likely_threshold")
        return SufficiencyReport(
            level=SufficiencyLevel.CANDIDATE.value,
            can_confirm=False,
            reasons=reasons,
            positive_count=pos,
            negative_count=neg,
            ambiguous_count=amb,
            verification_accepted=verification_accepted,
            disproof_attempted=disproof_attempted,
            reproducibility_signal=reproducibility_signal,
        )

    # Confirmed path: strict
    can_confirm = True
    if pos < min_positive_for_confirm:
        can_confirm = False
        reasons.append("need_more_positive_or_reproduction")
    if require_disproof_for_confirm and not disproof_attempted:
        can_confirm = False
        reasons.append("disproof_not_attempted")
    if not verification_accepted:
        can_confirm = False
        reasons.append("independent_verification_not_accepted")
    if neg > 0 and neg >= pos:
        can_confirm = False
        reasons.append("counter_evidence_unresolved")

    if can_confirm:
        reasons.append("evidence_and_verification_sufficient")
        return SufficiencyReport(
            level=SufficiencyLevel.CONFIRMED.value,
            can_confirm=True,
            reasons=reasons,
            positive_count=pos,
            negative_count=neg,
            ambiguous_count=amb,
            verification_accepted=verification_accepted,
            disproof_attempted=disproof_attempted,
            reproducibility_signal=reproducibility_signal,
        )

    if pos >= min_positive_for_likely and verification_accepted and neg == 0:
        reasons.append("likely_pending_stricter_confirm_gates")
        return SufficiencyReport(
            level=SufficiencyLevel.LIKELY.value,
            can_confirm=False,
            reasons=reasons,
            positive_count=pos,
            negative_count=neg,
            ambiguous_count=amb,
            verification_accepted=verification_accepted,
            disproof_attempted=disproof_attempted,
            reproducibility_signal=reproducibility_signal,
        )

    reasons.append("candidate_insufficient_for_confirm")
    return SufficiencyReport(
        level=SufficiencyLevel.CANDIDATE.value,
        can_confirm=False,
        reasons=reasons,
        positive_count=pos,
        negative_count=neg,
        ambiguous_count=amb,
        verification_accepted=verification_accepted,
        disproof_attempted=disproof_attempted,
        reproducibility_signal=reproducibility_signal,
    )


def finding_status_for_sufficiency(level: str) -> FindingStatus:
    mapping = {
        SufficiencyLevel.CONFIRMED.value: FindingStatus.CONFIRMED,
        SufficiencyLevel.LIKELY.value: FindingStatus.LIKELY,
        SufficiencyLevel.REJECTED.value: FindingStatus.REJECTED,
        SufficiencyLevel.CANDIDATE.value: FindingStatus.CANDIDATE,
        SufficiencyLevel.INSUFFICIENT.value: FindingStatus.CANDIDATE,
    }
    return mapping.get(level, FindingStatus.CANDIDATE)
