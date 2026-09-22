"""Closed-loop vertical slice tests (lab fixtures only — not live HTTP)."""

from __future__ import annotations

from pathlib import Path

from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_closed_loop_idor_lab_confirms_with_evidence():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_idor_lab")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.scope_allowed is True
    assert len(result.evidence_ids) >= 2
    assert result.referee_accepted is True
    assert result.final_status == "confirmed"
    assert result.finding_id is not None
    assert any("LabScenario" in lim or "not live" in lim.lower() for lim in result.limitations)
    assert runner.evidence.verify_chain() is True


def test_closed_loop_secure_lab_rejects_false_positive():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_secure_lab")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    assert result.scope_allowed is True
    assert result.referee_accepted is False
    assert result.final_status == "rejected"
    assert result.finding_id is None


def test_closed_loop_out_of_scope_host_denied(tmp_path):
    # Scope only allows acme-demo.test; use scenario host outside scope
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_oos", data_dir=tmp_path)
    # Mutate plan host by using scenario with out-of-scope host after plan
    # Force host via scenario observations; plan still uses fixture host.
    # authorize uses plan.target_context.primary_host which is in scope.
    # Instead write a tiny recon with evil host.
    evil = tmp_path / "evil_recon.json"
    evil.write_text(
        """{
      "primary_host": "evil.not-in-scope.test",
      "actors": [{"name": "a", "roles": ["customer"]}],
      "endpoints": [{"method": "GET", "path": "/x", "host": "evil.not-in-scope.test"}],
      "resources": []
    }""",
        encoding="utf-8",
    )
    result = runner.run(evil, scenario=default_idor_lab_scenario(host="evil.not-in-scope.test"))
    assert result.scope_allowed is False
    assert result.finding_id is None
