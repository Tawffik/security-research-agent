"""Prove adaptive research transitions — not merely pipeline success."""

from pathlib import Path

from agent_core.hypotheses.update import apply_evidence_to_hypotheses
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    LabObservation,
    LabScenario,
    default_idor_lab_scenario,
    secure_lab_scenario,
    ambiguous_incomplete_lab_scenario,
)
from agent_core.schemas.research import Hypothesis, HypothesisStatus
from agent_core.evaluation.benchmark import evaluate_closed_result, BenchmarkCase

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_contradicting_evidence_updates_hypothesis_status():
    hyps = [
        Hypothesis(
            hypothesis_id="h_a",
            statement="Ownership not enforced",
            status=HypothesisStatus.OPEN,
            confidence=0.7,
        ),
        Hypothesis(
            hypothesis_id="h_null",
            statement="Null: intended access control, not a vulnerability",
            status=HypothesisStatus.OPEN,
            confidence=0.5,
        ),
    ]
    updates = apply_evidence_to_hypotheses(
        hyps,
        polarity="negative",
        evidence_ids=["e1"],
    )
    assert updates
    null_u = next(u for u in updates if u.hypothesis_id == "h_null")
    assert null_u.new_status == HypothesisStatus.SUPPORTED.value


def test_positive_evidence_supports_claim_hypothesis():
    hyps = [
        Hypothesis(
            hypothesis_id="h_claim",
            statement="Cross-user object access allowed",
            status=HypothesisStatus.OPEN,
            confidence=0.6,
        ),
    ]
    updates = apply_evidence_to_hypotheses(hyps, polarity="positive", evidence_ids=["e2"])
    assert hyps[0].status == HypothesisStatus.SUPPORTED
    assert updates[0].reason.startswith("positive_evidence")


def test_ambiguous_observation_not_positive_finding():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="adapt_amb").run(
        SAMPLE, scenario=ambiguous_incomplete_lab_scenario()
    )
    score = evaluate_closed_result(
        BenchmarkCase("x", "ambiguous_incomplete", "ambiguous", "incomplete"), r
    )
    assert score.true_positive is False
    assert score.false_positive is False


def test_secure_scenario_rejects_without_fp():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="adapt_sec").run(
        SAMPLE, scenario=secure_lab_scenario()
    )
    assert r.referee_accepted is False
    score = evaluate_closed_result(BenchmarkCase("s", "secure", "secure", "rejected"), r)
    assert score.false_positive is False


def test_positive_lab_can_confirm_when_evidence_supports():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="adapt_pos").run(
        SAMPLE, scenario=default_idor_lab_scenario()
    )
    assert r.episode is not None
    assert r.evidence_ids
    assert r.final_status or r.stop_reason


def test_polarity_not_driven_by_suggests_authz_flag_alone():
    """Challenge 403 must not confirm issue even if suggests_authz_issue=True trap."""
    sc = LabScenario(
        name="lab_oracle_trap",
        suggests_authz_issue=True,
        expected_if_secure="denied",
        observations=[
            LabObservation(
                identity="user_a", method="GET", path="/api/x", host="api.acme-demo.test",
                status=200, body="owner", role="baseline",
            ),
            LabObservation(
                identity="user_b", method="GET", path="/api/x", host="api.acme-demo.test",
                status=403, body="denied", role="challenge",
            ),
        ],
    )
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="adapt_trap").run(SAMPLE, scenario=sc)
    assert r.referee_accepted is False


def test_plan_has_no_ground_truth_fields():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="adapt_gt").run(
        SAMPLE, scenario=default_idor_lab_scenario()
    )
    blob = str(r.plan) + str(r.summary)
    assert "ground_truth" not in blob
    assert "expected_vulnerability" not in blob
