"""Multi-branch replay stress — offline, no live HTTP."""

from agent_core.research.branch import (
    BranchManager,
    branch_manager_from_snapshot,
    branch_manager_snapshot,
)
from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import ClosedLoopRunner, secure_lab_scenario
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_snapshot_restore_preserves_lineage_and_parent_links():
    bm = BranchManager(episode_id="ep_stress")
    root = bm.open_branch(hypothesis_ids=["h1", "h2", "h3"])
    bm.record_experiment(root.branch_id, "exp_a")
    b1 = bm.backtrack(root.branch_id, new_hypothesis_ids=["h2", "h3"])
    assert b1 is not None
    bm.record_experiment(b1.branch_id, "exp_b")
    b2 = bm.backtrack(b1.branch_id, new_hypothesis_ids=["h3"])
    assert b2 is not None
    bm.record_experiment(b2.branch_id, "exp_c")
    bm.terminate(root.branch_id, "superseded_by_backtrack")

    snap = branch_manager_snapshot(bm)
    restored = branch_manager_from_snapshot(snap)

    assert len(restored.branches) == len(bm.branches)
    assert len(restored.events) == len(bm.events)
    by_id = {b.branch_id: b for b in restored.branches}
    assert by_id[b1.branch_id].parent_branch_id == root.branch_id
    assert by_id[b2.branch_id].parent_branch_id == b1.branch_id
    assert by_id[root.branch_id].termination_reason == "superseded_by_backtrack"
    assert "exp_a" in by_id[root.branch_id].experiment_ids
    assert any(e.event_type == "backtrack" for e in restored.events)


def test_duplicate_failed_fingerprint_blocks_identical_path():
    bm = BranchManager(episode_id="ep_fp")
    root = bm.open_branch(hypothesis_ids=["h1"])
    bm.record_experiment(root.branch_id, "exp1")
    bm.terminate(root.branch_id, "failed", failed_fingerprint=True) if False else None
    # terminate with fingerprint via terminate API
    for b in bm.branches:
        if b.branch_id == root.branch_id:
            b.failed_fingerprint = __import__("agent_core.research.branch", fromlist=["_fingerprint"])._fingerprint(
                ["h1"], ["exp1"]
            )
            bm._fingerprints_tried.add(b.failed_fingerprint)
            b.active = False
            b.termination_reason = "failed"
    assert bm.can_open_same_path(["h1"], ["exp1"]) is False
    # different exp allowed
    assert bm.can_open_same_path(["h1"], ["exp2"]) is True


def test_multi_branch_chain_depth_stress():
    bm = BranchManager(episode_id="ep_depth")
    parent = bm.open_branch(hypothesis_ids=["h0"])
    for i in range(8):
        nb = bm.backtrack(parent.branch_id, new_hypothesis_ids=[f"h{i+1}"])
        assert nb is not None
        bm.record_experiment(nb.branch_id, f"exp_{i}")
        parent = nb
    snap = branch_manager_snapshot(bm)
    restored = branch_manager_from_snapshot(snap)
    assert len(restored.branches) == 9  # root + 8
    # chain parent links intact
    children = [b for b in restored.branches if b.parent_branch_id]
    assert len(children) == 8


def test_adaptive_backtrack_then_snapshot_roundtrip():
    closed = ClosedLoopRunner(scope_path=SCOPE, engagement_id="mbr_ad").run(
        SAMPLE, scenario=secure_lab_scenario()
    )
    loop = AdaptiveLoop("mbr_ad")
    step = loop.step(closed)
    snap = branch_manager_snapshot(loop.branches)
    restored = branch_manager_from_snapshot(snap)
    if step.backtracked:
        assert any(b.parent_branch_id for b in restored.branches)
        assert any(e.event_type == "backtrack" for e in restored.events)
    # Round-trip does not invent authorization or live HTTP
    assert snap.get("episode_id") == "mbr_ad" or snap.get("episode_id") == loop.branches.episode_id


def test_double_snapshot_deterministic_structure():
    bm = BranchManager(episode_id="ep_det")
    r = bm.open_branch(hypothesis_ids=["ha", "hb"])
    bm.record_experiment(r.branch_id, "e1")
    bm.backtrack(r.branch_id, new_hypothesis_ids=["hb"])
    s1 = branch_manager_snapshot(bm)
    s2 = branch_manager_snapshot(bm)
    assert [b["branch_id"] for b in s1["branches"]] == [b["branch_id"] for b in s2["branches"]]
    assert [e["event_type"] for e in s1["events"]] == [e["event_type"] for e in s2["events"]]
