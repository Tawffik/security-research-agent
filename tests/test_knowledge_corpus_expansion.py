"""Curated knowledge expansion: loadable, multi-domain, no thin-only corpus."""

from collections import Counter
from pathlib import Path

from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_corpus_has_multiple_domains():
    idx = KnowledgeIndex(ROOT).load()
    domains = Counter(r.domain for r in idx.records)
    assert len(idx.records) >= 55
    for d in ("authorization", "ssrf", "xss", "authentication", "injection", "business_logic"):
        assert domains.get(d, 0) >= 1, f"missing domain {d}: {domains}"


def test_quality_pack_ids_present():
    idx = KnowledgeIndex(ROOT).load()
    ids = {r.record_id.upper() for r in idx.records}
    for rid in (
        "CASE-0010",
        "CASE-0013",
        "CASE-0016",
        "CASE-0017",
        "CASE-0018",
        "CASE-0019",
        "CASE-0020",
        "NEG-0005",
        "NEG-0007",
        "PROC-0018",
        "PAT-0016",
    ):
        assert rid in ids or any(rid in i for i in ids), rid


def test_cases_carry_falsification_or_decisive_language():
    """Quality bar: cases should teach how to disprove, not only claim."""
    idx = KnowledgeIndex(ROOT).load()
    cases = [r for r in idx.records if r.kind == "case"]
    strong = 0
    for c in cases:
        text = (c.raw_excerpt or "").lower()
        if any(k in text for k in ("falsif", "decisive experiment", "not the same", "alternatives")):
            strong += 1
    assert strong >= max(8, len(cases) // 2)


def test_authz_and_injection_retrieval_separated():
    idx = KnowledgeIndex(ROOT).load()
    ret = KnowledgeRetriever(index=idx)
    inj = ret.retrieve(
        KnowledgeQuery(domain="injection", kinds=["pattern", "procedure", "case"], limit=10)
    )
    auth = ret.retrieve(
        KnowledgeQuery(domain="authorization", kinds=["pattern", "procedure"], limit=10)
    )
    assert inj.patterns or inj.procedures or inj.cases
    assert auth.patterns or auth.procedures
