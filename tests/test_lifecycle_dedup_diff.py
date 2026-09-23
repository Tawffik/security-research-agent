from agent_core.experiments.dedup import ExperimentDeduper, experiment_fingerprint
from agent_core.experiments.differential import compare_identity_pair
from agent_core.findings.lifecycle import FindingLifecycle, FindingLifecycleState, lifecycle_from_closed_loop
from agent_core.orchestrator.closed_loop import (
    LabObservation,
    default_idor_lab_scenario,
    secure_lab_scenario,
)
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_lifecycle_no_skip_to_confirmed():
    lc = FindingLifecycle("f1")
    assert lc.transition(FindingLifecycleState.CONFIRMED) is False
    assert lc.transition(FindingLifecycleState.INVESTIGATING) is True


def test_lifecycle_from_idor_pipeline():
    result = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_lc",
        scenario=default_idor_lab_scenario(),
    )
    closed = result[0]
    lifecycle = result[11]
    assert lifecycle.state == FindingLifecycleState.CONFIRMED
    assert closed.referee_accepted


def test_dedup_detects_repeat():
    d = ExperimentDeduper()
    fp, ok = d.check_and_register(method="GET", path="/api/orders/1", identity="user_b")
    assert ok is True
    fp2, ok2 = d.check_and_register(method="GET", path="/api/orders/1", identity="user_b")
    assert ok2 is False
    assert fp == fp2


def test_differential_idor_vs_secure():
    a = LabObservation("user_a", "GET", "/api/orders/1", "h", 200, '{"owner":"a"}')
    b_bad = LabObservation("user_b", "GET", "/api/orders/1", "h", 200, '{"owner":"a"}')
    b_ok = LabObservation("user_b", "GET", "/api/orders/1", "h", 403, "denied")
    r1 = compare_identity_pair(a, b_bad)
    assert r1.interpretation == "possible_authorization_issue"
    r2 = compare_identity_pair(a, b_ok)
    assert r2.interpretation == "ownership_or_authz_appears_enforced"
