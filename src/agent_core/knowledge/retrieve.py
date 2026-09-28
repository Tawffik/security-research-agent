"""Contextual retrieval over structured knowledge index — keyword+signal, not embeddings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
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


class KnowledgeRetriever:
    def __init__(self, index: Optional[KnowledgeIndex] = None):
        self.index = index or KnowledgeIndex().load()

    def retrieve_for_authz(
        self,
        ctx: TargetContext,
        opportunities: list[Opportunity],
        *,
        limit: int = 5,
    ) -> RetrievalResult:
        signals: list[str] = []
        if len(ctx.actors) >= 2:
            signals.append("multi_identity")
        if any(r.owner_actor_id for r in ctx.resources):
            signals.append("owned_resource")
        if any(o.object_surface for o in opportunities):
            signals.append("object_surface")
        if any(o.mutation for o in opportunities):
            signals.append("mutation")
        if any(
            o.type in ("authorization", "authorization_mutation") for o in opportunities
        ):
            signals.append("authorization_opportunity")
        # endpoint shape
        for ep in ctx.endpoints:
            path = (ep.path or "").lower()
            if "{id}" in path or "order" in path or "user" in path:
                signals.append("object_path")
                break

        if not signals:
            return RetrievalResult(query_signals=[])

        # Score records in authorization domain / tags
        def score(rec: KnowledgeRecord) -> float:
            s = 0.0
            if rec.domain == "authorization":
                s += 2.0
            tags = set(rec.tags)
            if "authorization" in tags or "bola" in tags or "idor" in tags:
                s += 1.5
            if "multi_identity" in signals and (
                "cross-identity" in tags or "ownership" in tags
            ):
                s += 2.0
            if "mutation" in signals and "mutation" in tags:
                s += 2.5
            if "object_surface" in signals and "object" in tags:
                s += 1.5
            if "owned_resource" in signals and "ownership" in tags:
                s += 1.0
            # prefer procedures/patterns for experiment design
            if rec.kind == "procedure":
                s += 0.5
            if rec.kind == "pattern":
                s += 0.4
            if rec.experiment_steps:
                s += 0.3
            return s

        ranked = sorted(self.index.records, key=score, reverse=True)
        ranked = [r for r in ranked if score(r) > 0][: max(limit * 3, 10)]

        patterns = [r for r in ranked if r.kind == "pattern"][:limit]
        procedures = [r for r in ranked if r.kind == "procedure"][:limit]
        cases = [r for r in ranked if r.kind == "case"][:limit]
        strategies = [r for r in ranked if r.kind == "strategy"][:limit]

        # Prefer mutation procedure when mutation signal
        if "mutation" in signals:
            mut_procs = [
                r
                for r in self.index.records
                if r.kind == "procedure" and "mutation" in r.tags
            ]
            for mp in mut_procs:
                if mp not in procedures:
                    procedures.insert(0, mp)
            procedures = procedures[:limit]
            mut_pats = [
                r for r in self.index.records if r.kind == "pattern" and "mutation" in r.tags
            ]
            for mp in mut_pats:
                if mp not in patterns:
                    patterns.insert(0, mp)
            patterns = patterns[:limit]
        else:
            # ensure cross-identity procedure present when multi-identity object
            if "multi_identity" in signals and "object_surface" in signals:
                for r in self.index.records:
                    if r.kind == "procedure" and (
                        "cross" in r.record_id.lower()
                        or "cross-identity" in r.tags
                        or "ownership" in r.tags
                    ):
                        if r not in procedures:
                            procedures.insert(0, r)
                        break
                procedures = procedures[:limit]

        competing: list[str] = []
        for p in patterns + cases:
            for n in p.not_same_as:
                if n and n not in competing:
                    competing.append(n)
        # Always include core benign classes if we have authz hits
        if patterns or procedures:
            for base in (
                "Resource is intentionally public",
                "Resource is shared via ACL by design",
                "Role grants broader access than ownership",
            ):
                if base not in competing:
                    competing.append(base)

        prov = []
        for r in patterns + procedures + cases:
            prov.append(
                {
                    "record_id": r.record_id,
                    "kind": r.kind,
                    "path": r.path,
                    "loader": r.provenance.get("loader"),
                }
            )

        return RetrievalResult(
            query_signals=signals,
            patterns=patterns,
            procedures=procedures,
            cases=cases,
            strategies=strategies,
            competing_explanations=competing[:10],
            provenance=prov,
        )
