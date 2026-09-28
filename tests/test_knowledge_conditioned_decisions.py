"""M3: knowledge conditions hypothesis selection and experiment construction."""

from pathlib import Path

from agent_core.experiments.designer import ExperimentDesigner
from agent_core.hypotheses.engine import HypothesisEngine
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.retrieve import KnowledgeRetriever
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


def _ctx():
    ctx = TargetContext(
        engagement_id="eng_m3",
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
    return ctx, TargetGraph(engagement_id="eng_m3")


def test_a_knowledge_changes_hypothesis_selection():
    ctx, graph = _ctx()
    opps = OpportunityEngine("eng_m3").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    eng_k = HypothesisEngine("eng_m3_k")
    hyps_k = eng_k.generate_from_unknowns([], opps, ctx, retrieval=ret)
    eng_f = HypothesisEngine("eng_m3_f")
    hyps_f = eng_f.generate_from_unknowns([], opps, ctx, retrieval=None)

    assert eng_k.last_mode == "knowledge_driven"
    assert eng_f.last_mode == "fallback"
    stmts_k = [h.statement for h in hyps_k]
    stmts_f = [h.statement for h in hyps_f]
    # Knowledge path embeds pattern id as family selector
    assert any(s.startswith("[PAT-") or "[PAT-" in s for s in stmts_k)
    assert not any(s.startswith("[PAT-") for s in stmts_f)
    # Materially different sets
    assert set(stmts_k) != set(stmts_f)
    assert eng_k.knowledge_refs_by_hyp


def test_b_knowledge_changes_experiment_selection():
    ctx, graph = _ctx()
    opps = OpportunityEngine("eng_m3").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    eng = HypothesisEngine("eng_m3")
    hyps = eng.generate_from_unknowns([], opps, ctx, retrieval=ret)
    vuln = next(h for h in hyps if h.statement.startswith("[PAT-") or "authorization failure" in h.statement.lower())
    designer = ExperimentDesigner("eng_m3")
    exp_k = designer.design(vuln, ctx, retrieval=ret)
    exp_f = designer.design(vuln, ctx, retrieval=None)
    assert "Procedure-driven" in exp_k.description or "procedure:" in exp_k.discriminator
    assert exp_k.required_evidence  # from procedure when available
    assert exp_k.description != exp_f.description or exp_k.discriminator != exp_f.discriminator
    assert "evidence:" in exp_k.discriminator or "EvidenceReq=" in exp_k.description


def test_c_competing_hypotheses_remain():
    ctx, graph = _ctx()
    opps = OpportunityEngine("eng_m3").rank(ctx, graph)
    ret = KnowledgeRetriever(KnowledgeIndex(ROOT / "knowledge").load()).retrieve_for_authz(
        ctx, opps
    )
    hyps = HypothesisEngine("eng_m3").generate_from_unknowns([], opps, ctx, retrieval=ret)
    # At least one vuln-side and one benign/null
    assert any("failure" in h.statement.lower() or "PAT-" in h.statement for h in hyps)
    assert any(
        "intended" in h.statement.lower()
        or "benign" in h.statement.lower()
        or "public" in h.statement.lower()
        or "shared" in h.statement.lower()
        for h in hyps
    )
    # Alternatives on primary hyp
    primary = next(h for h in hyps if "PAT-" in h.statement or "failure" in h.statement.lower())
    assert primary.alternatives or any("benign" in h.statement.lower() for h in hyps)


def test_d_knowledge_miss_fallback():
    ctx, graph = _ctx()
    opps = OpportunityEngine("eng_m3").rank(ctx, graph)
    eng = HypothesisEngine("eng_m3")
    hyps = eng.generate_from_unknowns([], opps, ctx, retrieval=None)
    assert eng.last_mode == "fallback"
    assert any("Ownership bypass" in h.statement or "Action-level" in h.statement for h in hyps)
    designer = ExperimentDesigner("eng_m3")
    h = next(h for h in hyps if "Ownership" in h.statement or "Action-level" in h.statement)
    exp = designer.design(h, ctx, retrieval=None)
    assert exp.description  # still produces experiment
    assert "Procedure-driven" not in exp.description
