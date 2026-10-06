"""Multi-class curated knowledge at BOLA quality bar."""

from collections import Counter
from pathlib import Path

from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever

ROOT = Path(__file__).resolve().parents[1] / "knowledge"

REQUIRED_DOMAINS = (
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
    "smuggling",
    "ui_security",
)


def test_corpus_scale_multi_domain():
    idx = KnowledgeIndex(ROOT).load()
    domains = Counter(r.domain for r in idx.records)
    assert len(idx.records) >= 110, len(idx.records)
    for d in REQUIRED_DOMAINS:
        assert domains.get(d, 0) >= 1, f"missing {d}: {domains}"


def test_bola_family_and_cross_class_ids():
    ids = {r.record_id.upper() for r in KnowledgeIndex(ROOT).load().records}
    for rid in (
        "CASE-0001",
        "CASE-0033",
        "CASE-0034",
        "CASE-0035",
        "PROC-0033",
        "CASE-0036",
        "CASE-0037",
        "CASE-0038",
        "CASE-0039",
        "CASE-0040",
        "STRAT-0100",
        "STRAT-0033",
    ):
        assert rid in ids or any(rid in i for i in ids), rid


def test_cases_quality_language():
    cases = [r for r in KnowledgeIndex(ROOT).load().records if r.kind == "case"]
    strong = sum(
        1
        for c in cases
        if sum(
            1
            for k in (
                "security property",
                "hypothesis",
                "evidence",
                "disproof",
                "falsif",
                "actors",
                "minimum",
            )
            if k in (c.raw_excerpt or "").lower()
        )
        >= 3
    )
    assert strong >= max(18, int(0.5 * len(cases))), (strong, len(cases))


def test_retrieval_smoke_several_domains():
    idx = KnowledgeIndex(ROOT).load()
    ret = KnowledgeRetriever(index=idx)
    for domain in ("authorization", "injection", "smuggling", "ssrf"):
        r = ret.retrieve(
            KnowledgeQuery(domain=domain, kinds=["pattern", "procedure", "case"], limit=8)
        )
        assert r.patterns or r.procedures or r.cases, domain
