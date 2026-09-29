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
    tips: list[KnowledgeRecord] = field(default_factory=list)
    negatives: list[KnowledgeRecord] = field(default_factory=list)
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
            "tip_ids": [x.record_id for x in self.tips],
            "negative_ids": [x.record_id for x in self.negatives],
            "competing_explanations": self.competing_explanations,
            "provenance": self.provenance,
        }


def _alignment(rec_value: str, preferred: list[str]) -> str:
    """Return MATCH | MISMATCH | UNKNOWN for a field vs preferred list."""
    rv = (rec_value or "").lower().strip()
    prefs = [p.lower().strip() for p in preferred if p]
    if not prefs:
        return "UNKNOWN"
    if not rv or rv in ("unknown", ""):
        return "UNKNOWN"
    if rv in prefs:
        return "MATCH"
    # soft synonym map (data-driven-ish, still generic)
    synonyms = {
        "authorization": {"authz", "bola", "idor", "object-level"},
        "ssrf": {"server-side-request", "server_side_request"},
        "business_logic": {"business-logic", "workflow", "state"},
        "authentication": {"authn", "session"},
        "xss": {"cross-site-scripting"},
        "injection": {"sqli", "command-injection"},
    }
    for pref in prefs:
        if rv == pref:
            return "MATCH"
        alts = synonyms.get(pref, set()) | {pref}
        if rv in alts or any(a in rv for a in alts):
            return "MATCH"
        # reverse: record domain in preferred synonym set
        for k, vals in synonyms.items():
            if pref in vals or pref == k:
                if rv == k or rv in vals:
                    return "MATCH"
    return "MISMATCH"


def score_alignment_breakdown(rec: KnowledgeRecord, query: KnowledgeQuery) -> dict[str, str]:
    preferred = list(query.methodologies or []) + list(query.security_properties or [])
    if query.domain:
        preferred = preferred + [query.domain]
    # dedupe preserve order
    seen = set()
    prefs = []
    for p in preferred:
        if p.lower() not in seen:
            seen.add(p.lower())
            prefs.append(p)
    return {
        "methodology": _alignment(rec.domain or "", prefs),
        "property": _alignment(rec.security_property or "", prefs),
        "domain": _alignment(rec.domain or "", [query.domain] if query.domain else []),
    }


def _score_record(rec: KnowledgeRecord, query: KnowledgeQuery) -> float:
    """Domain-neutral score with methodology alignment as first-class signal."""
    s = 0.0
    tags = set(t.lower() for t in rec.tags)
    domain = (rec.domain or "").lower()
    q_domain = (query.domain or "").lower()

    preferred = list(query.methodologies or []) + list(query.security_properties or [])
    if q_domain:
        preferred.append(q_domain)

    meth_align = _alignment(domain, preferred)
    prop_align = _alignment(rec.security_property or "", preferred)

    if query.require_methodology_match and preferred:
        if meth_align == "MISMATCH" and prop_align == "MISMATCH":
            return -1.0

    if query.require_domain_match and q_domain:
        if domain != q_domain:
            return -1.0
        s += 2.0
    elif q_domain and domain == q_domain:
        s += 1.5
    elif q_domain and domain and domain != q_domain and domain not in ("unknown", ""):
        s -= 0.5

    # Methodology alignment weights (stronger than generic tag hits)
    if meth_align == "MATCH":
        s += 4.0
    elif meth_align == "MISMATCH":
        s -= 3.0
    # UNKNOWN: no large bonus/penalty

    if prop_align == "MATCH":
        s += 2.5
    elif prop_align == "MISMATCH":
        s -= 1.5

    tags_any = [t.lower() for t in query.tags_any]
    tags_prefer = [t.lower() for t in query.tags_prefer]
    signals = [x.lower() for x in query.signals]

    for tg in tags_any:
        if tg in tags:
            s += 1.0
    for tg in tags_prefer:
        if tg in tags:
            s += 2.0

    for sig in signals:
        if sig in tags:
            s += 1.2
        rid = rec.record_id.lower()
        if sig and sig in rid:
            s += 0.4
        # methodology token in signal
        if sig and (sig in domain or sig in (rec.security_property or "").lower()):
            s += 0.8

    for prop in query.security_properties:
        pl = prop.lower()
        if pl and pl in (rec.security_property or "").lower():
            s += 0.8
        if pl and pl in (rec.abstraction or "").lower():
            s += 0.3

    if query.kinds and rec.kind in query.kinds:
        idx = query.kinds.index(rec.kind)
        s += max(0.0, 1.0 - 0.15 * idx)
    elif query.kinds:
        return -1.0

    if rec.experiment_steps:
        s += 0.3
    if rec.evidence_required:
        s += 0.2
    if rec.kind == "tip":
        s += 0.15  # heuristic only — never outranks strong procedure alone
    if rec.kind == "negative":
        s += 0.25  # FP guidance is valuable when domain matches

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
        tips = take("tip")
        negatives = take("negative")

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
            tips=tips,
            negatives=negatives,
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
        return self.retrieve_for_context(
            ctx, opportunities, methodology="authorization", limit=limit
        )

    def retrieve_for_context(
        self,
        ctx: TargetContext,
        opportunities: list[Opportunity],
        *,
        methodology: str | None = None,
        limit: int = 5,
    ) -> RetrievalResult:
        query = build_contextual_query(
            ctx,
            opportunities,
            methodology=methodology,
            evidence_gaps=getattr(self, "_evidence_gaps", None),
            prior_experiment_ids=getattr(self, "_prior_experiment_ids", None),
            limit=limit,
        )
        return self.retrieve(query)


def build_contextual_query(
    ctx: TargetContext,
    opportunities: list,
    *,
    methodology: str | None = None,
    evidence_gaps: list[str] | None = None,
    prior_experiment_ids: list[str] | None = None,
    limit: int = 5,
) -> KnowledgeQuery:
    """Generic context query — methodology is data, not a separate engine."""
    from agent_core.knowledge.domains.authorization import build_authz_query

    meth = (methodology or "").lower().strip()
    if not meth or meth in ("authorization", "authz", "bola", "idor"):
        q = build_authz_query(ctx, opportunities, limit=limit)
        q.methodologies = ["authorization"]
        q.security_properties = list(dict.fromkeys(
            (q.security_properties or []) + ["authorization"]
        ))
        for g in evidence_gaps or []:
            q.signals.append(f"evidence_gap:{g}")
            q.tags_prefer.append(g)
        for eid in prior_experiment_ids or []:
            q.signals.append(f"prior_experiment:{eid}")
        return q

    signals = [meth]
    tags = [meth]
    if meth == "ssrf":
        signals += ["ssrf", "url-fetch", "server-side"]
        tags += ["ssrf"]
        prop = "ssrf"
    elif meth in ("business_logic", "business-logic"):
        signals += ["business_logic", "state", "workflow", "coupon"]
        tags += ["business_logic", "state"]
        prop = "business_logic"
    elif meth in ("authentication", "authn"):
        signals += ["authentication", "session"]
        tags += ["authentication"]
        prop = "authentication"
    elif meth == "xss":
        signals += ["xss"]
        tags += ["xss"]
        prop = "xss"
    else:
        signals += [meth]
        tags += [meth]
        prop = meth

    # light tech from context
    for tech in getattr(ctx, "technologies", None) or []:
        signals.append(str(tech).lower())

    for g in evidence_gaps or []:
        signals.append(f"evidence_gap:{g}")
        tags.append(g)
    for eid in prior_experiment_ids or []:
        signals.append(f"prior_experiment:{eid}")
    return KnowledgeQuery(
        domain=meth if meth else None,
        methodologies=[meth],
        security_properties=[prop],
        kinds=["pattern", "procedure", "case", "strategy", "tip", "negative"],
        signals=signals,
        tags_any=tags,
        tags_prefer=tags,
        limit=limit,
        require_domain_match=False,
        require_methodology_match=False,
    )

