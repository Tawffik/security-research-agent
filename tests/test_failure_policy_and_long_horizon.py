"""Failure diagnosis → next action; long-horizon checkpoint + branch restore."""

from pathlib import Path

from agent_core.tools.capability import FailureClass, CapabilityTracker
from agent_core.tools.failure_policy import next_action_for_failure, failure_is_terminal, FAILURE_NEXT_ACTION
from agent_core.ledger.checkpoint import CheckpointStore
from agent_core.research.branch import BranchManager, branch_manager_snapshot, branch_manager_from_snapshot
from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import ClosedLoopRunner, secure_lab_scenario
from agent_core.recon.bbci_contract import parse_bbci_live_txt

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_all_failure_classes_have_next_action():
    for fc in FailureClass:
        action = next_action_for_failure(fc)
        assert action in (
            "try_alternative", "backtrack", "defer", "block", "stop", "fix_precondition"
        )
        assert fc.value in FAILURE_NEXT_ACTION or action == "try_alternative"


def test_scope_and_budget_are_terminal_or_block():
    assert failure_is_terminal(FailureClass.SCOPE_BLOCK)
    assert failure_is_terminal(FailureClass.BUDGET_EXHAUSTION)
    assert failure_is_terminal(FailureClass.AUTHORIZATION_DENIED)
    assert not failure_is_terminal(FailureClass.DISCRIMINATION_FAILURE)


def test_capability_tracker_classify_and_suggested_action():
    t = CapabilityTracker("eng")
    fc = t.classify_denial_reason("host out of scope")
    assert fc == FailureClass.SCOPE_BLOCK
    rec = t.record_failure(fc, detail="scope", suggested_action=next_action_for_failure(fc))
    assert rec.suggested_action == "block"
    assert rec.failure_class == FailureClass.SCOPE_BLOCK.value


def test_long_horizon_checkpoint_with_branch_snapshot_roundtrip(tmp_path):
    closed = ClosedLoopRunner(scope_path=SCOPE, engagement_id="lh1").run(
        SAMPLE, scenario=secure_lab_scenario()
    )
    adaptive = AdaptiveLoop("lh1")
    step = adaptive.step(closed)
    snap = branch_manager_snapshot(adaptive.branches)
    store = CheckpointStore("lh1")
    cp = store.from_closed_and_adaptive(
        closed,
        step,
        label="post_adaptive",
        branch_snapshot=snap,
        failure_classes=["discrimination_failure"] if not step.stop else [],
        tried_experiment_ids=list(adaptive.tried_experiment_ids),
    )
    path = store.write(cp, tmp_path)
    assert path.exists()
    import json
    data = json.loads(path.read_text())
    assert data["checkpoint_id"].startswith("CP-")
    restored_bm = branch_manager_from_snapshot(data.get("branch_snapshot") or {})
    if step.backtracked:
        assert any(b.parent_branch_id for b in restored_bm.branches)
    # Resume: tried experiments preserved so no blind re-run of same exp
    assert set(data.get("tried_experiment_ids") or []) == set(adaptive.tried_experiment_ids)


def test_malformed_bbci_artifact_does_not_crash():
    bad = "@@@\nnot-a-url\n"
    res = parse_bbci_live_txt(bad, program_name="x.example")
    # may be ok=False or empty endpoints — must not raise
    assert res is not None
    assert hasattr(res, "ok")


def test_empty_bbci_artifact_safe():
    res = parse_bbci_live_txt("", program_name="")
    assert res is not None
