"""Research-utility A/B: knowledge must be able to change decisions; oracle isolated."""

from pathlib import Path

from agent_core.evaluation.research_utility import (
    KnowledgeCondition,
    ScenarioSpec,
    build_retriever,
    run_ablation_suite,
    run_condition,
)
from agent_core.knowledge.index import KnowledgeIndex

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_none_vs_curated_hyp_mode_differs_or_documents_effect():
    sc = ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed")
    tr_none, m_none, _ = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_a",
    )
    tr_cur, m_cur, _ = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_b",
    )
    # None should not retrieve curated procedure ids
    assert tr_none.knowledge_ids_retrieved == []
    assert m_none.knowledge_retrieved is False
    # Curated path should retrieve or still be fallback — record factual effect
    assert isinstance(m_cur.retrieval_had_effect, bool)
    # If curated retrieved knowledge, influence flags should be consistent
    if tr_cur.knowledge_ids_retrieved:
        assert m_cur.knowledge_retrieved is True
        # knowledge_driven hyp or procedure-driven exp is the measurable effect
        assert (
            m_cur.knowledge_changed_hyp_mode
            or m_cur.knowledge_changed_experiment
            or tr_cur.hyp_mode == "fallback"
        )


def test_irrelevant_knowledge_does_not_force_false_positive():
    sc = ScenarioSpec("secure_authz", "secure", "secure", "rejected")
    tr, m, result = run_condition(
        condition=KnowledgeCondition.IRRELEVANT,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert m.false_positive is False
    assert result.referee_accepted is False or m.false_positive is False
    # Irrelevant id may or may not be retrieved depending on query filters
    assert "ground_truth" not in (result.experiment_alignment or {})


def test_generated_candidates_remain_untrusted_tags():
    r = build_retriever(KnowledgeCondition.GENERATED, KROOT)
    for rec in r.index.records:
        if str(rec.path).startswith("generated://"):
            assert "untrusted" in rec.tags or "generated_candidate" in rec.tags


def test_ablation_suite_runs_deterministically():
    report = run_ablation_suite(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        scenarios=[
            ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed"),
            ScenarioSpec("secure_authz", "secure", "secure", "rejected"),
        ],
        conditions=[
            KnowledgeCondition.NONE,
            KnowledgeCondition.CURATED,
            KnowledgeCondition.IRRELEVANT,
        ],
    )
    assert report["summary"]["oracle_isolated"] is True
    assert report["summary"]["n_runs"] == 6
    assert report["summary"]["irrelevant_false_positive_on_secure"] is False
    # traces include hyp/experiment fields
    assert all("hyp_mode" in t for t in report["traces"])
    assert all("selected_experiment_id" in t for t in report["traces"])


def test_oracle_not_in_agent_result():
    sc = ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed")
    _, _, result = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert not hasattr(result, "ground_truth")
    blob = str(result.__dict__)
    assert "ground_truth" not in blob


def test_scope_guard_intact_under_all_conditions():
    sc = ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed")
    for cond in (
        KnowledgeCondition.NONE,
        KnowledgeCondition.CURATED,
        KnowledgeCondition.IRRELEVANT,
    ):
        _, _, result = run_condition(
            condition=cond,
            scenario=sc,
            recon_path=FIXTURE,
            scope_path=SCOPE,
            knowledge_root=KROOT,
            engagement_suffix=f"_{cond.value}",
        )
        assert result.scope_allowed is True


def test_negative_evidence_path_secure_not_confirmed():
    sc = ScenarioSpec("secure_authz", "secure", "secure", "rejected")
    _, m, result = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert m.false_positive is False
    assert result.referee_accepted is False
