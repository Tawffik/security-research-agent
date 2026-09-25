"""
Opportunity Engine (V2 §10).

Ranks where the agent should invest research time — offline, from TargetContext
only. No live traffic.
"""

from __future__ import annotations

from agent_core.schemas.research import Opportunity, Priority
from agent_core.schemas.target import Endpoint, TargetContext, TargetGraph


class OpportunityEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0

    def rank(self, ctx: TargetContext, graph: TargetGraph) -> list[Opportunity]:
        opps: list[Opportunity] = []
        multi_identity = len(ctx.actors) >= 2
        has_owned_resources = any(r.owner_actor_id for r in ctx.resources)

        for ep in ctx.endpoints:
            opp = self._from_endpoint(ep, multi_identity, has_owned_resources, ctx)
            if opp:
                opps.append(opp)

        # Workflow / state opportunities when resources have states
        stateful = [r for r in ctx.resources if r.state]
        if stateful and any(
            e.path.endswith("/refund") or "refund" in e.path for e in ctx.endpoints
        ):
            opps.append(
                self._make(
                    type_="state_violation",
                    target="workflow:order→refund",
                    identity_surface=True,
                    object_surface=True,
                    stateful=True,
                    mutation=True,
                    privilege_boundary=True,
                    novelty=0.7,
                    testability=0.6,
                    evidence_potential=0.8,
                    cost=0.4,
                    risk=0.5,
                    priority=Priority.HIGH,
                )
            )

        # Auth lifecycle if reset/login present
        auth_paths = [e for e in ctx.endpoints if "/auth/" in e.path]
        if auth_paths:
            opps.append(
                self._make(
                    type_="authentication_lifecycle",
                    target="auth:*",
                    identity_surface=True,
                    object_surface=False,
                    stateful=True,
                    mutation=True,
                    privilege_boundary=False,
                    novelty=0.5,
                    testability=0.7,
                    evidence_potential=0.6,
                    cost=0.3,
                    risk=0.3,
                    priority=Priority.MEDIUM,
                )
            )

        return sorted(opps, key=self._score, reverse=True)

    def _from_endpoint(
        self,
        ep: Endpoint,
        multi_identity: bool,
        has_owned: bool,
        ctx: TargetContext,
    ) -> Opportunity | None:
        """
        Rank object-keyed endpoints. Per PAT-0003 / STRAT-0002 field data,
        mutating object operations are first-class — not an afterthought to GET.
        """
        object_path = "{id}" in ep.path or "id" in ep.parameters
        mutating = ep.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
        if not object_path and not mutating:
            return None

        is_authz = object_path and (ep.auth_required or multi_identity)
        # Action-level object BOLA surface: mutate + object key
        is_action_bola = object_path and mutating
        if is_action_bola and multi_identity:
            priority = Priority.HIGH
            novelty = 0.75
            evidence_potential = 0.9
            typ = "authorization_mutation"
        elif is_authz and multi_identity and has_owned:
            priority = Priority.HIGH
            novelty = 0.65
            evidence_potential = 0.85
            typ = "authorization"
        elif object_path:
            priority = Priority.MEDIUM
            novelty = 0.45
            evidence_potential = 0.55
            typ = "api_surface"
        else:
            priority = Priority.MEDIUM
            novelty = 0.35
            evidence_potential = 0.4
            typ = "api_surface"

        return self._make(
            type_=typ,
            target=f"{ep.method} {ep.path}",
            identity_surface=bool(ep.auth_required and multi_identity) or multi_identity,
            object_surface=object_path,
            stateful=any(r.state for r in ctx.resources),
            mutation=mutating,
            privilege_boundary=is_authz or is_action_bola,
            novelty=novelty,
            testability=0.8 if multi_identity else 0.4,
            evidence_potential=evidence_potential,
            cost=0.25 if not mutating else 0.4,
            risk=0.3 if not mutating else 0.5,
            priority=priority,
        )

    def _make(self, type_: str, target: str, **kwargs) -> Opportunity:
        self._counter += 1
        return Opportunity(
            opportunity_id=f"opp_{self._counter}",
            type=type_,
            target=target,
            **kwargs,
        )

    @staticmethod
    def _score(o: Opportunity) -> float:
        # Higher evidence potential and novelty, lower cost/risk → higher rank.
        # Boost mutation+object surfaces (STRAT-0002): field BOLA is often action-level.
        base = (
            o.evidence_potential * 0.35
            + o.novelty * 0.25
            + o.testability * 0.2
            + (1.0 - o.cost) * 0.1
            + (1.0 - o.risk) * 0.1
        )
        if o.mutation and o.object_surface:
            base += 0.12
        if o.type == "authorization_mutation":
            base += 0.08
        return base
