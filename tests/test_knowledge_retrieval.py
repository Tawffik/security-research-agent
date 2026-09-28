"""M1: knowledge index + retrieval must change hypotheses/experiments (not metadata-only)."""

from pathlib import Path

from agent_core.experiments.designer import ExperimentDesigner
from agent_core.hypotheses.engine import HypothesisEngine
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.retrieve import KnowledgeRetriever
from agent_core.orchestrator.research_loop import ResearchLoop
from agent_core.schemas.target import (
    Actor,
    ActorType,
    Endpoint,
    Resource,
    ResourceType,
    TargetContext,
    TargetGraph,
)
from agent_core.target.opportunity import OpportunityEngine


ROOT = Path(__file__).resolve().parents[1]


def _authz_ctx() -> tuple[TargetContext, TargetGraph]:
    ctx = TargetContext(
        engagement_id="eng_m1",
        primary_host="api.example.test",
        actors=[
            Actor(actor_id="user_a", name="A", actor_type=ActorType.USER),
            Actor(actor_id="user_b", name="B", actor_type=ActorType.USER),
        ],
        resources=[
            Resource(
                resource_id="r1",
                name="order-1",
                resource_type=ResourceType.OBJECT,
                owner_actor_id="user_a",
            )
        ],
        endpoints=[
            Endpoint(
                endpoint_id="e1",
                method="GET",
                path="/api/orders/{id}",
                auth_required=True,
                parameters=["id"],
            ),
            Endpoint(
                endpoint_id="e2",
                method="DELETE",
                path="/api/orders/{id}",
                auth_required=True,
                parameters=["id"],
            ),
        ],
    )
    return ctx, TargetGraph(engagement_id="eng_m1")


def test_knowledge_index_loads_curated_md():
    idx = KnowledgeIndex(ROOT / "knowledge").load()
    assert idx.records, "expected curated knowledge records"
    kinds = {r.kind for r in idx.records}
    assert "pattern" in kinds
    assert "procedure" in kinds
    assert any(r.record_id.upper().startswith("PAT") for r in idx.records)
    assert any(r.record_id.upper().startswith("PROC") for r in idx.records)
    for r in idx.records:
        assert r.provenance.get("source_path")
        assert r.provenance.get("loader")


def test_retrieve_authz_returns_pattern_and_procedure():
    ctx, graph = _authz_ctx()
    opps = OpportunityEngine("eng_m1").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    assert "multi_identity" in ret.query_signals
    assert ret.pattern_ids, "expected pattern hits"
    assert ret.procedure_ids, "expected procedure hits"
    assert ret.competing_explanations, "expected competing explanations from knowledge"
    assert ret.provenance


def test_hypothesis_includes_knowledge_provenance_and_alts():
    ctx, graph = _authz_ctx()
    opps = OpportunityEngine("eng_m1").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    eng = HypothesisEngine("eng_m1")
    hyps = eng.generate_from_unknowns([], opps, ctx, retrieval=ret)
    authz_hyps = [h for h in hyps if "Ownership" in h.statement or "mutat" in h.statement.lower()]
    assert authz_hyps
    # Provenance visible in statement
    assert any("knowledge:" in h.statement for h in authz_hyps)
    # Alternatives from knowledge (K* ids) when competing explanations exist
    k_alts = [
        a
        for h in authz_hyps
        for a in h.alternatives
        if a.explanation_id.startswith("K")
    ]
    assert k_alts, "expected knowledge-derived alternative explanations"
    # Engine stores refs
    assert eng.knowledge_refs_by_hyp
    refs = next(iter(eng.knowledge_refs_by_hyp.values()))
    assert refs.get("pattern_ids")
    assert refs.get("procedure_ids")


def test_experiment_is_procedure_driven_when_knowledge_present():
    ctx, graph = _authz_ctx()
    opps = OpportunityEngine("eng_m1").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    eng = HypothesisEngine("eng_m1")
    hyps = eng.generate_from_unknowns([], opps, ctx, retrieval=ret)
    ownership = next(h for h in hyps if "Ownership bypass" in h.statement)
    designer = ExperimentDesigner("eng_m1")
    # Without retrieval — baseline template path
    exp_plain = designer.design(ownership, ctx, retrieval=None)
    # With retrieval — must be procedure-driven
    exp_know = designer.design(ownership, ctx, retrieval=ret)
    assert "Procedure-driven" in exp_know.description or "procedure:" in exp_know.discriminator
    assert any(pid in exp_know.description or pid in exp_know.discriminator for pid in ret.procedure_ids)
    # Knowledge path must differ from plain template (behavioral change)
    assert exp_know.description != exp_plain.description or exp_know.discriminator != exp_plain.discriminator
    assert designer.last_procedure_ids


def test_research_loop_wires_retrieval(tmp_path):
    recon = ROOT / "examples" / "fixtures" / "sample_recon.json"
    if not recon.exists():
        # minimal inline
        p = tmp_path / "recon.json"
        p.write_text(
            '{"primary_host":"api.acme-demo.test","endpoints":[{"method":"GET","path":"/api/orders/{id}"}],'
            '"actors":[{"actor_id":"user_a","name":"a","type":"user"},{"actor_id":"user_b","name":"b","type":"user"}],'
            '"resources":[{"name":"order-1","type":"object","owner_actor_id":"user_a"}]}'
        )
        recon = p
    loop = ResearchLoop("eng_m1_loop")
    result = loop.run_from_recon_file(recon)
    assert loop.last_retrieval is not None
    assert loop.last_retrieval.procedure_ids or loop.last_retrieval.pattern_ids
    assert "knowledge_procedures" in result.summary or "knowledge_patterns" in result.summary
    # At least one experiment should reference procedure when authz opps exist
    if result.experiments and loop.last_retrieval.procedure_ids:
        blob = " ".join(e.description + e.discriminator for e in result.experiments)
        assert any(pid in blob for pid in loop.last_retrieval.procedure_ids) or "Procedure-driven" in blob
