
"""Curated knowledge: multi-domain quality corpus."""

from collections import Counter
from pathlib import Path

from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_corpus_scale_and_domains():
    idx = KnowledgeIndex(ROOT).load()
    domains = Counter(r.domain for r in idx.records)
    assert len(idx.records) >= 80
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


def test_new_pack_ids_present():
    ids = {r.record_id.upper() for r in KnowledgeIndex(ROOT).load().records}
    for rid in (
        "CASE-0021",
        "CASE-0022",
        "CASE-0023",
        "CASE-0024",
        "CASE-0025",
        "CASE-0026",
        "CASE-0027",
        "CASE-0028",
        "NEG-0009",
        "NEG-0010",
        "PAT-0021",
        "PROC-0024",
    ):
        assert rid in ids or any(rid in i for i in ids), rid


def test_cases_teach_falsification():
    cases = [r for r in KnowledgeIndex(ROOT).load().records if r.kind == "case"]
    strong = sum(
        1
        for c in cases
        if any(
            k in (c.raw_excerpt or "").lower()
            for k in ("falsif", "decisive experiment", "not the same", "alternatives")
        )
    )
    assert strong >= max(12, len(cases) // 2)


def test_domain_retrieval_smoke():
    idx = KnowledgeIndex(ROOT).load()
    ret = KnowledgeRetriever(index=idx)
    for domain in ("cache", "deserialization", "injection", "authorization"):
        r = ret.retrieve(KnowledgeQuery(domain=domain, kinds=["pattern", "case", "procedure"], limit=8))
        assert r.patterns or r.cases or r.procedures, domain
