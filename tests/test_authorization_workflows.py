from pathlib import Path

from agent_core.authorization.analyzer import AuthorizationAnalyzer
from agent_core.recon.adapter import RawRecon, ReconResultAdapter
from agent_core.workflows.miner import WorkflowMiner

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "sample_recon.json"


def test_authz_surfaces_and_invariants():
    ctx, graph, _ = ReconResultAdapter("e").adapt(RawRecon.from_file(FIXTURE))
    az = AuthorizationAnalyzer("e")
    surfaces = az.surfaces(ctx, graph)
    assert any(s.needs_cross_identity_test for s in surfaces)
    inv = az.ownership_invariants(ctx)
    assert any("I-001" in i for i in inv)


def test_workflow_miner_order_machine():
    ctx, _, _ = ReconResultAdapter("e").adapt(RawRecon.from_file(FIXTURE))
    machines = WorkflowMiner("e").mine(ctx)
    assert machines
    assert machines[0].name == "ORDER"
    assert any(t.action == "refund" for t in machines[0].transitions)
    assert machines[0].invalid_candidates
