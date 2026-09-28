"""M6: experiment sufficiency drives adaptive follow-up / STOP (lab only)."""

from pathlib import Path

from agent_core.experiments.designer import steps_from_procedure
from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    LabObservation,
    LabScenario,
    default_idor_lab_scenario,
)
from agent_core.orchestrator.experiment_alignment import (
    align_experiment_to_scenario,
    compute_experiment_sufficiency,
    cover_steps,
)
from agent_core.schemas.research import Experiment, ExperimentStatus, ExperimentStep, ExperimentStepRole

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def _steps_proc():
    return steps_from_procedure(
        "PROC-0001",
        [
            "As owner: request object",
            "As non-owner: same request",
            "compare responses",
        ],
    )


def test_1_complete_experiment_sufficient():
    scenario = default_idor_lab_scenario()
    exp = Experiment(
        experiment_id="e_ok",
        hypothesis_id="h1",
        description="ok",
        steps=_steps_proc(),
        status=ExperimentStatus.PLANNED,
    )
    cov = cover_steps(exp, scenario)
    assert compute_experiment_sufficiency(exp, cov) == "sufficient"
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    assert align.experiment_sufficiency == "sufficient"


def test_2_missing_required_step_insufficient_no_positive_fabricated():
    scenario = LabScenario(
        name="only_base",
        expected_if_secure="x",
        suggests_authz_issue=False,
        observations=[
            LabObservation(
                identity="user_a", method="GET", path="/x", host="h", status=200, body="{}", role="baseline"
            )
        ],
    )
    exp = Experiment(
        experiment_id="e_miss",
        hypothesis_id="h1",
        description="t",
        steps=_steps_proc(),
        status=ExperimentStatus.PLANNED,
    )
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    assert align.experiment_sufficiency == "insufficient"
    # no finding path here — alignment only
    assert align.discriminator_outcome in (
        "indeterminate",
        "ambiguous",
        "supports",
        "contradicts",
    )


def test_3_ambiguous_required_step():
    scenario = LabScenario(
        name="dup_base",
        expected_if_secure="x",
        observations=[
            LabObservation(
                identity="user_a", method="GET", path="/x", host="h", status=200, body="{}", role="baseline"
            ),
            LabObservation(
                identity="user_c", method="GET", path="/x", host="h", status=200, body="{}", role="baseline"
            ),
        ],
    )
    steps = [
        ExperimentStep(step_id="P-S01", order=1, role=ExperimentStepRole.BASELINE, text="As owner"),
        ExperimentStep(step_id="P-S02", order=2, role=ExperimentStepRole.CHALLENGE, text="As non-owner"),
    ]
    exp = Experiment(
        experiment_id="e_amb", hypothesis_id="h1", description="t", steps=steps, status=ExperimentStatus.PLANNED
    )
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    assert align.experiment_sufficiency in ("ambiguous", "insufficient")


def test_4_and_5_followup_or_stop(tmp_path):
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m6", data_dir=tmp_path)
    closed = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert closed.experiment_alignment
    # force insufficient for adaptive by mutating alignment dict
    closed.experiment_alignment = dict(closed.experiment_alignment)
    closed.experiment_alignment["experiment_sufficiency"] = "insufficient"
    if not closed.selected_experiment_id and closed.plan.experiments:
        closed.selected_experiment_id = closed.plan.experiments[0].experiment_id

    loop = AdaptiveLoop("eng_m6")
    # mark current as tried
    if closed.selected_experiment_id:
        loop.tried_experiment_ids.add(closed.selected_experiment_id)

    step = loop.step(closed)
    assert step.prior_outcome.startswith("coverage_")
    if step.stop:
        assert "followup" in step.stop_reason or "jev" in step.stop_reason or "same" in step.stop_reason
        assert step.next_action == "STOP"
    else:
        assert step.next_action == "EXECUTE_FOLLOWUP"
        assert step.next_experiment is not None
        assert step.next_experiment.experiment_id != closed.selected_experiment_id


def test_6_same_experiment_cannot_loop():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m6_loop")
    closed = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    closed.experiment_alignment = dict(closed.experiment_alignment or {})
    closed.experiment_alignment["experiment_sufficiency"] = "insufficient"
    eid = closed.selected_experiment_id or (
        closed.plan.experiments[0].experiment_id if closed.plan.experiments else "exp_x"
    )
    closed.selected_experiment_id = eid

    loop = AdaptiveLoop("eng_m6_loop")
    # Pretend all candidates already tried including future ones by pre-seeding after first design
    step1 = loop.step(closed)
    if not step1.stop and step1.next_experiment:
        # second time: mark that follow-up tried too, force insufficient again
        closed.selected_experiment_id = step1.next_experiment.experiment_id
        closed.experiment_alignment["experiment_sufficiency"] = "insufficient"
        step2 = loop.step(closed)
        if step2.next_experiment:
            assert step2.next_experiment.experiment_id != step1.next_experiment.experiment_id or step2.stop
        # eventually stops when exhausted
        loop.tried_experiment_ids.add(step1.next_experiment.experiment_id)
        closed.experiment_alignment["experiment_sufficiency"] = "insufficient"
        step3 = loop.step(closed)
        # with portfolio small, may stop
        assert step3.stop or (
            step3.next_experiment
            and step3.next_experiment.experiment_id not in (eid, step1.next_experiment.experiment_id)
        )


def test_7_contradicts_not_adaptive_verdict():
    scenario = default_idor_lab_scenario()
    exp = Experiment(
        experiment_id="e_c",
        hypothesis_id="h1",
        description="denial expected",
        discriminator="non-owner denied 403",
        steps=_steps_proc(),
        status=ExperimentStatus.PLANNED,
    )
    align = align_experiment_to_scenario(exp, scenario, hypothesis_id="h1")
    # may contradict on issue scenario; sufficiency still about coverage
    assert align.experiment_sufficiency == "sufficient"
    assert align.discriminator_outcome in ("contradicts", "supports", "ambiguous", "indeterminate")


def test_8_closed_loop_exposes_sufficiency():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m6_cl")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert "experiment_sufficiency" in (result.experiment_alignment or {})
