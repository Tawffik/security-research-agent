from pathlib import Path

from agent_core.ledger.checkpoint import CheckpointStore
from agent_core.orchestrator.closed_loop import default_idor_lab_scenario, secure_lab_scenario
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_checkpoint_after_confirmed_adaptive(tmp_path):
    closed, adaptive, cp, _regret, _sur, _mem = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_cp_c",
        scenario=default_idor_lab_scenario(),
    )
    assert cp.checkpoint_id.startswith("CP-")
    assert cp.engagement_id == "eng_cp_c"
    assert cp.evidence_ids
    assert cp.execution_position
    path = CheckpointStore("eng_cp_c").write(cp, tmp_path)
    assert path.exists()
    assert "hypothesis" in path.read_text().lower() or "evidence" in path.read_text().lower()


def test_checkpoint_after_rejected_stop():
    closed, adaptive, cp, _regret, _sur, _mem = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_cp_r",
        scenario=secure_lab_scenario(),
    )
    assert adaptive.stop is True
    assert cp.outcome_so_far == "rejected"
    assert "stop" in cp.execution_position or cp.stop_reason
