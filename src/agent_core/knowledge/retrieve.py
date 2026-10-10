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
        # Surface-tech alignment: when target exposes GraphQL/WS, prefer matching tags
        if sig in ("graphql", "websocket", "gql") and sig in tags:
            s += 2.5

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

    # --- Gate 2 research-state signals ---
    rid = rec.record_id.lower()
    blob = f"{rec.title} {rec.abstraction} {' '.join(rec.tags)} {rec.raw_excerpt}".lower()

    # Hypothesis tokens: boost knowledge that can discriminate current claims
    for tok in query.hypothesis_tokens or []:
        tl = tok.lower().strip()
        if len(tl) < 3:
            continue
        if tl in blob or tl in rid:
            s += 0.6

    # Evidence gaps: prefer procedures that mention missing roles/evidence
    for g in query.evidence_gaps or []:
        gl = str(g).lower()
        if gl and gl in blob:
            s += 0.5
        if gl.startswith("evidence_gap:"):
            gl = gl.split(":", 1)[-1]
        if gl and gl in blob:
            s += 0.4

    # Prior experiments: avoid recommending the same procedure again
    for eid in query.prior_experiment_ids or []:
        el = str(eid).lower()
        if el and (el in rid or el in blob):
            s -= 2.0

    # Negative evidence ids: boost negative-kind records that match
    for nid in query.negative_evidence_ids or []:
        if str(nid).lower() in rid:
            s += 1.0

    # Preconditions from target context (MATCH boost / MISMATCH soft penalty)
    preconds = list(query.precondition_hints or [])
    if query.actor_count >= 2:
        preconds.append("multiple identities")
        preconds.append("two identities")
        preconds.append("cross-identity")
    if query.has_object_id_param:
        preconds.append("object identifier")
        preconds.append("object id")
        preconds.append("resource id")

    matched_pre = 0
    for pre in preconds:
        pl = pre.lower()
        if pl in blob:
            matched_pre += 1
            s += 0.45
    # If procedure text requires multi-identity but actor_count < 2 → soft mismatch
    if query.actor_count < 2 and any(
        x in blob for x in ("cross-identity", "two identities", "multiple identities")
    ):
        if "public" not in blob:
            s -= 0.8

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

        # Prefer records matching tags_prefer, then re-rank by score.
        # (insert(0) in score-descending order would reverse rank — do not do that.)
        if query.tags_prefer:
            prefer = {t.lower() for t in query.tags_prefer}
            preferred_procs = [
                r
                for r in self.index.records
                if r.kind == "procedure" and prefer.intersection(t.lower() for t in r.tags)
            ]
            merged_procs = list(procedures)
            for p in preferred_procs:
                if p not in merged_procs:
                    merged_procs.append(p)
            merged_procs.sort(key=lambda r: _score_record(r, query), reverse=True)
            procedures = merged_procs[:limit]
            preferred_pats = [
                r
                for r in self.index.records
                if r.kind == "pattern" and prefer.intersection(t.lower() for t in r.tags)
            ]
            merged_pats = list(patterns)
            for p in preferred_pats:
                if p not in merged_pats:
                    merged_pats.append(p)
            merged_pats.sort(key=lambda r: _score_record(r, query), reverse=True)
            patterns = merged_pats[:limit]

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
            hypothesis_tokens=getattr(self, "_hypothesis_tokens", None),
            negative_evidence_ids=getattr(self, "_negative_evidence_ids", None),
            precondition_hints=getattr(self, "_precondition_hints", None),
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
    hypothesis_tokens: list[str] | None = None,
    negative_evidence_ids: list[str] | None = None,
    precondition_hints: list[str] | None = None,
    limit: int = 5,
) -> KnowledgeQuery:
    """Generic context query — methodology is data, not a separate engine."""
    from agent_core.knowledge.domains.authorization import build_authz_query

    meth = (methodology or "").lower().strip()

    actor_count = len(getattr(ctx, "actors", None) or [])
    has_obj = False
    for ep in getattr(ctx, "endpoints", None) or []:
        path = (getattr(ep, "path", "") or "").lower()
        if "{id}" in path or ":id" in path or "id}" in path:
            has_obj = True
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
        q.evidence_gaps = list(evidence_gaps or [])
        q.prior_experiment_ids = list(prior_experiment_ids or [])
        q.hypothesis_tokens = list(hypothesis_tokens or [])
        q.negative_evidence_ids = list(negative_evidence_ids or [])
        q.precondition_hints = list(precondition_hints or [])
        q.actor_count = actor_count
        q.has_object_id_param = has_obj
        return q

    # Data map — not per-methodology engines
    METHOD_SIGNALS = {
        "ssrf": (["ssrf", "url-fetch", "server-side"], ["ssrf"], "ssrf"),
        "business_logic": (["business_logic", "state", "workflow", "coupon"], ["business_logic", "state"], "business_logic"),
        "business-logic": (["business_logic", "state", "workflow", "coupon"], ["business_logic", "state"], "business_logic"),
        "authentication": (["authentication", "session"], ["authentication"], "authentication"),
        "authn": (["authentication", "session"], ["authentication"], "authentication"),
        "xss": (["xss", "reflection", "encoding"], ["xss"], "xss"),
        "injection": (["injection", "sqli", "interpreter"], ["injection"], "injection"),
    }
    if meth in METHOD_SIGNALS:
        extra_sig, extra_tags, prop = METHOD_SIGNALS[meth]
        signals = [meth] + list(extra_sig)
        tags = [meth] + list(extra_tags)
    else:
        signals = [meth]
        tags = [meth]
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
        evidence_gaps=list(evidence_gaps or []),
        prior_experiment_ids=list(prior_experiment_ids or []),
        hypothesis_tokens=list(hypothesis_tokens or []),
        negative_evidence_ids=list(negative_evidence_ids or []),
        precondition_hints=list(precondition_hints or []),
        actor_count=actor_count,
        has_object_id_param=has_obj,
    )

