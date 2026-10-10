"""Skill → ResearchLoop integration: selection, influence, safety, A/B utility."""

from pathlib import Path

from agent_core.evaluation.research_utility import (
    KnowledgeCondition,
    ScenarioSpec,
    run_condition,
)
from agent_core.skills.advisor import SkillDecisionAdvisor, _extract_skeptic_prompts

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"
SKILLS = ROOT / "skills"


def test_skill_advisor_selects_authz_for_idor_methodology():
    adv = SkillDecisionAdvisor(skills_dir=SKILLS)
    advice = adv.advise(methodology="authorization", technologies=["api"])
    assert "authz-idor-analysis" in advice.selected
    assert advice.evidence_requirements
    assert advice.influenced is True
    assert any(c.startswith("skill:authz-idor-analysis:") for c in advice.competing_explanations)


def test_skill_body_skeptic_prompts_extractable():
    body = (SKILLS / "authz-idor-analysis" / "SKILL.md").read_text()
    prompts = _extract_skeptic_prompts(body)
    assert len(prompts) >= 1


def test_skills_alone_do_not_create_false_positive_on_secure():
    sc = ScenarioSpec("secure_authz", "secure", "secure", "rejected")
    tr, m, result = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=True,
        engagement_suffix="_sec",
    )
    assert m.false_positive is False
    assert result.referee_accepted is False
    assert tr.skill_selected  # skill selected even without knowledge
    assert tr.skill_influenced is True


def test_skills_alone_do_not_flip_hard_authz_to_tp():
    """Skills inject policy; they do not replace curated procedures."""
    sc = ScenarioSpec("hard_authz", "hard_authz", "vulnerable", "confirmed")
    tr, m, _ = run_condition(
        condition=KnowledgeCondition.NONE,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=True,
        engagement_suffix="_hard",
    )
    # Without knowledge, hard scenario remains FN (skill is not a substitute)
    assert m.false_negative is True or m.true_positive is False
    assert tr.skill_selected


def test_knowledge_plus_skills_preserves_tp_and_records_skill_influence():
    sc = ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed")
    tr, m, _ = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=True,
        engagement_suffix="_combo",
    )
    assert m.true_positive is True
    assert tr.skill_selected
    assert tr.skill_influenced is True
    assert tr.skill_competing_count >= 1


def test_knowledge_without_skills_still_tp_baseline():
    sc = ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed")
    tr, m, _ = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=sc,
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=False,
        engagement_suffix="_base",
    )
    assert m.true_positive is True
    assert tr.skill_selected == []
    assert tr.skill_influenced is False


def test_skills_do_not_bypass_secure_or_public_rejection():
    for sid, factory, gt in [
        ("secure_authz", "secure", "secure"),
        ("public_res", "public", "public"),
    ]:
        sc = ScenarioSpec(sid, factory, gt, "rejected")
        tr, m, result = run_condition(
            condition=KnowledgeCondition.CURATED,
            scenario=sc,
            recon_path=FIXTURE,
            scope_path=SCOPE,
            knowledge_root=KROOT,
            enable_skills=True,
            engagement_suffix=f"_{sid}",
        )
        assert m.false_positive is False, sid
        assert result.referee_accepted is False or m.true_negative is True
