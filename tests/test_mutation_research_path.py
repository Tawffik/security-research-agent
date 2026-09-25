"""Behavioral change from PAT-0003 / STRAT-0002 — wired into engines."""

from agent_core.experiments.designer import ExperimentDesigner
from agent_core.hypotheses.engine import HypothesisEngine
from agent_core.schemas.research import Hypothesis, HypothesisStatus
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


def _ctx_with_mutate() -> tuple[TargetContext, TargetGraph]:
    ctx = TargetContext(
        engagement_id="eng_mut",
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
            Endpoint(
                endpoint_id="e3",
                method="PATCH",
                path="/api/orders/{id}",
                auth_required=True,
                parameters=["id"],
            ),
        ],
    )
    return ctx, TargetGraph(engagement_id="eng_mut")


def test_mutation_opportunities_rank_above_plain_get():
    ctx, graph = _ctx_with_mutate()
    opps = OpportunityEngine("eng_mut").rank(ctx, graph)
    assert opps
    mut = [o for o in opps if o.mutation and o.object_surface]
    assert mut, "expected mutation object opportunities"
    gets = [o for o in opps if not o.mutation and o.object_surface]
    if gets:
        assert OpportunityEngine._score(mut[0]) >= OpportunityEngine._score(gets[0])


def test_hypothesis_includes_action_level_mutation():
    ctx, graph = _ctx_with_mutate()
    opps = OpportunityEngine("eng_mut").rank(ctx, graph)
    hyps = HypothesisEngine("eng_mut").generate_from_unknowns([], opps, ctx)
    statements = " ".join(h.statement.lower() for h in hyps)
    assert "mutat" in statements or "delete" in statements or "action-level" in statements


def test_designer_builds_mutation_experiment():
    ctx, _ = _ctx_with_mutate()
    h = Hypothesis(
        hypothesis_id="h_mut",
        statement="Action-level object authorization failure: non-owner can mutate delete object",
        primary_explanation="missing ownership on DELETE",
        confidence=0.6,
        status=HypothesisStatus.OPEN,
    )
    exp = ExperimentDesigner("eng_mut").design(h, ctx)
    blob = (exp.description + exp.discriminator).lower()
    assert "side effect" in blob or "mutat" in blob
    assert exp.information_gain >= 0.85
