"""
Knowledge Compiler — Source registry, lineage, normalize/classify/cluster.

Pipeline implemented offline on curated corpus:
  SOURCE → EXTRACT → NORMALIZE → CLASSIFY → CLUSTER
  (GENERATE new MD / PROMOTE skills are explicit and NOT automatic)

Does NOT:
  - scrape the web
  - auto-write knowledge/*.md
  - auto-promote skills/
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
    relation: str

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
        chain = [record_id]
        chain.extend(self.ancestors(record_id))
        return chain


@dataclass
class NormalizedUnit:
    unit_id: str
    kind: str
    title: str
    domain: str
    security_property: str
    technologies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    experiment_steps: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    abstraction: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompileReport:
    sources: int = 0
    extracted: int = 0
    normalized: int = 0
    classified: dict[str, int] = field(default_factory=dict)
    clustered: int = 0
    units: list[NormalizedUnit] = field(default_factory=list)
    lineage_edges: int = 0
    deduped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": self.sources,
            "extracted": self.extracted,
            "normalized": self.normalized,
            "classified": dict(self.classified),
            "clustered": self.clustered,
            "lineage_edges": self.lineage_edges,
            "deduped": self.deduped,
            "unit_ids": [u.unit_id for u in self.units],
        }


def parse_source_registry(path: Path) -> list[SourceEntry]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[SourceEntry] = []
    for line in text.splitlines():
        if not line.strip().startswith("| SRC-"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 5:
            continue
        sid, tier, name, role, status = parts[0], parts[1], parts[2], parts[3], parts[4]
        linked = re.findall(r"(CASE|PAT|PROC|STRAT)-\d{4}", line)
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


def _tech_from_record(r: KnowledgeRecord) -> list[str]:
    techs: list[str] = []
    blob = f"{r.raw_excerpt} {' '.join(r.tags)} {r.title}".lower()
    for token in ("graphql", "rest", "jwt", "oauth", "websocket", "grpc", "soap"):
        if token in blob:
            techs.append(token)
    return list(dict.fromkeys(techs))


class KnowledgeCompiler:
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
            for rel in r.related_ids or []:
                edges.append(LineageEdge(parent_id=rel, child_id=r.record_id, relation="references"))
            blob = f"{r.raw_excerpt} {r.path} {r.provenance}"
            for sid in re.findall(r"SRC-\d{4}", str(blob)):
                edges.append(LineageEdge(parent_id=sid, child_id=r.record_id, relation="derived_from"))
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

        seen: set[tuple[str, str, str]] = set()
        unique: list[LineageEdge] = []
        for e in edges:
            key = (e.parent_id, e.child_id, e.relation)
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return LineageGraph(sources=sources, edges=unique, records_by_id=by_id)

    def extract(self) -> list[KnowledgeRecord]:
        return list(self.index.load().records)

    def normalize(self, records: Optional[list[KnowledgeRecord]] = None) -> list[NormalizedUnit]:
        records = records if records is not None else self.extract()
        graph = self.compile()
        units: list[NormalizedUnit] = []
        seen_ids: set[str] = set()
        for r in records:
            if r.record_id in seen_ids:
                continue
            seen_ids.add(r.record_id)
            src_ids = [
                e.parent_id
                for e in graph.edges
                if e.child_id == r.record_id and e.parent_id.startswith("SRC-")
            ]
            units.append(
                NormalizedUnit(
                    unit_id=r.record_id,
                    kind=r.kind,
                    title=r.title,
                    domain=r.domain or "authorization",
                    security_property=r.security_property or "authorization",
                    technologies=_tech_from_record(r),
                    tags=list(r.tags or []),
                    source_ids=src_ids,
                    related_ids=list(r.related_ids or []),
                    experiment_steps=list(r.experiment_steps or []),
                    evidence_required=list(r.evidence_required or []),
                    abstraction=r.abstraction or "",
                    path=r.path,
                )
            )
        return units

    def classify_counts(self, units: list[NormalizedUnit]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for u in units:
            counts[u.kind] = counts.get(u.kind, 0) + 1
        return counts

    def cluster_by_property(self, units: list[NormalizedUnit]) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {}
        for u in units:
            key = u.security_property or "unknown"
            clusters.setdefault(key, []).append(u.unit_id)
        return clusters

    def run_pipeline(self) -> CompileReport:
        graph = self.compile()
        records = self.extract()
        units = self.normalize(records)
        return CompileReport(
            sources=len(graph.sources),
            extracted=len(records),
            normalized=len(units),
            classified=self.classify_counts(units),
            clustered=len(self.cluster_by_property(units)),
            units=units,
            lineage_edges=len(graph.edges),
            deduped=max(0, len(records) - len(units)),
        )

    def assert_no_auto_skill_write(self) -> bool:
        return not hasattr(self, "write_skill")
