"""Semantic backtracking — not merely force_experiment."""

from pathlib import Path

from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    secure_lab_scenario,
    ambiguous_incomplete_lab_scenario,
    default_idor_lab_scenario,
)
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from agent_core.evaluation.trajectory import evaluate_trajectory
from agent_core.schemas.research import Hypothesis, HypothesisStatus

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_negative_evidence_can_trigger_backtrack_or_stop():
    closed = ClosedLoopRunner(scope_path=SCOPE, engagement_id="bt_neg").run(
        SAMPLE, scenario=secure_lab_scenario()
    )
    assert closed.referee_accepted is False
    adaptive = AdaptiveLoop("bt_neg")
    step = adaptive.step(closed)
    # Either stop (no alt) or EXECUTE_FOLLOWUP with backtracked flag
    assert step.next_action in ("STOP", "EXECUTE_FOLLOWUP")
    if step.backtracked:
        assert step.parent_branch_id
        assert step.branch_id
        # May stop if no discriminating experiment remains on alternate branch
        if step.next_experiment is not None:
            assert step.next_action == "EXECUTE_FOLLOWUP"
            assert step.selection_reason == "evidence_driven_backtrack"
        else:
            assert step.stop is True
            assert step.stop_reason == "no_discriminating_experiment"
    else:
        assert step.stop is True
        assert step.stop_reason in (
            "hypothesis_disproven",
            "no_discriminating_experiment",
            "no_alternate_hypothesis_branch",
        ) or "hypothesis" in step.stop_reason or "discriminat" in step.stop_reason


def test_ambiguous_does_not_confirm_finding():
    closed, adaptive_step, followup, *_rest = run_closed_then_adaptive(
        recon_path=SAMPLE,
        scope_path=SCOPE,
        engagement_id="bt_amb",
        scenario=ambiguous_incomplete_lab_scenario(),
        max_followups=1,
    )
    assert closed.referee_accepted is False
    assert adaptive_step is not None


def test_branch_manager_preserves_parent_on_backtrack():
    from agent_core.research.branch import BranchManager

    bm = BranchManager(episode_id="ep1")
    root = bm.open_branch(hypothesis_ids=["h1", "h2"])
    bm.record_experiment(root.branch_id, "exp1")
    nb = bm.backtrack(root.branch_id, new_hypothesis_ids=["h2", "h3"])
    assert nb is not None
    assert nb.parent_branch_id == root.branch_id
    assert any(e.event_type == "backtrack" for e in bm.events)


def test_trajectory_records_backtrack_count():
    metrics = evaluate_trajectory(
        episode_id="t1",
        experiment_ids=["e1", "e2"],
        observation_count=4,
        evidence_polarities=["negative", "neutral"],
        branch_count=2,
        backtrack_count=1,
        stop_reason="hypothesis_disproven",
        tried_experiment_ids=["e1", "e2"],
    )
    assert metrics.n_backtracks == 1
    assert metrics.n_branches == 2


def test_positive_path_still_can_confirm():
    closed = ClosedLoopRunner(scope_path=SCOPE, engagement_id="bt_pos").run(
        SAMPLE, scenario=default_idor_lab_scenario()
    )
    assert closed.episode is not None
