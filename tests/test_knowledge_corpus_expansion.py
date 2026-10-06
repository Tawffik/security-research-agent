
"""Curated knowledge: BOLA-quality multi-domain corpus + retrieval smoke."""

from collections import Counter
from pathlib import Path

from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_corpus_scale_and_domains():
    idx = KnowledgeIndex(ROOT).load()
    domains = Counter(r.domain for r in idx.records)
    assert len(idx.records) >= 90
    for d in (
        "authorization",
        "ssrf",
        "xss",
        "authentication",
        "injection",
        "business_logic",
        "cache",
        "deserialization",
        "upload",
        "traversal",
    ):
        assert domains.get(d, 0) >= 1, f"missing {d}: {domains}"


def test_bola_depth_ids_and_function_level():
    ids = {r.record_id.upper() for r in KnowledgeIndex(ROOT).load().records}
    for rid in (
        "CASE-0001",
        "CASE-0006",
        "PROC-0001",
        "PAT-0001",
        "CASE-0029",
        "PROC-0029",
        "CASE-0030",
        "NEG-0011",
        "STRAT-0003",
        "CASE-0032",
    ):
        assert rid in ids or any(rid in i for i in ids), rid


def test_cases_meet_bola_language_bar():
    cases = [r for r in KnowledgeIndex(ROOT).load().records if r.kind == "case"]
    strong = 0
    for c in cases:
        text = (c.raw_excerpt or "").lower()
        if sum(
            1
            for k in (
                "security property",
                "hypothesis",
                "evidence",
                "falsif",
                "disproof",
                "alternatives",
                "decisive experiment",
                "actors",
            )
            if k in text
        ) >= 3:
            strong += 1
    assert strong >= max(15, int(0.6 * len(cases))), (strong, len(cases))


def test_authz_retrieval_surfaces_bola_procedures():
    idx = KnowledgeIndex(ROOT).load()
    ret = KnowledgeRetriever(index=idx)
    r = ret.retrieve(
        KnowledgeQuery(
            domain="authorization",
            kinds=["procedure", "pattern", "case"],
            signals=["ownership", "object", "identity"],
            limit=15,
        )
    )
    blob = " ".join(
        [
            (x.record_id or "") + " " + (x.raw_excerpt or "")[:120]
            for x in (r.procedures + r.patterns + r.cases)
        ]
    ).lower()
    assert r.procedures or r.patterns
    assert "owner" in blob or "object" in blob or "auth" in blob
