from pathlib import Path

from agent_core.findings.poc import PoCMinimizer
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    LabObservation,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_poc_requires_evidence():
    m = PoCMinimizer("e")
    assert (
        m.minimize(
            finding_id="f1",
            observations=[
                LabObservation(
                    identity="user_a",
                    method="GET",
                    path="/x",
                    host="api.acme-demo.test",
                    status=200,
                    body='{"owner":"a"}',
                )
            ],
            evidence_ids=[],
        )
        is None
    )


def test_closed_loop_confirmed_has_minimal_poc():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_poc")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.poc is not None
    assert result.poc.finding_id == result.finding_id
    assert result.poc.evidence_ids
    assert len(result.poc.steps) >= 2
    assert "Steps" in result.poc.markdown
    # first step should be owner-ish
    assert result.poc.steps[0].actor in ("user_a", "owner") or result.poc.steps[0].actor.endswith("_a")


def test_rejected_has_no_poc():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_poc_sec")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    assert result.poc is None
