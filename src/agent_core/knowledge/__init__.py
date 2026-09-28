"""Knowledge runtime: curated MD → index → contextual retrieval (not RAG/vector DB)."""

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever, RetrievalResult
from agent_core.knowledge.compiler import KnowledgeCompiler, LineageGraph, SourceEntry, GeneratedArtifact, run_full_pipeline
from agent_core.knowledge.curated_import import CuratedKnowledgeImporter
from agent_core.knowledge.registry import KnowledgeRegistry
from agent_core.knowledge.expansion import KnowledgeExpansionPipeline
from agent_core.knowledge.source_quality import SourceRecord, SourceStatus, SourceType
from agent_core.knowledge.case_extract import StructuredCase, extract_case_from_text
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
    "KnowledgeCompiler",
    "LineageGraph",
    "SourceEntry",
    "GeneratedArtifact",
    "run_full_pipeline",
    "CuratedKnowledgeImporter",
    "KnowledgeRegistry",
    "KnowledgeExpansionPipeline",
    "SourceRecord",
    "SourceStatus",
    "SourceType",
    "StructuredCase",
    "extract_case_from_text",
]
