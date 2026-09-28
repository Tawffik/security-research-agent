"""
Knowledge Expansion Pipeline orchestrator (offline).

Source → quality → extract case → novelty/dedup → generate candidates → validate
Never auto-promotes to trusted knowledge/*.md corpus.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_core.knowledge.case_extract import StructuredCase, extract_case_from_text
from agent_core.knowledge.compiler import KnowledgeCompiler, generate_from_units, validate_generated
from agent_core.knowledge.dedup import (
    cluster_cases_to_patterns,
    find_duplicate_patterns,
    novelty_vs_existing,
)
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.source_quality import (
    SourceRecord,
    SourceStatus,
    SourceType,
    score_writeup_text,
)


@dataclass
class ExpansionResult:
    source: SourceRecord
    case: Optional[StructuredCase] = None
    novelty: str = ""
    pattern_clusters: list[dict[str, Any]] = field(default_factory=list)
    generated_ids: list[str] = field(default_factory=list)
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "case": self.case.to_dict() if self.case else None,
            "novelty": self.novelty,
            "pattern_clusters": list(self.pattern_clusters),
            "generated_ids": list(self.generated_ids),
            "blocked_reason": self.blocked_reason,
        }


class KnowledgeExpansionPipeline:
    def __init__(self, knowledge_root: Path):
        self.root = knowledge_root
        self.compiler = KnowledgeCompiler(knowledge_root)
        self.index = KnowledgeIndex(knowledge_root)

    def ingest_text_source(
        self,
        *,
        source_id: str,
        text: str,
        origin: str,
        source_type: SourceType = SourceType.WRITEUP,
        title: str = "",
        url: str = "",
        auto_accept: bool = False,
    ) -> ExpansionResult:
        signals = score_writeup_text(text, origin=origin)
        record = SourceRecord(
            source_id=source_id,
            source_type=source_type,
            origin=origin,
            title=title,
            url=url,
            signals=signals,
            reliability=signals.source_reliability,
            provenance={"pipeline": "knowledge_expansion_v1"},
        )
        # Quality gate: very low priority or empty text → reject process
        if not text.strip():
            record.status = SourceStatus.REJECTED
            return ExpansionResult(source=record, blocked_reason="empty_text")
        if signals.priority_score() < 0.15 and not auto_accept:
            record.status = SourceStatus.REJECTED
            return ExpansionResult(
                source=record, blocked_reason="priority_below_threshold"
            )

        if auto_accept:
            record.status = SourceStatus.ACCEPTED
        else:
            record.status = SourceStatus.UNVERIFIED

        # Only extract structured case when accepted or explicitly auto (offline demos)
        if record.status not in (SourceStatus.ACCEPTED, SourceStatus.UNVERIFIED):
            return ExpansionResult(source=record, blocked_reason="source_not_processable")

        case = extract_case_from_text(
            text, case_id=f"CASE-X-{source_id}", source_id=source_id, title=title
        )
        record.extraction_status = "extracted"

        patterns = [r for r in self.index.load().records if r.kind == "pattern"]
        novelty = novelty_vs_existing(case, patterns)
        clusters = [c.to_dict() for c in cluster_cases_to_patterns([case])]

        # GENERATE remains candidate-level via compiler units — optional when ACCEPTED
        generated_ids: list[str] = []
        if record.status == SourceStatus.ACCEPTED and novelty != "duplicate_information":
            units = self.compiler.normalize()
            arts = validate_generated(generate_from_units(units))
            generated_ids = [a.artifact_id for a in arts if a.status == "validated"]

        return ExpansionResult(
            source=record,
            case=case,
            novelty=novelty,
            pattern_clusters=clusters,
            generated_ids=generated_ids,
        )

    def pattern_duplicates(self) -> list[tuple[str, str, str]]:
        return find_duplicate_patterns(self.index.load().records)
