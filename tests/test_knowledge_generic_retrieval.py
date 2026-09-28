"""M2: generic KnowledgeQuery + retrieve() — domain-neutral core, multi-consumer."""

from pathlib import Path

from agent_core.knowledge.domains.authorization import build_authz_query
from agent_core.knowledge.domains.graphql_authorization import build_graphql_authorization_query
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
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


def _idx() -> KnowledgeIndex:
    return KnowledgeIndex(ROOT / "knowledge").load()


def _authz_ctx():
    ctx = TargetContext(
        engagement_id="eng_m2",
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
    return ctx, TargetGraph(engagement_id="eng_m2")


def test_retrieve_accepts_knowledge_query():
    ret = KnowledgeRetriever(_idx()).retrieve(
        KnowledgeQuery(
            domain="authorization",
            signals=["object_surface", "multi_identity"],
            tags_any=["authorization", "object"],
            limit=5,
        )
    )
    assert isinstance(ret.query_signals, list)
    assert ret.pattern_ids or ret.procedure_ids or ret.cases


def test_authz_wrapper_matches_m1_behavior():
    ctx, graph = _authz_ctx()
    opps = OpportunityEngine("eng_m2").rank(ctx, graph)
    ret = KnowledgeRetriever(_idx()).retrieve_for_authz(ctx, opps)
    assert "multi_identity" in ret.query_signals
    assert ret.pattern_ids
    assert ret.procedure_ids
    assert ret.provenance
    assert ret.competing_explanations
    # authz defaults present
    assert any("public" in c.lower() or "shared" in c.lower() for c in ret.competing_explanations)


def test_ranking_respects_tags_prefer():
    r = KnowledgeRetriever(_idx())
    base = KnowledgeQuery(
        signals=["object"],
        tags_any=["authorization"],
        tags_prefer=[],
        limit=5,
    )
    prefer = KnowledgeQuery(
        signals=["object"],
        tags_any=["authorization"],
        tags_prefer=["mutation"],
        limit=5,
    )
    rb = r.retrieve(base)
    rp = r.retrieve(prefer)
    # prefer should surface mutation-tagged procedure/pattern earlier when present
    mut_ids = {
        x.record_id
        for x in r.index.records
        if "mutation" in [t.lower() for t in x.tags]
    }
    if mut_ids:
        assert any(i in mut_ids for i in (rp.procedure_ids + rp.pattern_ids))


def test_domain_filter_isolation():
    r = KnowledgeRetriever(_idx())
    q = KnowledgeQuery(
        domain="nonexistent_domain_xyz",
        require_domain_match=True,
        tags_any=["authorization"],
        signals=["object"],
        limit=5,
    )
    ret = r.retrieve(q)
    assert ret.pattern_ids == []
    assert ret.procedure_ids == []
    assert ret.cases == []


def test_empty_query_or_no_signals():
    ret = KnowledgeRetriever(_idx()).retrieve(KnowledgeQuery())
    assert ret.query_signals == []
    assert ret.patterns == []
    assert ret.procedures == []


def test_unknown_domain_no_crash():
    ret = KnowledgeRetriever(_idx()).retrieve(
        KnowledgeQuery(domain="totally_unknown", signals=["x"], tags_any=["y"], limit=3)
    )
    assert ret is not None
    assert isinstance(ret.provenance, list)


def test_provenance_preserved_on_generic_path():
    ret = KnowledgeRetriever(_idx()).retrieve(
        KnowledgeQuery(
            tags_any=["authorization"],
            signals=["object_surface"],
            limit=5,
        )
    )
    assert ret.provenance
    for p in ret.provenance:
        assert p.get("record_id")
        assert p.get("kind")
        assert p.get("path") or p.get("source_path")
        assert p.get("loader")


def test_graphql_query_hits_pat_0004():
    """Second consumer uses SAME retrieve() — not retrieve_for_authz."""
    q = build_graphql_authorization_query()
    ret = KnowledgeRetriever(_idx()).retrieve(q)
    ids = set(ret.pattern_ids + [c.record_id for c in ret.cases])
    assert any("0004" in i for i in ids) or any(
        "graphql" in (p.title + p.record_id).lower() for p in ret.patterns
    ), f"expected PAT-0004 or graphql pattern, got {ids}"


def test_build_authz_query_shapes_signals():
    ctx, graph = _authz_ctx()
    opps = OpportunityEngine("eng_m2").rank(ctx, graph)
    q = build_authz_query(ctx, opps)
    assert "multi_identity" in q.signals
    assert q.extra_competing_explanations


def test_authz_query_includes_technology_signals():
    from agent_core.knowledge.domains.authorization import build_authz_query
    from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

    ctx = TargetContext(
        engagement_id="e",
        primary_host="api.example.test",
        technologies=["GraphQL", "JWT"],
        actors=[
            Actor(actor_id="a", name="a", actor_type=ActorType.USER),
            Actor(actor_id="b", name="b", actor_type=ActorType.USER),
        ],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/api/orders/{id}")],
    )
    q = build_authz_query(ctx, [])
    assert any(s.startswith("tech:") for s in q.signals)
    assert "jwt" in q.tags_prefer or "graphql" in q.tags_prefer


def test_authz_query_with_gap_signals():
    from agent_core.knowledge.domains.authorization import build_authz_query_with_gap
    from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

    ctx = TargetContext(
        engagement_id="e",
        primary_host="api.example.test",
        actors=[
            Actor(actor_id="a", name="a", actor_type=ActorType.USER),
            Actor(actor_id="b", name="b", actor_type=ActorType.USER),
        ],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/api/orders/{id}")],
    )
    q = build_authz_query_with_gap(ctx, [], missing_roles=["challenge"])
    assert any(s == "evidence_gap:challenge" for s in q.signals)


def test_different_context_changes_query_signals():
    from agent_core.knowledge.domains.authorization import build_authz_query
    from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

    base = dict(
        engagement_id="e",
        actors=[
            Actor(actor_id="a", name="a", actor_type=ActorType.USER),
            Actor(actor_id="b", name="b", actor_type=ActorType.USER),
        ],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/api/orders/{id}")],
    )
    ctx_jwt = TargetContext(primary_host="api.a.test", technologies=["jwt"], **base)
    ctx_gql = TargetContext(primary_host="api.b.test", technologies=["graphql"], **base)
    q1 = build_authz_query(ctx_jwt, [])
    q2 = build_authz_query(ctx_gql, [])
    assert q1.signals != q2.signals or q1.tags_prefer != q2.tags_prefer
