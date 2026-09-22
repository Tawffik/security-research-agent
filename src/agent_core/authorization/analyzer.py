"""
Authorization Engine (V2 §34).

Actor → Action → Resource → Condition abstraction.
Produces hypotheses/experiment hints from TargetGraph without live traffic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agent_core.schemas.target import RelationshipKind, TargetContext, TargetGraph


@dataclass
class AuthzSurface:
    endpoint_id: str
    resource_id: str
    owner_actor_id: Optional[str]
    action: str
    condition: str
    needs_cross_identity_test: bool


class AuthorizationAnalyzer:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id

    def surfaces(self, ctx: TargetContext, graph: TargetGraph) -> list[AuthzSurface]:
        out: list[AuthzSurface] = []
        multi = len(ctx.actors) >= 2
        for edge in graph.edges:
            if edge.kind != RelationshipKind.CAN_ACCESS:
                continue
            owner = None
            for r in ctx.resources:
                if r.resource_id == edge.target_id:
                    owner = r.owner_actor_id
                    break
            out.append(
                AuthzSurface(
                    endpoint_id=edge.source_id,
                    resource_id=edge.target_id,
                    owner_actor_id=owner,
                    action=edge.action or "access",
                    condition=edge.condition or "",
                    needs_cross_identity_test=bool(multi and owner),
                )
            )
        return out

    def ownership_invariants(self, ctx: TargetContext) -> list[str]:
        inv: list[str] = []
        if any(r.owner_actor_id for r in ctx.resources):
            inv.append("I-001: User can access only owned objects")
        if any(a.actor_type.value == "admin" for a in ctx.actors):
            inv.append("I-006: Client-side role does not determine server authorization")
        return inv
