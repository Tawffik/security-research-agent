"""Gate 7 offline foundation — research branches + lineage."""

from agent_core.research.branch import BranchManager


def test_open_and_terminate_branch():
    m = BranchManager(episode_id="ep1")
    b = m.open_branch(hypothesis_ids=["h1"], parent_checkpoint="cp1")
    m.record_experiment(b.branch_id, "exp1")
    m.terminate(b.branch_id, "disproved", return_target="cp1")
    assert b.active is False
    assert b.termination_reason == "disproved"
    assert b.failed_fingerprint


def test_cannot_replay_identical_failed_path():
    m = BranchManager()
    b = m.open_branch(hypothesis_ids=["h1"])
    m.record_experiment(b.branch_id, "exp1")
    m.terminate(b.branch_id, "failed")
    assert m.can_open_same_path(["h1"], ["exp1"]) is False
    assert m.can_open_same_path(["h2"], ["exp1"]) is True


def test_backtrack_creates_new_branch():
    m = BranchManager()
    b = m.open_branch(hypothesis_ids=["h1"])
    m.terminate(b.branch_id, "blocked")
    nb = m.backtrack(b.branch_id, new_hypothesis_ids=["h2"], parent_checkpoint="cp2")
    assert nb is not None
    assert nb.parent_branch_id == b.branch_id
    assert nb.hypothesis_path == ["h2"]
    assert any(e.event_type == "backtrack" for e in m.events)


def test_lineage_events_linked():
    m = BranchManager(episode_id="ep")
    m.open_branch(hypothesis_ids=["h1"])
    assert m.events
    assert m.events[0].episode_id == "ep"
