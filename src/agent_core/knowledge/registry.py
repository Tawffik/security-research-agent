"""Knowledge registry: curated index + optional generated-candidate overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent_core.knowledge.compiler import GeneratedArtifact, KnowledgeCompiler, run_full_pipeline
from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
from agent_core.knowledge.retrieve import KnowledgeRetriever


class KnowledgeRegistry:
    def __init__(self, knowledge_root: Path):
        self.root = knowledge_root
        self.index = KnowledgeIndex(knowledge_root)

    def load_curated(self) -> list[KnowledgeRecord]:
        return list(self.index.load().records)

    def load_with_generated(
        self, generated: Optional[list[GeneratedArtifact]] = None
    ) -> KnowledgeIndex:
        idx = KnowledgeIndex(self.root).load()
        if generated is None:
            _, generated = run_full_pipeline(KnowledgeCompiler(self.root))
        existing = {r.record_id for r in idx.records}
        for a in generated:
            if a.status != "validated":
                continue
            rec = a.to_knowledge_record()
            if rec.record_id not in existing:
                idx.records.append(rec)
                idx.by_id[rec.record_id.upper()] = rec
                existing.add(rec.record_id)
        return idx

    def retriever_with_generated(
        self, generated: Optional[list[GeneratedArtifact]] = None
    ) -> KnowledgeRetriever:
        return KnowledgeRetriever(self.load_with_generated(generated))
