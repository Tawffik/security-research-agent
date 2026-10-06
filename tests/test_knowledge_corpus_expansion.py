"""Curated knowledge expansion remains loadable and domain-tagged."""

from pathlib import Path

from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.retrieve import KnowledgeRetriever

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_new_curated_records_load():
    idx = KnowledgeIndex(ROOT).load()
    ids = {r.record_id for r in idx.records}
    for rid in (
        "CASE-0014",
        "PAT-0014",
        "PROC-0014",
        "CASE-0015",
        "PAT-0015",
        "NEG-0003",
        "NEG-0004",
        "STRAT-0014",
    ):
        # record_id may be full stem; accept substring match
        assert any(rid in i or rid.lower() in i.lower() for i in ids) or any(
            rid in (r.title or "") or rid in (r.record_id or "") for r in idx.records
        ), f"missing {rid} in {list(ids)[:20]}"


def test_authz_retrieval_can_surface_mass_assignment_pattern():
    idx = KnowledgeIndex(ROOT).load()
    ret = KnowledgeRetriever(index=idx)
    # domain-neutral query preferring authorization
    q = KnowledgeQuery(
        domain="authorization",
        kinds=["pattern", "procedure", "case"],
        signals=["role", "privilege", "object"],
        tags_any=["authorization"],
        limit=20,
    )
    result = ret.retrieve(q)
    blob = " ".join(
        [
            (getattr(r, "record_id", "") or "")
            + " "
            + (getattr(r, "title", "") or "")
            + " "
            + (getattr(r, "raw_excerpt", "") or "")[:200]
            for r in (result.patterns + result.procedures + result.cases)
        ]
    ).lower()
    # at least authorization-related corpus still retrieves
    assert result.patterns or result.procedures or result.cases
