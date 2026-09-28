"""Contextual retrieval over structured knowledge index — domain-neutral ranking."""

from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass, field
from typing import Any, Optional

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.schemas.research import Opportunity
from agent_core.schemas.target import TargetContext


@dataclass
class RetrievalResult:
    query_signals: list[str]
    patterns: list[KnowledgeRecord] = field(default_factory=list)
    procedures: list[KnowledgeRecord] = field(default_factory=list)
    cases: list[KnowledgeRecord] = field(default_factory=list)
    strategies: list[KnowledgeRecord] = field(default_factory=list)
    competing_explanations: list[str] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pattern_ids(self) -> list[str]:
        return [p.record_id for p in self.patterns]

    @property
    def procedure_ids(self) -> list[str]:
        return [p.record_id for p in self.procedures]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_signals": self.query_signals,
            "pattern_ids": self.pattern_ids,
            "procedure_ids": self.procedure_ids,
            "case_ids": [c.record_id for c in self.cases],
            "competing_explanations": self.competing_explanations,
            "provenance": self.provenance,
        }


def _score_record(rec: KnowledgeRecord, query: KnowledgeQuery) -> float:
    """Domain-neutral score from query fields only."""
    s = 0.0
    tags = set(t.lower() for t in rec.tags)
    domain = (rec.domain or "").lower()
    q_domain = (query.domain or "").lower()

    if query.require_domain_match and q_domain:
        if domain != q_domain:
            return -1.0  # filtered out
        s += 2.0
    elif q_domain and domain == q_domain:
        s += 1.5
    elif q_domain and domain and domain != q_domain and domain not in ("unknown", ""):
        # soft penalty when domains disagree (still allow tag overlap)
        s -= 0.5

    tags_any = [t.lower() for t in query.tags_any]
    tags_prefer = [t.lower() for t in query.tags_prefer]
    signals = [x.lower() for x in query.signals]

    for t in tags_any:
        if t in tags:
            s += 1.0
    for t in tags_prefer:
        if t in tags:
            s += 2.0

    # signal/tag token overlap (generic)
    for sig in signals:
        if sig in tags:
            s += 1.2
        # also match signal tokens against record id/title lightly
        rid = rec.record_id.lower()
        if sig and sig in rid:
            s += 0.4

    for prop in query.security_properties:
        pl = prop.lower()
        if pl and pl in (rec.security_property or "").lower():
            s += 0.8
        if pl and pl in (rec.abstraction or "").lower():
            s += 0.3

    # kind priority: earlier in query.kinds → higher
    if query.kinds and rec.kind in query.kinds:
        idx = query.kinds.index(rec.kind)
        s += max(0.0, 1.0 - 0.15 * idx)
    elif query.kinds:
        return -1.0

    if rec.experiment_steps:
        s += 0.3
    if rec.evidence_required:
        s += 0.2

    return s


class KnowledgeRetriever:
    def __init__(
        self,
        index: Optional[KnowledgeIndex] = None,
        *,
        include_generated: bool = False,
        knowledge_root: Optional[Path] = None,
    ):
        if index is not None:
            self.index = index
        elif include_generated:
            from agent_core.knowledge.index import _default_knowledge_root
            from agent_core.knowledge.registry import KnowledgeRegistry

            reg = KnowledgeRegistry(knowledge_root or _default_knowledge_root())
            self.index = reg.load_with_generated()
        else:
            self.index = (
                KnowledgeIndex(knowledge_root).load()
                if knowledge_root
                else KnowledgeIndex().load()
            )

    def retrieve(self, query: KnowledgeQuery) -> RetrievalResult:
        if not query.signals and not query.tags_any and not query.tags_prefer and not query.domain:
            return RetrievalResult(query_signals=[])

        scored: list[tuple[float, KnowledgeRecord]] = []
        for rec in self.index.records:
            sc = _score_record(rec, query)
            if sc < 0:
                continue
            if sc <= 0 and not (
                query.tags_prefer or query.tags_any or query.signals or query.domain
            ):
                continue
            if sc > 0:
                scored.append((sc, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        limit = max(1, query.limit)
        top = [r for _, r in scored[: max(limit * 3, 10)]]

        def take(kind: str) -> list[KnowledgeRecord]:
            return [r for r in top if r.kind == kind][:limit]

        patterns = take("pattern")
        procedures = take("procedure")
        cases = take("case")
        strategies = take("strategy")

        # Prefer procedures that match tags_prefer among all procedures in index
        if query.tags_prefer:
            prefer = {t.lower() for t in query.tags_prefer}
            preferred_procs = [
                r
                for r in self.index.records
                if r.kind == "procedure" and prefer.intersection(t.lower() for t in r.tags)
            ]
            preferred_procs.sort(
                key=lambda r: _score_record(r, query), reverse=True
            )
            for p in preferred_procs:
                if p not in procedures:
                    procedures.insert(0, p)
            procedures = procedures[:limit]
            preferred_pats = [
                r
                for r in self.index.records
                if r.kind == "pattern" and prefer.intersection(t.lower() for t in r.tags)
            ]
            preferred_pats.sort(key=lambda r: _score_record(r, query), reverse=True)
            for p in preferred_pats:
                if p not in patterns:
                    patterns.insert(0, p)
            patterns = patterns[:limit]

        competing: list[str] = []
        for p in patterns + cases:
            for n in p.not_same_as:
                if n and n not in competing:
                    competing.append(n)
        for extra in query.extra_competing_explanations:
            if extra and extra not in competing:
                competing.append(extra)

        prov = []
        for r in patterns + procedures + cases:
            prov.append(
                {
                    "record_id": r.record_id,
                    "kind": r.kind,
                    "path": r.path,
                    "loader": r.provenance.get("loader"),
                    "source_path": r.provenance.get("source_path", r.path),
                }
            )

        return RetrievalResult(
            query_signals=list(query.signals),
            patterns=patterns,
            procedures=procedures,
            cases=cases,
            strategies=strategies,
            competing_explanations=competing[:10],
            provenance=prov,
        )

    def retrieve_for_authz(
        self,
        ctx: TargetContext,
        opportunities: list[Opportunity],
        *,
        limit: int = 5,
    ) -> RetrievalResult:
        """M1-compatible wrapper: Authorization domain query → generic retrieve."""
        from agent_core.knowledge.domains.authorization import build_authz_query

        query = build_authz_query(ctx, opportunities, limit=limit)
        return self.retrieve(query)
