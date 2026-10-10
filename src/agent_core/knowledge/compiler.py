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
                    domain=r.domain or "unknown",
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

    def generalize(self, units=None):
        units = units if units is not None else self.normalize()
        return generalize_cluster(units)

    def generate(self, units=None):
        units = units if units is not None else self.normalize()
        return generate_from_units(units)

    def generate_validated(self, units=None):
        return validate_generated(self.generate(units))

    def run_full(self):
        return run_full_pipeline(self)

    def assert_no_auto_skill_write(self) -> bool:
        return not hasattr(self, "write_skill")


@dataclass
class GeneratedArtifact:
    """
    Compiler GENERATE output — NOT trusted curated knowledge.
    Status remains candidate until promotion + import.
    """

    artifact_id: str
    kind: str  # pattern | procedure | strategy
    title: str
    domain: str
    security_property: str
    abstraction: str
    experiment_steps: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    source_unit_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.35
    status: str = "generated_candidate"  # generated_candidate | rejected | validated
    validation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_knowledge_record(self) -> KnowledgeRecord:
        """Convert to KnowledgeRecord for optional retrieval overlay (untrusted path)."""
        return KnowledgeRecord(
            record_id=self.artifact_id,
            kind=self.kind,
            title=self.title,
            domain=self.domain,
            path=f"generated://{self.artifact_id}",
            security_property=self.security_property,
            abstraction=self.abstraction,
            experiment_steps=list(self.experiment_steps),
            evidence_required=list(self.evidence_required),
            related_ids=list(self.source_unit_ids),
            tags=list(self.tags) + ["generated_candidate", "untrusted"],
            raw_excerpt=self.abstraction[:500],
            provenance={
                "origin": "knowledge_compiler_generate",
                "status": self.status,
                "source_unit_ids": list(self.source_unit_ids),
                "source_ids": list(self.source_ids),
                "confidence": self.confidence,
            },
        )


def generalize_cluster(units: list[NormalizedUnit]) -> list[dict[str, Any]]:
    """GENERALIZE: group normalized units by security_property + kind."""
    groups: dict[str, list[NormalizedUnit]] = {}
    for u in units:
        key = f"{u.security_property}|{u.kind}"
        groups.setdefault(key, []).append(u)
    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        prop, kind = key.split("|", 1)
        out.append(
            {
                "security_property": prop,
                "kind": kind,
                "member_ids": [m.unit_id for m in members],
                "technologies": list(
                    dict.fromkeys(t for m in members for t in m.technologies)
                ),
                "tags": list(dict.fromkeys(t for m in members for t in m.tags)),
            }
        )
    return out


def generate_from_units(units: list[NormalizedUnit]) -> list[GeneratedArtifact]:
    """
    GENERATE: produce pattern/procedure/strategy candidates from clustered units.
    Generic — driven by unit kind + property, not vuln-specific hard branches.
    """
    artifacts: list[GeneratedArtifact] = []
    by_prop: dict[str, list[NormalizedUnit]] = {}
    for u in units:
        by_prop.setdefault(u.security_property or "unknown", []).append(u)

    n = 0
    for prop, members in by_prop.items():
        cases = [m for m in members if m.kind == "case"]
        patterns = [m for m in members if m.kind == "pattern"]
        procedures = [m for m in members if m.kind == "procedure"]

        # Pattern candidate from cases when no pattern yet for property
        if cases and not patterns:
            n += 1
            case = cases[0]
            artifacts.append(
                GeneratedArtifact(
                    artifact_id=f"GEN-PAT-{n:04d}",
                    kind="pattern",
                    title=f"Generated pattern for {prop}",
                    domain=case.domain,
                    security_property=prop,
                    abstraction=(
                        f"Generalized from case {case.unit_id}: "
                        f"{case.abstraction or case.title}"
                    )[:500],
                    source_unit_ids=[c.unit_id for c in cases[:5]],
                    source_ids=list(dict.fromkeys(s for c in cases for s in c.source_ids)),
                    technologies=list(
                        dict.fromkeys(t for c in cases for t in c.technologies)
                    ),
                    tags=["generated", prop, "pattern"],
                    confidence=0.3,
                    validation_notes=["derived_from_cases_only"],
                )
            )

        # Procedure candidate from patterns
        if patterns and not procedures:
            n += 1
            pat = patterns[0]
            steps = list(pat.experiment_steps) or [
                "Establish baseline under authorized identity",
                "Apply challenge under alternate identity or context",
                "Compare observations and collect required evidence",
            ]
            artifacts.append(
                GeneratedArtifact(
                    artifact_id=f"GEN-PROC-{n:04d}",
                    kind="procedure",
                    title=f"Generated procedure for {prop}",
                    domain=pat.domain,
                    security_property=prop,
                    abstraction=f"Procedure scaffold from pattern {pat.unit_id}",
                    experiment_steps=steps,
                    evidence_required=list(pat.evidence_required)
                    or ["baseline observation", "challenge observation", "scope decision"],
                    source_unit_ids=[p.unit_id for p in patterns[:5]],
                    source_ids=list(dict.fromkeys(s for p in patterns for s in p.source_ids)),
                    technologies=list(
                        dict.fromkeys(t for p in patterns for t in p.technologies)
                    ),
                    tags=["generated", prop, "procedure"],
                    confidence=0.32,
                    validation_notes=["derived_from_patterns"],
                )
            )

        # Strategy candidate when we have both pattern and procedure
        if patterns and procedures:
            n += 1
            artifacts.append(
                GeneratedArtifact(
                    artifact_id=f"GEN-STRAT-{n:04d}",
                    kind="strategy",
                    title=f"Generated strategy for {prop}",
                    domain=patterns[0].domain,
                    security_property=prop,
                    abstraction=(
                        f"Prefer minimum discriminating experiment using "
                        f"{procedures[0].unit_id} guided by {patterns[0].unit_id}"
                    ),
                    source_unit_ids=[patterns[0].unit_id, procedures[0].unit_id],
                    tags=["generated", prop, "strategy"],
                    confidence=0.34,
                    validation_notes=["requires_benchmark_before_trust"],
                )
            )
    return artifacts


def validate_generated(artifacts: list[GeneratedArtifact]) -> list[GeneratedArtifact]:
    """Quality gate: reject empty abstraction / universal language."""
    out: list[GeneratedArtifact] = []
    for a in artifacts:
        notes = list(a.validation_notes)
        if not a.abstraction.strip():
            a.status = "rejected"
            notes.append("empty_abstraction")
        low = a.abstraction.lower()
        if "always vulnerable" in low or "never vulnerable" in low:
            a.status = "rejected"
            notes.append("absolute_claim_forbidden")
        if a.status != "rejected":
            a.status = "validated"
            notes.append("structure_ok")
        a.validation_notes = notes
        out.append(a)
    return out


# Monkey-patch methods onto KnowledgeCompiler via extension functions used by run_full_pipeline
def run_full_pipeline(compiler: KnowledgeCompiler) -> tuple[CompileReport, list[GeneratedArtifact]]:
    report = compiler.run_pipeline()
    generalized = generalize_cluster(report.units)
    generated = generate_from_units(report.units)
    validated = validate_generated(generated)
    # Attach counts onto report via side dict for callers
    report.classified = {
        **report.classified,
        "generated": len(validated),
        "generated_validated": sum(1 for a in validated if a.status == "validated"),
        "generalized_groups": len(generalized),
    }
    return report, validated
