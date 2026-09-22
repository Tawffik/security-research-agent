from pathlib import Path

from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_confirmed_gets_root_cause_and_variants():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_rc")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.referee_accepted is True
    assert result.root_cause is not None
    assert result.root_cause.finding_id == result.finding_id
    assert result.root_cause.evidence_ids
    assert "ownership" in result.root_cause.summary.lower() or "enforcement" in result.root_cause.summary.lower()
    # variants should include other {id} surfaces (users, invoices) not orders
    assert result.variants
    paths = [v.path for v in result.variants]
    assert any("invoice" in p or "user" in p for p in paths)
    assert not any("/orders/" in p for p in paths)


def test_rejected_has_no_root_cause():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_rc_sec")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    assert result.referee_accepted is False
    assert result.root_cause is None
    assert result.variants == []
