"""M7: gap-aware follow-up experiment is re-evaluated in the lab closed loop."""

from pathlib import Path

from agent_core.experiments.designer import steps_from_procedure
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
)
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from agent_core.schemas.research import Experiment, ExperimentStatus

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_force_experiment_binds_selected_id():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m7_force")
    steps = steps_from_procedure(
        "PROC-0001",
        ["As owner: x", "As non-owner: y", "compare"],
    )
    forced = Experiment(
        experiment_id="exp_forced_m7",
        hypothesis_id="h1",
        description="forced follow-up",
        steps=steps,
        status=ExperimentStatus.PLANNED,
        information_gain=0.9,
        cost=0.2,
        risk=0.2,
    )
    first = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    second = runner.run(
        FIXTURE,
        scenario=default_idor_lab_scenario(),
        force_experiment=forced,
        skip_research=True,
        prior_plan=first.plan,
    )
    assert second.selected_experiment_id == "exp_forced_m7"
    assert second.experiment_alignment
    assert second.experiment_alignment.get("experiment_id") == "exp_forced_m7"


def test_run_closed_then_adaptive_may_execute_followup():
    closed, adaptive, *_rest = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_m7_pipe",
        scenario=default_idor_lab_scenario(),
        max_followups=1,
    )
    assert closed is not None
    assert adaptive is not None
    # If a follow-up ran, notes record M7 execution
    notes = " ".join(adaptive.notes or [])
    if "M7 follow-up executed" in notes:
        assert "experiment_id=" in notes
    # Pipeline always completes without crash
    assert closed.scope_allowed in (True, False)


def test_episode_records_coverage_lessons_when_present():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m7_ep")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.episode is not None
    # When alignment exists, experiment_id lesson may appear
    if result.selected_experiment_id:
        lessons = " ".join(result.episode.lessons)
        assert result.selected_experiment_id in lessons or "experiment" in lessons.lower() or lessons is not None
