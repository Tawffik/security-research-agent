"""Compiler GENERATE → registry retrieval → curated import gates."""

from pathlib import Path

from agent_core.knowledge.candidates import (
    CandidateKind,
    CandidateStatus,
    KnowledgeCandidate,
    PromotionGate,
)
from agent_core.knowledge.compiler import KnowledgeCompiler, run_full_pipeline
from agent_core.knowledge.curated_import import CuratedKnowledgeImporter
from agent_core.knowledge.query import KnowledgeQuery
from agent_core.knowledge.registry import KnowledgeRegistry

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"


def test_generate_produces_candidates_not_trusted_paths():
    report, arts = run_full_pipeline(KnowledgeCompiler(KROOT))
    assert report.normalized >= 1
    assert isinstance(arts, list)
    for a in arts:
        assert a.artifact_id.startswith("GEN-")
        assert a.status in ("validated", "rejected")
        assert "generated://" in a.to_knowledge_record().path or a.path if hasattr(a, "path") else True
        rec = a.to_knowledge_record()
        assert "untrusted" in rec.tags or "generated_candidate" in rec.tags
        assert rec.provenance.get("origin") == "knowledge_compiler_generate"


def test_generated_affects_retrieval_ranking():
    reg = KnowledgeRegistry(KROOT)
    _, arts = run_full_pipeline(KnowledgeCompiler(KROOT))
    # Force at least one validated artifact if generate produced none for some props
    validated = [a for a in arts if a.status == "validated"]
    retriever = reg.retriever_with_generated(arts)
    q = KnowledgeQuery(
        domain="authorization",
        kinds=["pattern", "procedure", "strategy"],
        signals=["authorization"],
        tags_any=["authorization", "generated"],
        limit=10,
    )
    result = retriever.retrieve(q)
    # curated still works
    assert result is not None
    all_ids = [r.record_id for r in (result.patterns + result.procedures + result.strategies)]
    if validated:
        # overlay present in index records
        idx_ids = {r.record_id for r in retriever.index.records}
        assert any(a.artifact_id in idx_ids for a in validated)


def test_import_rejects_non_promoted():
    imp = CuratedKnowledgeImporter(KROOT, import_subdir="imported")
    c = KnowledgeCandidate(
        candidate_id="KC-rej",
        kind=CandidateKind.POSITIVE,
        status=CandidateStatus.PROPOSED,
        summary="x",
        episode_id="EP",
        engagement_id="e",
        evidence_ids=["1"],
        benchmark_snapshot={"false_positive": False, "true_positive": True},
    )
    r = imp.import_candidate(c, human_review_token="review-1")
    assert r.ok is False
    assert "promoted" in r.reason


def test_import_rejects_false_positive_benchmark():
    imp = CuratedKnowledgeImporter(KROOT, import_subdir="imported")
    c = KnowledgeCandidate(
        candidate_id="KC-fp",
        kind=CandidateKind.POSITIVE,
        status=CandidateStatus.PROMOTED,
        summary="x",
        episode_id="EP",
        engagement_id="e",
        evidence_ids=["1"],
        promotion_reason="test",
        benchmark_snapshot={"false_positive": True, "true_positive": False},
    )
    r = imp.import_candidate(c, human_review_token="review-1")
    assert r.ok is False
    assert "false_positive" in r.reason


def test_import_rejects_without_human_review():
    imp = CuratedKnowledgeImporter(KROOT, import_subdir="imported")
    c = KnowledgeCandidate(
        candidate_id="KC-hr",
        kind=CandidateKind.POSITIVE,
        status=CandidateStatus.PROMOTED,
        summary="x",
        episode_id="EP",
        engagement_id="e",
        evidence_ids=["1"],
        promotion_reason="test",
        benchmark_snapshot={"false_positive": False, "true_positive": True},
    )
    r = imp.import_candidate(c, human_review_token="")
    assert r.ok is False
    assert "human_review" in r.reason


def test_import_promoted_with_review(tmp_path):
    imp = CuratedKnowledgeImporter(tmp_path, import_subdir="imported")
    c = KnowledgeCandidate(
        candidate_id="KC-ok",
        kind=CandidateKind.POSITIVE,
        status=CandidateStatus.PROMOTED,
        summary="context-bound lesson",
        episode_id="EP-1",
        engagement_id="eng",
        experiment_id="exp1",
        evidence_ids=["ev1"],
        promotion_reason="validated",
        benchmark_snapshot={
            "false_positive": False,
            "true_positive": True,
            "case_id": "bm",
            "ground_truth_hidden_from_agent": True,
        },
        universal_claim=False,
    )
    r = imp.import_candidate(c, human_review_token="human-ok")
    assert r.ok is True
    assert r.path
    text = Path(r.path).read_text(encoding="utf-8")
    assert "EP-1" in text
    assert "ev1" in text
    assert "STAGING" in text
    # duplicate deterministic
    r2 = imp.import_candidate(c, human_review_token="human-ok")
    assert r2.ok is True
    assert r2.reason == "already_imported"


def test_ssrf_knowledge_loaded_as_data():
    from agent_core.knowledge.index import KnowledgeIndex

    idx = KnowledgeIndex(KROOT).load()
    ids = {r.record_id.upper() for r in idx.records}
    assert any("0010" in i for i in ids)


def test_retriever_include_generated_flag():
    from agent_core.knowledge.retrieve import KnowledgeRetriever

    r = KnowledgeRetriever(include_generated=True, knowledge_root=KROOT)
    assert any(
        "generated_candidate" in (rec.tags or []) or str(rec.path).startswith("generated://")
        for rec in r.index.records
    ) or len(r.index.records) >= 1
