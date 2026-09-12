import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.ledger.state_tree import ExecutionLedger, NodeStatus


def make_ledger(tmp_path) -> ExecutionLedger:
    return ExecutionLedger.open(tmp_path / "test_ledger.db")


def test_create_and_fetch_node(tmp_path):
    ledger = make_ledger(tmp_path)
    node = ledger.create_node(parent_id=None, kind="target_understanding", label="acme.com")
    fetched = ledger.get_node(node.node_id)
    assert fetched.label == "acme.com"
    assert fetched.status == NodeStatus.PENDING


def test_rejected_node_kept_as_negative_evidence(tmp_path):
    ledger = make_ledger(tmp_path)
    node = ledger.create_node(parent_id=None, kind="hypothesis", label="H001")
    ledger.mark_rejected(node.node_id, reason="skeptic disproved the claim")
    fetched = ledger.get_node(node.node_id)
    assert fetched.status == NodeStatus.REJECTED
    assert fetched.metadata["rejection_reason"] == "skeptic disproved the claim"
    # Rejected nodes must NOT disappear from unresolved queries silently —
    # they simply stop appearing as "unresolved" so they aren't re-attempted.
    assert node.node_id not in [n.node_id for n in ledger.unresolved_nodes()]


def test_resume_sees_only_unresolved_nodes(tmp_path):
    ledger = make_ledger(tmp_path)
    root = ledger.create_node(parent_id=None, kind="target_understanding", label="acme.com")
    done = ledger.create_node(parent_id=root.node_id, kind="recon", label="recon")
    pending = ledger.create_node(parent_id=root.node_id, kind="recon", label="js-analysis")
    ledger.mark_audited_complete(done.node_id, confidence=0.9)

    unresolved_labels = {n.label for n in ledger.unresolved_nodes()}
    assert "js-analysis" in unresolved_labels
    assert "recon" not in unresolved_labels  # completed, should not resurface


def test_budget_circuit_breaker_trips(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.set_budget("target:acme.com", token_budget=1000, tool_call_budget=5)
    assert ledger.spend("target:acme.com", tokens=500, tool_calls=2) is True
    assert ledger.spend("target:acme.com", tokens=600, tool_calls=1) is False  # 1100 > 1000


def test_checkpoint_recorded(tmp_path):
    ledger = make_ledger(tmp_path)
    root = ledger.create_node(parent_id=None, kind="target_understanding", label="acme.com")
    cp_id = ledger.checkpoint(reason="unit test checkpoint", root_node_id=root.node_id)
    row = ledger.conn.execute("SELECT checkpoint_id FROM checkpoints WHERE checkpoint_id=?", (cp_id,)).fetchone()
    assert row is not None
