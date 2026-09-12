"""
Researcher -> Skeptic -> Referee — MASTER SPEC §10.

This is the single highest-leverage pattern in the whole system, confirmed
by the real-world "Singularity" hackbot (Rez0 + xssdoctor, 126 bugs / 5
months): a dedicated adversarial validator that is REWARDED for killing
findings, not confirming them, cut their false-positive rate from ~80% to
~60%. This module encodes that as a structural constraint rather than a
prompt suggestion: a Finding literally cannot reach CONFIRMED status
without passing through a SkepticVerdict that itself cites evidence.

The three roles are represented as protocols (interfaces), not concrete
LLM calls — plug in whatever model / skill you want per role. Nothing here
prescribes which model does the reasoning; it prescribes that the roles
cannot be collapsed into one pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from agent_core.evidence.store import Evidence, EvidencePolarity, EvidenceStore, FindingStatus


class SkepticQuestion(str, Enum):
    ALTERNATE_EXPLANATION = "is_there_an_alternate_explanation"
    INTENDED_BEHAVIOR = "is_this_behavior_intended"
    AUTH_ACTUALLY_BYPASSED = "is_authentication_actually_bypassed"
    AUTHZ_ACTUALLY_CROSSED = "is_authorization_actually_crossed"
    REPRODUCIBLE = "is_this_reproducible"
    IMPACT_REAL = "is_the_impact_real"
    EVIDENCE_COMPLETE = "is_the_evidence_complete"
    IN_SCOPE = "is_the_target_in_scope"
    POSSIBLE_DUPLICATE = "could_this_be_a_duplicate"
    TEST_ARTIFACT = "could_this_be_a_test_artifact"


@dataclass
class ResearcherClaim:
    hypothesis_id: str
    title: str
    claim: str
    supporting_evidence_ids: list[str]
    severity_estimate: str


@dataclass
class SkepticVerdict:
    claim: ResearcherClaim
    answers: dict[SkepticQuestion, bool]   # True = "this concern is resolved / not a problem"
    disproof_attempted: bool
    disproof_evidence_id: Optional[str]    # evidence the skeptic itself generated trying to break it
    notes: str = ""

    @property
    def survived(self) -> bool:
        """A claim only survives if every skeptic question resolved cleanly
        AND the skeptic actually attempted to disprove it (not just asked
        questions rhetorically)."""
        return self.disproof_attempted and all(self.answers.values())


@dataclass
class RefereeRuling:
    accepted: bool
    finding_id: Optional[str]
    final_status: FindingStatus
    reason: str


ResearcherFn = Callable[[str], ResearcherClaim]
SkepticFn = Callable[[ResearcherClaim, EvidenceStore], SkepticVerdict]


class VerificationLoop:
    """
    Wires the three roles together against a shared EvidenceStore so every
    verdict is itself auditable evidence, not a bare boolean.
    """

    def __init__(
        self,
        evidence_store: EvidenceStore,
        researcher_fn: ResearcherFn,
        skeptic_fn: SkepticFn,
        min_confidence_to_confirm: float = 0.75,
    ):
        self.evidence_store = evidence_store
        self.researcher_fn = researcher_fn
        self.skeptic_fn = skeptic_fn
        self.min_confidence_to_confirm = min_confidence_to_confirm

    def run(self, hypothesis_id: str, target: str) -> RefereeRuling:
        claim = self.researcher_fn(hypothesis_id)
        verdict = self.skeptic_fn(claim, self.evidence_store)

        # The skeptic's own attempt to disprove is itself recorded as evidence,
        # regardless of outcome — this is what prevents the loop from being
        # re-run pointlessly after a restart (negative evidence persists).
        polarity = EvidencePolarity.NEGATIVE if not verdict.survived else EvidencePolarity.POSITIVE
        skeptic_evidence = self.evidence_store.record(
            target=target,
            action="skeptic_disproof_attempt",
            input_data=str(claim.claim),
            expected="skeptic fails to disprove the claim",
            observed=verdict.notes or str(verdict.answers),
            polarity=polarity,
            confidence=1.0 if verdict.disproof_attempted else 0.0,
            source="verification_loop.skeptic",
            related_hypothesis=hypothesis_id,
        )

        return self._referee(claim, verdict, skeptic_evidence)

    def _referee(self, claim: ResearcherClaim, verdict: SkepticVerdict, skeptic_evidence: Evidence) -> RefereeRuling:
        if not verdict.disproof_attempted:
            return RefereeRuling(
                accepted=False,
                finding_id=None,
                final_status=FindingStatus.CANDIDATE,
                reason="Skeptic did not actually attempt disproof — cannot promote past CANDIDATE.",
            )

        if not verdict.survived:
            failed = [q.value for q, ok in verdict.answers.items() if not ok]
            return RefereeRuling(
                accepted=False,
                finding_id=None,
                final_status=FindingStatus.REJECTED,
                reason=f"Skeptic disproved or flagged unresolved concerns: {failed}",
            )

        evidence_ids = list(set(claim.supporting_evidence_ids + [skeptic_evidence.evidence_id]))
        finding_id = self.evidence_store.create_finding(
            title=claim.title,
            evidence_ids=evidence_ids,
            severity=claim.severity_estimate,
        )
        self.evidence_store.set_finding_status(finding_id, FindingStatus.CONFIRMED)
        return RefereeRuling(
            accepted=True,
            finding_id=finding_id,
            final_status=FindingStatus.CONFIRMED,
            reason="Skeptic attempted disproof and every question resolved cleanly.",
        )
