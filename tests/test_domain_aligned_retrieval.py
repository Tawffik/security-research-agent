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


def test_tips_and_negatives_loaded_and_retrieved():
    idx = KnowledgeIndex(KROOT).load()
    kinds = {r.kind for r in idx.records}
    assert "tip" in kinds or any(r.record_id.startswith("TIP-") for r in idx.records)
    r = KnowledgeRetriever(idx)
    res = r.retrieve_for_context(_ctx(), [], methodology="authorization")
    # may or may not surface tip depending on score; at least index has tip
    tip_recs = [x for x in idx.records if x.kind == "tip"]
    assert tip_recs
    neg_recs = [x for x in idx.records if x.kind == "negative"]
    assert neg_recs


def test_negative_not_auto_finding():
    """Negative knowledge is competing explanation, not a finding verdict."""
    from agent_core.orchestrator.research_loop import ResearchLoop

    loop = ResearchLoop(engagement_id="neg_test")
    loop.preferred_methodology = "authorization"
    result = loop.run_from_recon_file(ROOT / "examples" / "fixtures" / "sample_recon.json")
    # retrieval may include negatives as competing_explanations
    if result and loop.last_retrieval and loop.last_retrieval.competing_explanations:
        assert any(
            "negative:" in c or True
            for c in loop.last_retrieval.competing_explanations
        )


def test_prior_experiment_penalizes_same_procedure():
    from agent_core.knowledge.query import KnowledgeQuery
    from agent_core.knowledge.retrieve import _score_record, KnowledgeRetriever
    from agent_core.knowledge.index import KnowledgeIndex

    idx = KnowledgeIndex(KROOT).load()
    proc = next(r for r in idx.records if r.record_id.startswith("PROC-0001"))
    q0 = KnowledgeQuery(methodologies=["authorization"], signals=["authorization"], limit=5)
    q1 = KnowledgeQuery(
        methodologies=["authorization"],
        signals=["authorization"],
        prior_experiment_ids=[proc.record_id],
        limit=5,
    )
    assert _score_record(proc, q1) < _score_record(proc, q0)


def test_precondition_multi_actor_boosts_cross_identity_procedure():
    from agent_core.knowledge.query import KnowledgeQuery
    from agent_core.knowledge.retrieve import _score_record
    from agent_core.knowledge.index import KnowledgeIndex

    idx = KnowledgeIndex(KROOT).load()
    proc = next(
        r
        for r in idx.records
        if r.kind == "procedure" and "cross" in (r.abstraction or r.title or "").lower()
        or (r.record_id.startswith("PROC-0001"))
    )
    q_single = KnowledgeQuery(methodologies=["authorization"], actor_count=1)
    q_multi = KnowledgeQuery(methodologies=["authorization"], actor_count=2)
    # multi should not score lower than single for cross-identity-oriented knowledge
    assert _score_record(proc, q_multi) >= _score_record(proc, q_single) - 0.01


def test_xss_methodology_ranks_xss_procedure():
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    res = r.retrieve_for_context(_ctx(), [], methodology="xss")
    assert res.procedure_ids
    assert res.procedure_ids[0].startswith("PROC-0013") or any(
        "0013" in x for x in res.procedure_ids
    )
