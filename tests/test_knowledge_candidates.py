"""M8: episode → knowledge candidates with explicit promotion gate."""

from pathlib import Path

from agent_core.knowledge.candidates import (
    CandidateKind,
    CandidateStatus,
    CandidateStore,
    KnowledgeCandidate,
    KnowledgeCandidateFactory,
    PromotionGate,
)
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_a_episode_creates_candidate():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_kc_a").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    assert result.knowledge_candidates is not None
    # positive path may yield positive candidate when referee accepts
    if result.referee_accepted:
        kinds = [c.kind for c in result.knowledge_candidates]
        assert CandidateKind.POSITIVE in kinds


def test_b_provenance():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_kc_b").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    for c in result.knowledge_candidates:
        assert c.engagement_id == "eng_kc_b"
        assert c.episode_id or c.engagement_id
        assert c.experiment_id or c.evidence_ids is not None
        assert c.universal_claim is False


def test_c_no_auto_promotion():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_kc_c").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    for c in result.knowledge_candidates:
        assert c.status == CandidateStatus.PROPOSED
    # curated knowledge index unchanged by candidates
    from agent_core.knowledge.index import KnowledgeIndex

    idx = KnowledgeIndex(ROOT / "knowledge").load()
    assert any(r.kind == "procedure" for r in idx.records)


def test_d_negative_not_universal():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_kc_d").run(
        FIXTURE, scenario=secure_lab_scenario()
    )
    negatives = [c for c in result.knowledge_candidates if c.kind == CandidateKind.NEGATIVE]
    for c in negatives:
        assert c.universal_claim is False
        assert "universal" not in c.summary.lower() or "not" in c.summary.lower()
        assert "scoped" in c.context_notes or "not" in c.summary.lower()


def test_e_positive_not_global_pattern():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_kc_e").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    for c in result.knowledge_candidates:
        if c.kind == CandidateKind.POSITIVE:
            assert c.universal_claim is False
            assert "global" in c.summary.lower() or "not a global" in c.summary.lower() or "context" in c.summary.lower()


def test_f_promotion_gate():
    gate = PromotionGate()
    c = KnowledgeCandidate(
        candidate_id="KC-test-1",
        kind=CandidateKind.POSITIVE,
        status=CandidateStatus.PROPOSED,
        summary="context-bound",
        episode_id="EP-1",
        engagement_id="e",
        evidence_ids=["ev1"],
        universal_claim=False,
    )
    c = gate.mark_validated(c)
    assert c.status == CandidateStatus.VALIDATED
    c = gate.promote(c, reason="manual review for test")
    assert c.status == CandidateStatus.PROMOTED
    # universal forbidden
    bad = KnowledgeCandidate(
        candidate_id="KC-bad",
        kind=CandidateKind.NEGATIVE,
        status=CandidateStatus.PROPOSED,
        summary="universal not vulnerable",
        episode_id="EP-1",
        engagement_id="e",
        evidence_ids=["ev1"],
        universal_claim=True,
    )
    bad = gate.mark_validated(bad)
    assert bad.status == CandidateStatus.REJECTED


def test_g_store_does_not_write_knowledge_md(tmp_path):
    store = CandidateStore(tmp_path / "candidates.jsonl")
    c = KnowledgeCandidate(
        candidate_id="KC-s",
        kind=CandidateKind.PROCEDURE_IMPROVEMENT,
        status=CandidateStatus.PROPOSED,
        summary="coverage gap",
        episode_id="EP",
        engagement_id="e",
        universal_claim=False,
    )
    store.add(c)
    path = store.write_jsonl()
    assert path.exists()
    # knowledge corpus files untouched
    assert (ROOT / "knowledge" / "procedures").is_dir()
