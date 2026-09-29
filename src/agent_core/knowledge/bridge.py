
"""
Gate 1 — Real Knowledge Bridge (offline bounded corpus).

Notion Control Plane Gate 1:
  Notion/real source → provenance → extract → normalize → Case/Pattern path
  without raw RAG, without auto-promotion, without fabricating facts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_core.knowledge.case_extract import StructuredCase, extract_case_from_text
from agent_core.knowledge.compiler import KnowledgeCompiler, run_full_pipeline
from agent_core.knowledge.dedup import novelty_vs_existing
from agent_core.knowledge.index import KnowledgeIndex, parse_knowledge_markdown
from agent_core.knowledge.source_quality import (
    SourceRecord,
    SourceStatus,
    SourceType,
    score_writeup_text,
)


@dataclass
class CompiledUnit:
    unit_id: str
    kind: str
    lineage: list[str]
    case: Optional[dict[str, Any]] = None
    false_positive_guidance: list[str] = field(default_factory=list)
    source_id: str = ""
    path: str = ""
    trusted: bool = False  # compiled from fixtures remain untrusted candidates unless curated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BridgeReport:
    sources_processed: int = 0
    cases_extracted: int = 0
    units: list[CompiledUnit] = field(default_factory=list)
    lineage_complete: bool = False
    fp_guidance_preserved: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources_processed": self.sources_processed,
            "cases_extracted": self.cases_extracted,
            "units": [u.to_dict() for u in self.units],
            "lineage_complete": self.lineage_complete,
            "fp_guidance_preserved": self.fp_guidance_preserved,
            "notes": list(self.notes),
        }


class KnowledgeBridge:
    """Compile bounded offline sources into lineage-preserving units."""

    def __init__(self, knowledge_root: Path):
        self.root = knowledge_root
        self.fixtures_dir = knowledge_root / "sources" / "fixtures"
        self.compiler = KnowledgeCompiler(knowledge_root)
        self.index = KnowledgeIndex(knowledge_root)

    def list_fixture_sources(self) -> list[Path]:
        if not self.fixtures_dir.is_dir():
            return []
        return sorted(self.fixtures_dir.glob("WRITEUP-*.md"))

    def compile_fixtures(self) -> BridgeReport:
        report = BridgeReport()
        patterns = [r for r in self.index.load().records if r.kind == "pattern"]

        for path in self.list_fixture_sources():
            text = path.read_text(encoding="utf-8")
            report.sources_processed += 1
            # extract source id
            sid = path.stem
            for line in text.splitlines()[:15]:
                if "Source ID:" in line:
                    sid = line.split("Source ID:")[-1].strip()
                    break
            signals = score_writeup_text(text, origin=str(path))
            case = extract_case_from_text(
                text, case_id=f"CASE-FX-{path.stem}", source_id=sid, title=path.stem
            )
            report.cases_extracted += 1
            novelty = novelty_vs_existing(case, patterns)
            lineage = [sid, case.case_id]
            if case.security_property:
                lineage.append(f"property:{case.security_property}")
            unit = CompiledUnit(
                unit_id=case.case_id,
                kind="case",
                lineage=lineage,
                case=case.to_dict(),
                false_positive_guidance=list(case.false_positive_guidance),
                source_id=sid,
                path=str(path),
                trusted=False,
            )
            report.units.append(unit)
            report.notes.append(f"{case.case_id} novelty={novelty} fp={len(case.false_positive_guidance)}")

        # Include negative knowledge as FP guidance units
        neg_dir = self.root / "negative"
        if neg_dir.is_dir():
            for path in sorted(neg_dir.glob("*.md")):
                rec = parse_knowledge_markdown(path, "case")
                if not rec:
                    continue
                report.units.append(
                    CompiledUnit(
                        unit_id=rec.record_id,
                        kind="negative",
                        lineage=[f"source:{path.name}", rec.record_id],
                        false_positive_guidance=[rec.abstraction or rec.title],
                        source_id=path.name,
                        path=str(path),
                        trusted=False,
                    )
                )

        report.lineage_complete = all(u.lineage for u in report.units) and bool(report.units)
        report.fp_guidance_preserved = any(u.false_positive_guidance for u in report.units)
        return report

    def compiler_pipeline_with_lineage(self) -> dict[str, Any]:
        report, arts = run_full_pipeline(self.compiler)
        graph = self.compiler.compile()
        return {
            "compile_report": report.to_dict(),
            "generated": [a.to_dict() for a in arts],
            "lineage_edges": len(graph.edges),
            "sources": len(graph.sources),
        }
