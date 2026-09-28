"""GraphQL authorization domain — query builder only (M2 genericity proof)."""

from __future__ import annotations

from agent_core.knowledge.query import KnowledgeQuery


def build_graphql_authorization_query(*, limit: int = 5) -> KnowledgeQuery:
    return KnowledgeQuery(
        domain=None,  # records may not set domain=graphql; use tags
        kinds=["pattern", "case", "procedure", "strategy"],
        signals=["graphql", "mutation", "operation"],
        tags_any=["graphql", "authorization"],
        tags_prefer=["graphql"],
        security_properties=["authorization", "graphql"],
        limit=limit,
        require_domain_match=False,
        extra_competing_explanations=[],
    )
