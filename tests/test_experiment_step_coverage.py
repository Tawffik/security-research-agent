"""M5: structured experiment step coverage (lab only)."""

from pathlib import Path

from agent_core.experiments.designer import steps_from_procedure
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    LabObservation,
    LabScenario,
    default_idor_lab_scenario,
)
from agent_core.orchestrator.experiment_alignment import (
    align_experiment_to_scenario,
    baseline_challenge_pair,
    cover_steps,
)
from agent_core.schemas.research import (
    Experiment,
    ExperimentStatus,
    ExperimentStep,
    ExperimentStepRole,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_1_procedure_steps_compile_roles_and_ids():
    steps = steps_from_procedure(
        "PROC-0001",
        [
            "As owner: request object → record status + ownership markers",
            "As non-owner: same request → compare",
            "Prefer one differential pair — do not enumerate all IDs",
        ],
    )
    assert [s.role for s in steps] == [
        ExperimentStepRole.BASELINE,
        ExperimentStepRole.CHALLENGE,
        ExperimentStepRole.COMPARE,
    ]
    assert steps[0].step_id == "PROC-0001-S01"
    assert steps[1].step_id == "PROC-0001-S02"
    assert steps[2].step_id == "PROC-0001-S03"
    # deterministic
    assert steps_from_procedure("PROC-0001", [steps[0].text])[0].step_id == "PROC-0001-S01"


def test_2_step_coverage_when_roles_mapped():
    scenario = default_idor_lab_scenario()
    steps = steps_from_procedure(
        "PROC-0001",
        [
            "As owner: request object",
            "As non-owner: same request",
            "compare responses",
        ],
    )
    exp = Experiment(
        experiment_id="e1",
        hypothesis_id="h1",
        description="test",
        steps=steps,
        status=ExperimentStatus.PLANNED,
    )
    cov = cover_steps(exp, scenario)
    assert [c.status for c in cov] == ["covered", "covered", "covered"]


def test_3_missing_step_no_false_evidence():
    scenario = LabScenario(
        name="only_baseline",
        expected_if_secure="x",
        suggests_authz_issue=False,
        observations=[
            LabObservation(
                identity="user_a",
                method="GET",
                path="/api/x",
                host="h",
                status=200,
                body="{}",
                role="baseline",
            )
        ],
    )
    steps = steps_from_procedure(
        "PROC-0001",
        ["As owner: x", "As non-owner: y", "compare"],
    )
    exp = Experiment(
        experiment_id="e2",
        hypothesis_id="h1",
        description="t",
        steps=steps,
        status=ExperimentStatus.PLANNED,
    )
    cov = cover_steps(exp, scenario)
    assert cov[0].status == "covered"
    assert cov[1].status == "missing"
    assert cov[2].status == "ambiguous" or cov[2].status == "missing"
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    # alignment meta only — does not fabricate POSITIVE vulnerability evidence
    assert align.step_coverage


def test_4_ambiguous_mapping():
    scenario = LabScenario(
        name="two_baselines",
        expected_if_secure="x",
        observations=[
            LabObservation(
                identity="user_a", method="GET", path="/a", host="h", status=200, body="{}", role="baseline"
            ),
            LabObservation(
                identity="user_c", method="GET", path="/a", host="h", status=200, body="{}", role="baseline"
            ),
        ],
    )
    steps = [
        ExperimentStep(step_id="P-S01", order=1, role=ExperimentStepRole.BASELINE, text="As owner")
    ]
    exp = Experiment(
        experiment_id="e3", hypothesis_id="h1", description="t", steps=steps, status=ExperimentStatus.PLANNED
    )
    cov = cover_steps(exp, scenario)
    assert cov[0].status == "ambiguous"


def test_5_baseline_challenge_pair_not_list_index():
    scenario = LabScenario(
        name="reversed_list_but_roles",
        expected_if_secure="x",
        suggests_authz_issue=True,
        observations=[
            # challenge listed first — roles still authoritative
            LabObservation(
                identity="user_b", method="GET", path="/o", host="h", status=200, body='{"owner":"user_a"}', role="challenge"
            ),
            LabObservation(
                identity="user_a", method="GET", path="/o", host="h", status=200, body='{"owner":"user_a"}', role="baseline"
            ),
        ],
    )
    b, c = baseline_challenge_pair(scenario)
    assert b is not None and c is not None
    assert b.identity == "user_a"
    assert c.identity == "user_b"
    steps = steps_from_procedure("PROC-0001", ["As owner: x", "As non-owner: y", "compare"])
    exp = Experiment(
        experiment_id="e4",
        hypothesis_id="h1",
        description="proc",
        discriminator="procedure:PROC-0001|differential",
        steps=steps,
        status=ExperimentStatus.PLANNED,
    )
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    assert align.baseline_ref and "user_a" in align.baseline_ref
    assert align.challenge_ref and "user_b" in align.challenge_ref


def test_6_closed_loop_includes_step_coverage_when_steps_present():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m5")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.experiment_alignment is not None
    # knowledge path usually attaches steps from procedure
    sc = result.experiment_alignment.get("step_coverage") or []
    if result.plan.experiments and result.plan.experiments[0].steps:
        assert sc
        assert result.experiment_alignment.get("baseline_ref")
        assert result.experiment_alignment.get("challenge_ref")


def test_7_step_coverage_not_a_finding():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m5_safe")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    # finding only via referee path; alignment evidence is NEUTRAL source
    for eid in result.evidence_ids:
        row = runner.evidence.conn.execute(
            "SELECT source, polarity FROM evidence WHERE evidence_id=?", (eid,)
        ).fetchone()
        if row and "experiment_alignment" in row[0]:
            assert row[1] == "neutral"
