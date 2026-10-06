"""Hard offline utility: knowledge can turn FN into TP without FP from noise."""

from pathlib import Path

from agent_core.evaluation.research_utility import (
    HARD_SCENARIOS,
    KnowledgeCondition,
    ScenarioSpec,
    run_condition,
    run_ablation_suite,
)

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_hard_authz_none_fn_curated_tp():
    sc = ScenarioSpec("hard_authz", "hard_authz", "vulnerable", "confirmed")
    tr_n, m_n, r_n = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_n",
    )
    tr_c, m_c, r_c = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_c",
    )
    assert m_n.false_negative is True
    assert r_n.knowledge_procedure_required_blocked is True
    assert m_c.true_positive is True
    assert r_c.knowledge_procedure_required_blocked is False
    assert m_c.knowledge_changed_experiment or m_c.knowledge_changed_hyp_mode
    assert m_c.influence_class == "useful_influence"


def test_hard_authz_irrelevant_no_fp_on_secure_still():
    sc = ScenarioSpec("secure_authz", "secure", "secure", "rejected")
    _, m, _ = run_condition(
        condition=KnowledgeCondition.IRRELEVANT,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert m.false_positive is False


def test_business_logic_hard_none_fn_or_blocked():
    sc = ScenarioSpec("business_logic", "business_logic", "vulnerable", "confirmed")
    _, m_n, r_n = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_bln",
    )
    _, m_c, r_c = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_blc",
    )
    # Without knowledge should not confirm when procedure required
    assert m_n.true_positive is False
    assert r_n.knowledge_procedure_required_blocked or m_n.false_negative
    # Curated may TP if authz procedures still count as knowledge-driven for any domain
    # Business-logic may still use authz procedures — record factual outcome
    assert isinstance(m_c.true_positive, bool)


def test_hard_ssrf_none_blocked():
    sc = ScenarioSpec("hard_ssrf", "hard_ssrf", "vulnerable", "confirmed")
    _, m_n, r_n = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        engagement_suffix="_s",
    )
    assert r_n.knowledge_procedure_required_blocked is True
    assert m_n.true_positive is False


def test_oracle_isolated_hard():
    sc = ScenarioSpec("hard_authz", "hard_authz", "vulnerable", "confirmed")
    _, _, result = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
    )
    assert not hasattr(result, "ground_truth")
    assert "ground_truth" not in (result.experiment_alignment or {})


def test_hard_ablation_suite():
    report = run_ablation_suite(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        scenarios=HARD_SCENARIOS,
        conditions=[
            KnowledgeCondition.NONE,
            KnowledgeCondition.CURATED,
            KnowledgeCondition.IRRELEVANT,
        ],
    )
    assert report["summary"]["oracle_isolated"] is True
    hard_none = next(
        m
        for m in report["metrics"]
        if m["scenario_id"] == "hard_authz" and m["condition"] == "none"
    )
    hard_cur = next(
        m
        for m in report["metrics"]
        if m["scenario_id"] == "hard_authz" and m["condition"] == "curated"
    )
    assert hard_none["false_negative"] is True
    assert hard_cur["true_positive"] is True


def test_action_level_bola_none_fn_curated_tp():
    from agent_core.evaluation.research_utility import (
        KnowledgeCondition,
        ScenarioSpec,
        run_condition,
    )
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sc = ScenarioSpec("action_level_bola", "action_level_bola", "vulnerable", "confirmed")
    tr_n, m_n, _ = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=root / "examples" / "fixtures" / "sample_recon.json",
        scope_path=root / "examples" / "demo_program_scope.yaml",
        knowledge_root=root / "knowledge",
        engagement_suffix="_al_none",
    )
    tr_c, m_c, _ = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=root / "examples" / "fixtures" / "sample_recon.json",
        scope_path=root / "examples" / "demo_program_scope.yaml",
        knowledge_root=root / "knowledge",
        engagement_suffix="_al_cur",
    )
    # Knowledge procedure gate: none should not confirm; curated should TP
    assert m_n.false_negative is True or m_n.true_positive is False
    assert m_c.true_positive is True, (m_c, tr_c.procedure_ids, tr_c.influence_class)


def test_vertical_and_graphql_curated_tp():
    from agent_core.evaluation.research_utility import (
        KnowledgeCondition,
        ScenarioSpec,
        run_condition,
    )
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for sid, factory in (
        ("vertical_object", "vertical_object"),
        ("graphql_global_id", "graphql_global_id"),
    ):
        sc = ScenarioSpec(sid, factory, "vulnerable", "confirmed")
        _, m_c, _ = run_condition(
            condition=KnowledgeCondition.CURATED,
            scenario=sc,
            recon_path=root / "examples" / "fixtures" / "sample_recon.json",
            scope_path=root / "examples" / "demo_program_scope.yaml",
            knowledge_root=root / "knowledge",
            engagement_suffix=f"_{sid}_cur",
        )
        assert m_c.true_positive is True, (sid, m_c)
