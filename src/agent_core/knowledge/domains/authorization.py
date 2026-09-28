"""Authorization domain: context → KnowledgeQuery + default competitors."""

from __future__ import annotations

from agent_core.knowledge.query import KnowledgeQuery
from agent_core.schemas.research import Opportunity
from agent_core.schemas.target import TargetContext

AUTHZ_DEFAULT_COMPETING = [
    "Resource is intentionally public",
    "Resource is shared via ACL by design",
    "Role grants broader access than ownership",
]


def build_authz_query(
    ctx: TargetContext,
    opportunities: list[Opportunity],
    *,
    limit: int = 5,
) -> KnowledgeQuery:
    signals: list[str] = []
    tags_any: list[str] = ["authorization", "object"]
    tags_prefer: list[str] = []

    if len(ctx.actors) >= 2:
        signals.append("multi_identity")
        tags_any.append("cross-identity")
        tags_any.append("ownership")
    if any(r.owner_actor_id for r in ctx.resources):
        signals.append("owned_resource")
        tags_prefer.append("ownership")
    if any(o.object_surface for o in opportunities):
        signals.append("object_surface")
        tags_any.append("object")
    if any(o.mutation for o in opportunities):
        signals.append("mutation")
        tags_prefer.append("mutation")
    if any(o.type in ("authorization", "authorization_mutation") for o in opportunities):
        signals.append("authorization_opportunity")
        tags_any.extend(["bola", "idor", "authorization"])

    for ep in ctx.endpoints:
        path = (ep.path or "").lower()
        if "{id}" in path or "order" in path or "user" in path:
            signals.append("object_path")
            break

    # Target technologies as soft signals (ranking only; not execution permission)
    for tech in list(getattr(ctx, "technologies", None) or [])[:8]:
        tname = str(tech).strip().lower()
        if tname:
            signals.append(f"tech:{tname}")
            tags_prefer.append(tname)

    if getattr(ctx, "primary_host", None):
        signals.append("host_context")

    return KnowledgeQuery(
        domain="authorization",
        kinds=["pattern", "procedure", "case", "strategy"],
        signals=signals,
        tags_any=list(dict.fromkeys(tags_any)),
        tags_prefer=list(dict.fromkeys(tags_prefer)),
        security_properties=["authorization", "ownership", "object-level"],
        limit=limit,
        require_domain_match=False,  # many records tag authorization without strict domain field
        extra_competing_explanations=list(AUTHZ_DEFAULT_COMPETING),
    )


def build_authz_query_with_gap(
    ctx: TargetContext,
    opportunities: list[Opportunity],
    *,
    missing_roles: list[str] | None = None,
    limit: int = 5,
) -> KnowledgeQuery:
    """Contextual retrieval: include evidence-gap roles as ranking signals."""
    q = build_authz_query(ctx, opportunities, limit=limit)
    for role in missing_roles or []:
        q.signals.append(f"evidence_gap:{role}")
        q.tags_prefer.append(role)
    return q
