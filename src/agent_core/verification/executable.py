"""
Gate 5.3 — Executable verification boundary.

Claim → Evidence Contract → Requirements → Evidence Set → Verifier → Result

Researcher/Skeptic may interpret; they cannot alone establish CONFIRMED.
Insufficient / missing evidence → INCONCLUSIVE, never SECURE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence
from uuid import uuid4

from agent_core.evidence.store import Evidence, EvidencePolarity, EvidenceStore, FindingStatus


class VerificationOutcome(str, Enum):
    CONFIRMED = "confirmed"
    DISPROVED = "disproved"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"


@dataclass
class EvidenceRequirement:
    requirement_id: str
    description: str
    polarity_needed: str = "positive"  # positive | negative | any
    satisfied: bool = False
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceContract:
    contract_id: str
    claim: str
    hypothesis_id: str = ""
    requirements: list[EvidenceRequirement] = field(default_factory=list)
    min_positive: int = 1
    allow_confirm_without_positive: bool = False  # always False in practice

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "claim": self.claim,
            "hypothesis_id": self.hypothesis_id,
            "requirements": [r.to_dict() for r in self.requirements],
            "min_positive": self.min_positive,
            "allow_confirm_without_positive": self.allow_confirm_without_positive,
        }


@dataclass
class VerificationResult:
    result_id: str
    outcome: str
    claim: str
    hypothesis_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    requirements_met: list[str] = field(default_factory=list)
    requirements_unmet: list[str] = field(default_factory=list)
    finding_status: str = FindingStatus.CANDIDATE.value
    reason: str = ""
    cannot_become_confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutableVerifier:
    """Deterministic verifier over EvidenceStore — no LLM authority."""

    def __init__(self, store: EvidenceStore):
        self.store = store
        self.history: list[VerificationResult] = []

    def build_contract(
        self,
        claim: str,
        *,
        hypothesis_id: str = "",
        requirement_descriptions: Sequence[str] | None = None,
        min_positive: int = 1,
    ) -> EvidenceContract:
        reqs = []
        for i, desc in enumerate(requirement_descriptions or ["supporting observation"]):
            reqs.append(
                EvidenceRequirement(
                    requirement_id=f"req-{i+1}",
                    description=desc,
                    polarity_needed="positive",
                )
            )
        return EvidenceContract(
            contract_id=f"ec-{uuid4().hex[:10]}",
            claim=claim,
            hypothesis_id=hypothesis_id,
            requirements=reqs,
            min_positive=min_positive,
            allow_confirm_without_positive=False,
        )

    def verify(
        self,
        contract: EvidenceContract,
        *,
        related_hypothesis: str | None = None,
    ) -> VerificationResult:
        hyp = related_hypothesis or contract.hypothesis_id
        all_ev: list[Evidence] = []
        if hasattr(self.store, "conn"):
            rows = self.store.conn.execute(
                "SELECT * FROM evidence ORDER BY timestamp ASC"
            ).fetchall()
            all_ev = [self.store._row_to_evidence(r) for r in rows]
        positive: list[Evidence] = []
        negative: list[Evidence] = []
        neutral: list[Evidence] = []
        for e in all_ev:
            pol = e.polarity
            rel = e.related_hypothesis or ""
            if hyp and rel and rel != hyp:
                # still count unscoped evidence lightly
                pass
            if pol == EvidencePolarity.POSITIVE:
                if not hyp or not rel or rel == hyp:
                    positive.append(e)
            elif pol == EvidencePolarity.NEGATIVE:
                if not hyp or not rel or rel == hyp:
                    negative.append(e)
            else:
                if not hyp or not rel or rel == hyp:
                    neutral.append(e)

        met: list[str] = []
        unmet: list[str] = []
        for req in contract.requirements:
            if req.polarity_needed == "positive" and positive:
                req.satisfied = True
                req.evidence_ids = [e.evidence_id for e in positive[:3]]
                met.append(req.requirement_id)
            elif req.polarity_needed == "negative" and negative:
                req.satisfied = True
                req.evidence_ids = [e.evidence_id for e in negative[:3]]
                met.append(req.requirement_id)
            else:
                unmet.append(req.requirement_id)

        evidence_ids = [e.evidence_id for e in positive + negative + neutral]

        # Core invariant: cannot confirm without positive evidence
        if len(positive) < contract.min_positive or contract.allow_confirm_without_positive:
            if len(positive) < contract.min_positive:
                outcome = VerificationOutcome.INCONCLUSIVE
                if negative and not positive:
                    outcome = VerificationOutcome.DISPROVED
                result = VerificationResult(
                    result_id=f"vr-{uuid4().hex[:10]}",
                    outcome=outcome.value,
                    claim=contract.claim,
                    hypothesis_id=hyp,
                    evidence_ids=evidence_ids,
                    requirements_met=met,
                    requirements_unmet=unmet,
                    finding_status=(
                        FindingStatus.REJECTED.value
                        if outcome == VerificationOutcome.DISPROVED
                        else FindingStatus.CANDIDATE.value
                    ),
                    reason=(
                        "disproved_by_negative_evidence"
                        if outcome == VerificationOutcome.DISPROVED
                        else "insufficient_positive_evidence"
                    ),
                    cannot_become_confirmed=True,
                )
                self.history.append(result)
                return result

        if unmet and len(positive) < contract.min_positive:
            result = VerificationResult(
                result_id=f"vr-{uuid4().hex[:10]}",
                outcome=VerificationOutcome.INCONCLUSIVE.value,
                claim=contract.claim,
                hypothesis_id=hyp,
                evidence_ids=evidence_ids,
                requirements_met=met,
                requirements_unmet=unmet,
                finding_status=FindingStatus.CANDIDATE.value,
                reason="requirements_unmet",
                cannot_become_confirmed=True,
            )
            self.history.append(result)
            return result

        # Positive evidence sufficient and requirements met
        if negative and len(negative) >= len(positive):
            # Contradictory — inconclusive, preserve both
            result = VerificationResult(
                result_id=f"vr-{uuid4().hex[:10]}",
                outcome=VerificationOutcome.INCONCLUSIVE.value,
                claim=contract.claim,
                hypothesis_id=hyp,
                evidence_ids=evidence_ids,
                requirements_met=met,
                requirements_unmet=unmet,
                finding_status=FindingStatus.LIKELY.value,
                reason="contradictory_evidence_preserved",
                cannot_become_confirmed=True,
            )
            self.history.append(result)
            return result

        result = VerificationResult(
            result_id=f"vr-{uuid4().hex[:10]}",
            outcome=VerificationOutcome.CONFIRMED.value,
            claim=contract.claim,
            hypothesis_id=hyp,
            evidence_ids=evidence_ids,
            requirements_met=met,
            requirements_unmet=unmet,
            finding_status=FindingStatus.CONFIRMED.value,
            reason="requirements_met_with_positive_evidence",
            cannot_become_confirmed=False,
        )
        self.history.append(result)
        return result
