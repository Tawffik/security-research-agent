from pathlib import Path

from agent_core.orchestrator.closed_loop import default_idor_lab_scenario, secure_lab_scenario
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from agent_core.research.surprise import SurpriseEngine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_idor_lab_produces_status_surprise():
    closed, _, _, _, surprises, _mem = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_sur_c",
        scenario=default_idor_lab_scenario(),
    )
    assert closed.referee_accepted
    assert surprises
    assert any(s.severity == "high" for s in surprises)
    assert any("ownership" in h.lower() or "authorization" in h.lower() or "missing" in h.lower() for s in surprises for h in s.candidate_hypotheses)


def test_secure_lab_non_owner_403_not_high_surprise():
    eng = SurpriseEngine("x")
    from agent_core.orchestrator.closed_loop import LabObservation

    obs = [
        LabObservation(
            identity="user_b",
            method="GET",
            path="/api/orders/1",
            host="api.acme-demo.test",
            status=403,
            body="forbidden",
        )
    ]
    events = eng.from_lab_observations(obs, suggests_authz_issue=False)
    # 403 when denial expected → no surprise event
    assert events == []
