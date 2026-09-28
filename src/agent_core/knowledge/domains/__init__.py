"""Domain query builders — convert app context into KnowledgeQuery."""

from agent_core.knowledge.domains.authorization import build_authz_query
from agent_core.knowledge.domains.graphql_authorization import build_graphql_authorization_query

__all__ = ["build_authz_query", "build_graphql_authorization_query"]
