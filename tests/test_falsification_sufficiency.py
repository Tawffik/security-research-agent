"""P0: falsification contract, evidence sufficiency, evidence package, loss attribution."""

from agent_core.evidence.store import Evidence, EvidencePolarity, EvidenceStore
from agent_core.evidence.sufficiency import (
    SufficiencyLevel,
    assess_evidence_sufficiency,
)
from agent_core.evaluation.loss_attribution import StagePresence, attribute_loss, LossStage
from agent_core.hypotheses.engine import HypothesisEngine
from agent_core.research.falsification import (
    apply_falsification_to_hypothesis,
    evaluate_falsification,
)
from agent_core.schemas.research import Hypothesis, HypothesisStatus, Opportunity
from agent_core.schemas.target import TargetContext
from agent_core.verification.evidence_package import build_evidence_package


def _ev(eid: str, pol: EvidencePolarity, notes: str = "") -> Evidence:
    import time
    return Evidence(
        evidence_id=eid,
        target="https://api.example/obj/1",
        action="GET",
        input_data="id=1",
        expected="authz enforced",
        observed=notes or pol.value,
        artifact_path=None,
        polarity=pol,
        confidence=0.8,
        related_hypothesis="h1",
        source="lab",
        timestamp=time.time(),
        prev_hash="",
    )


def test_hypothesis_engine_sets_falsification_contract():
    eng = HypothesisEngine("eng-f")
    hyps = eng._from_opportunities(
        retrieval=None,
        unknowns=[],
        mutation_opps=[],
        authz_opps=[
            Opportunity(
                opportunity_id="o1",
                type="authorization",
                target="https://api.example/orders/1",
                identity_surface=True,
                object_surface=True,
            )
        ],
        state_opps=[],
        multi=True,
    )
    assert hyps
    h = hyps[0]
    assert h.falsification_condition
    assert h.expected_security_property
    assert "non-owner" in h.falsification_condition.lower() or "denied" in h.falsification_condition.lower()


def test_negative_evidence_falsifies_hypothesis():
    h = Hypothesis(
        hypothesis_id="h1",
        statement="Ownership bypass: non-owner can access object",
        expected_security_property="non-owners denied",
        falsification_condition="non-owner denied without private fields",
    )
    store_ev = [
        _ev("e-neg", EvidencePolarity.NEGATIVE, notes="expected_secure denied 403"),
    ]
    result = evaluate_falsification(h, store_ev)
    assert result.falsified is True
    updated = apply_falsification_to_hypothesis(h, store_ev)
    assert updated.status == HypothesisStatus.REJECTED
    assert "e-neg" in updated.falsification_evidence_ids


def test_positive_only_does_not_falsify():
    h = Hypothesis(
        hypothesis_id="h2",
        statement="Ownership bypass",
        falsification_condition="denied",
        expected_security_property="owners only",
    )
    result = evaluate_falsification(h, [_ev("e-pos", EvidencePolarity.POSITIVE)])
    assert result.falsified is False


def test_sufficiency_interesting_evidence_not_confirmed():
    evs = [_ev("p1", EvidencePolarity.POSITIVE)]
    # no disproof, no verification → cannot confirm
    rep = assess_evidence_sufficiency(
        evs,
        disproof_attempted=False,
        verification_accepted=False,
        min_positive_for_confirm=1,
    )
    assert rep.can_confirm is False
    assert rep.level in (
        SufficiencyLevel.CANDIDATE.value,
        SufficiencyLevel.LIKELY.value,
        SufficiencyLevel.INSUFFICIENT.value,
    )


def test_sufficiency_confirm_requires_disproof_and_verification():
    evs = [
        _ev("p1", EvidencePolarity.POSITIVE),
        _ev("p2", EvidencePolarity.POSITIVE),
    ]
    rep = assess_evidence_sufficiency(
        evs,
        disproof_attempted=True,
        verification_accepted=True,
        min_positive_for_confirm=2,
    )
    assert rep.can_confirm is True
    assert rep.level == SufficiencyLevel.CONFIRMED.value


def test_sufficiency_rejects_on_negative_only():
    rep = assess_evidence_sufficiency(
        [_ev("n1", EvidencePolarity.NEGATIVE)],
        disproof_attempted=True,
        verification_accepted=False,
    )
    assert rep.level == SufficiencyLevel.REJECTED.value
    assert rep.can_confirm is False


def test_evidence_package_not_verifiable_without_evidence():
    pkg = build_evidence_package(
        package_id="pkg1",
        hypothesis_id="h1",
        hypothesis_statement="x",
        claim="y",
        supporting_evidence_ids=[],
        researcher_confidence=0.99,  # confidence alone is not enough
    )
    assert pkg.is_verifiable() is False
    assert pkg.researcher_confidence == 0.99


def test_evidence_package_verifiable_with_support():
    pkg = build_evidence_package(
        package_id="pkg2",
        hypothesis_id="h1",
        hypothesis_statement="x",
        claim="y",
        supporting_evidence_ids=["e1"],
        falsification_condition="denied",
        expected_security_property="owners only",
    )
    assert pkg.is_verifiable() is True
    d = pkg.to_dict()
    assert d["falsification_condition"] == "denied"


def test_loss_attribution_hypothesis_stage():
    present = StagePresence(recon=True, adapter=True, modeling=True, hypothesis=False)
    rep = attribute_loss("cand-1", present)
    assert rep.loss_stage == LossStage.HYPOTHESIS_LOSS.value


def test_loss_attribution_full_pipeline():
    present = StagePresence(
        recon=True,
        adapter=True,
        modeling=True,
        hypothesis=True,
        experiment_selected=True,
        executed=True,
        observation=True,
        interpretation=True,
        falsification_evaluated=True,
        verification=True,
        promoted=True,
    )
    rep = attribute_loss("cand-2", present)
    assert rep.loss_stage == LossStage.NONE.value
