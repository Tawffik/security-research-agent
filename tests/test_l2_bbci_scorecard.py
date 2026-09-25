from pathlib import Path

from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    public_resource_lab_scenario,
    shared_object_lab_scenario,
    default_idor_lab_scenario,
)
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from agent_core.recon.bbci_contract import normalize_bbci_artifact
from agent_core.recon.adapter import adapt_bbci_artifact, RawRecon, ReconResultAdapter

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_public_resource_not_confirmed_idor():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_pub").run(
        FIXTURE, scenario=public_resource_lab_scenario()
    )
    assert r.referee_accepted is False
    assert r.final_status == "rejected"


def test_shared_acl_not_confirmed_idor():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_share").run(
        FIXTURE, scenario=shared_object_lab_scenario()
    )
    assert r.referee_accepted is False


def test_bbci_contract_normalizes_urls_shape():
    raw = {
        "host": "api.acme-demo.test",
        "urls": ["https://api.acme-demo.test/api/orders/{id}", "/api/invoices/{id}"],
        "identities": [{"id": "user_a", "roles": ["customer"]}, "user_b"],
        "technologies": ["nginx"],
    }
    res = normalize_bbci_artifact(raw)
    assert res.ok
    assert res.normalized["primary_host"] == "api.acme-demo.test"
    assert len(res.normalized["endpoints"]) >= 2
    assert res.normalized["endpoints"][0]["method"] == "GET"


def test_bbci_contract_rejects_missing_host():
    res = normalize_bbci_artifact({"urls": ["/x"]})
    assert res.ok is False


def test_adapt_bbci_then_target_model():
    raw = {
        "target": "api.acme-demo.test",
        "endpoints": [{"method": "GET", "path": "/api/orders/{id}"}],
        "actors": [{"actor_id": "user_a", "type": "user"}],
    }
    (ctx_graph_meta), contract = adapt_bbci_artifact("eng_bbci", raw)
    ctx, graph, meta = ctx_graph_meta
    assert contract.ok
    assert ctx.primary_host == "api.acme-demo.test"
    assert ctx.endpoints


def test_scorecard_on_idor_and_reject():
    idor = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_sc_i",
        scenario=default_idor_lab_scenario(),
    )
    scorecard = idor[-1]
    assert scorecard.validated_finding is True
    assert scorecard.scope_safe is True

    from agent_core.orchestrator.closed_loop import secure_lab_scenario

    secure = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_sc_s",
        scenario=secure_lab_scenario(),
    )
    sc2 = secure[-1]
    assert sc2.false_positive_avoided is True
    assert sc2.validated_finding is False
