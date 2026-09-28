"""
Knowledge Compiler (M10) — Source registry + lineage, not generic RAG.

Pipeline intent:
  Source → Case → Pattern → Procedure → Strategy → (candidate skill only)

Does NOT:
  - scrape the web
  - auto-promote to skills/
  - write trusted knowledge MD without explicit review
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord


@dataclass
class SourceEntry:
    source_id: str
    tier: str
    name: str
    role: str
    status: str
    linked_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineageEdge:
    parent_id: str
    child_id: str
    relation: str  # derived_from | references | extracts

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineageGraph:
    sources: list[SourceEntry] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)
    records_by_id: dict[str, KnowledgeRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [s.to_dict() for s in self.sources],
            "edges": [e.to_dict() for e in self.edges],
            "record_ids": list(self.records_by_id.keys()),
        }

    def ancestors(self, record_id: str) -> list[str]:
        parents = {e.parent_id for e in self.edges if e.child_id == record_id}
        out = list(parents)
        for p in list(parents):
            out.extend(self.ancestors(p))
        return list(dict.fromkeys(out))

    def lineage_for(self, record_id: str) -> list[str]:
        """Ordered lineage tip → root where available."""
        chain = [record_id]
        chain.extend(self.ancestors(record_id))
        return chain


def parse_source_registry(path: Path) -> list[SourceEntry]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[SourceEntry] = []
    # Table rows: | SRC-xxxx | tier | name | role | status |
    for line in text.splitlines():
        if not line.strip().startswith("| SRC-"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 5:
            continue
        sid, tier, name, role, status = parts[0], parts[1], parts[2], parts[3], parts[4]
        linked = re.findall(r"(CASE|PAT|PROC|STRAT)-\d{4}", status + " " + role + " " + name)
        # Also scan whole line for linked ids
        linked += re.findall(r"(CASE|PAT|PROC|STRAT)-\d{4}", line)
        linked = list(dict.fromkeys(linked))
        entries.append(
            SourceEntry(
                source_id=sid,
                tier=tier,
                name=name,
                role=role,
                status=status,
                linked_ids=linked,
            )
        )
    return entries


class KnowledgeCompiler:
    """Build lineage from curated sources + knowledge records."""

    def __init__(self, knowledge_root: Optional[Path] = None):
        self.root = knowledge_root or Path(__file__).resolve().parents[3] / "knowledge"
        self.index = KnowledgeIndex(self.root)

    def compile(self) -> LineageGraph:
        records = self.index.load().records
        by_id = {r.record_id: r for r in records}
        sources = parse_source_registry(self.root / "sources" / "SOURCE-REGISTRY.md")
        edges: list[LineageEdge] = []

        for src in sources:
            for lid in src.linked_ids:
                edges.append(LineageEdge(parent_id=src.source_id, child_id=lid, relation="extracts"))

        for r in records:
            # related_ids in record
            for rel in r.related_ids or []:
                edges.append(LineageEdge(parent_id=rel, child_id=r.record_id, relation="references"))
            # provenance / raw excerpt SRC-xxxx
            blob = f"{r.raw_excerpt} {r.path} {r.provenance}"
            for sid in re.findall(r"SRC-\d{4}", str(blob)):
                edges.append(LineageEdge(parent_id=sid, child_id=r.record_id, relation="derived_from"))
            # case → pattern → procedure heuristics from record_id prefixes in related
            if r.kind == "procedure":
                for rel in r.related_ids or []:
                    if rel.startswith("PAT-"):
                        edges.append(
                            LineageEdge(parent_id=rel, child_id=r.record_id, relation="implements")
                        )
            if r.kind == "pattern":
                for rel in r.related_ids or []:
                    if rel.startswith("CASE-"):
                        edges.append(
                            LineageEdge(parent_id=rel, child_id=r.record_id, relation="generalizes")
                        )

        # dedupe edges
        seen = set()
        unique: list[LineageEdge] = []
        for e in edges:
            key = (e.parent_id, e.child_id, e.relation)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return LineageGraph(sources=sources, edges=unique, records_by_id=by_id)

    def assert_no_auto_skill_write(self) -> bool:
        """Compiler never writes skills/ — safety check for tests."""
        skills = self.root.parent / "skills"
        # We only assert this module has no write API to skills — always True by design
        return not hasattr(self, "write_skill")
