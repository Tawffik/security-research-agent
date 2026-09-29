"""Domain-aligned retrieval: methodology match drives procedure ranking."""

from pathlib import Path

from agent_core.evaluation.research_utility import (
    KnowledgeCondition,
    ScenarioSpec,
    run_condition,
)
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.retrieve import KnowledgeRetriever, score_alignment_breakdown
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def _ctx():
    return TargetContext(
        engagement_id="e",
        primary_host="api.acme-demo.test",
        actors=[
            Actor(actor_id="a", name="a", actor_type=ActorType.USER),
            Actor(actor_id="b", name="b", actor_type=ActorType.USER),
        ],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/api/x")],
    )


def test_authz_outranks_cross_domain():
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    res = r.retrieve_for_context(_ctx(), [], methodology="authorization")
    assert res.procedure_ids
    assert res.procedure_ids[0].startswith("PROC-000")
    assert "PROC-0010" not in res.procedure_ids[:1]
    assert "PROC-0012" not in res.procedure_ids[:1]


def test_ssrf_outranks_authz():
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    res = r.retrieve_for_context(_ctx(), [], methodology="ssrf")
    assert res.procedure_ids[0] == "PROC-0010"


def test_business_logic_outranks_authz():
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    res = r.retrieve_for_context(_ctx(), [], methodology="business_logic")
    assert res.procedure_ids[0] == "PROC-0012"


def test_alignment_unknown_vs_mismatch():
    recs = KnowledgeIndex(KROOT).load().records
    ssrf = next(x for x in recs if x.record_id == "PROC-0010")
    q = KnowledgeQuery(methodologies=["ssrf"], security_properties=["ssrf"])
    br = score_alignment_breakdown(ssrf, q)
    assert br["methodology"] == "MATCH"
    q2 = KnowledgeQuery(methodologies=["authorization"])
    br2 = score_alignment_breakdown(ssrf, q2)
    assert br2["methodology"] == "MISMATCH"


def test_missing_methodology_unknown_not_mismatch():
    from agent_core.knowledge.index import KnowledgeRecord

    rec = KnowledgeRecord(
        record_id="X",
        kind="procedure",
        title="t",
        domain="",
        path="x",
        security_property="",
    )
    q = KnowledgeQuery(methodologies=["ssrf"])
    br = score_alignment_breakdown(rec, q)
    assert br["methodology"] == "UNKNOWN"


def test_hard_scenarios_select_aligned_procedures():
    cases = [
        ("hard_authz", "hard_authz", "PROC-000"),
        ("business_logic", "business_logic", "PROC-0012"),
        ("hard_ssrf", "hard_ssrf", "PROC-0010"),
    ]
    for sid, factory, prefix in cases:
        tr, m, _ = run_condition(
            condition=KnowledgeCondition.CURATED,
            scenario=ScenarioSpec(sid, factory, "vulnerable", "confirmed"),
            recon_path=FIXTURE,
            scope_path=SCOPE,
            knowledge_root=KROOT,
            engagement_suffix=f"_dom_{sid}",
        )
        assert m.true_positive is True
        assert tr.procedure_ids
        assert tr.procedure_ids[0].startswith(prefix) or prefix in tr.procedure_ids[0]


def test_none_still_fn_on_hard():
    tr, m, _ = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=ScenarioSpec("hard_ssrf", "hard_ssrf", "vulnerable", "confirmed"),
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert m.false_negative is True


def test_evidence_gap_signals_in_query():
    from agent_core.knowledge.retrieve import build_contextual_query

    q = build_contextual_query(
        _ctx(), [], methodology="authorization", evidence_gaps=["challenge"]
    )
    assert any(s == "evidence_gap:challenge" for s in q.signals)
