"""Knowledge runtime: curated MD → index → contextual retrieval (not RAG/vector DB)."""

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever, RetrievalResult
from agent_core.knowledge.candidates import (
    KnowledgeCandidate,
    KnowledgeCandidateFactory,
    CandidateStore,
    PromotionGate,
    CandidateStatus,
    CandidateKind,
)

__all__ = [
    "KnowledgeIndex",
    "KnowledgeRecord",
    "KnowledgeQuery",
    "KnowledgeRetriever",
    "RetrievalResult",
    "KnowledgeCandidate",
    "KnowledgeCandidateFactory",
    "CandidateStore",
    "PromotionGate",
    "CandidateStatus",
    "CandidateKind",
]
