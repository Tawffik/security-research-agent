"""Evidence-requirement decision impact: skills must change experiment evidence checks."""

from pathlib import Path

from agent_core.evaluation.research_utility import (
    KnowledgeCondition,
    ScenarioSpec,
    build_retriever,
    run_condition,
)
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    ambiguous_incomplete_lab_scenario,
    default_idor_lab_scenario,
    secure_lab_scenario,
)
from agent_core.skills.advisor import SkillDecisionAdvisor

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"
SKILLS = ROOT / "skills"


def test_normalize_maps_identity_pair_requirement():
    toks = SkillDecisionAdvisor.normalize_evidence_requirements(
        [
            "every candidate must show the SAME request replayed under two different, "
            "legitimately-owned identities with a diffed response"
        ]
    )
    assert "Identities A/B" in toks


def test_skill_evidence_requirements_attached_to_experiments():
    ret = build_retriever(KnowledgeCondition.NONE, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="skill_ev_attach",
        knowledge_retriever=ret,
        enable_skills=True,
    )
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert runner.research.last_skill_advice is not None
    assert runner.research.last_skill_advice.evidence_requirements
    # At least one experiment should carry skill-derived identity-pair req
    found = False
    for exp in result.plan.experiments or []:
        reqs = [str(x) for x in (exp.required_evidence or [])]
        if "Identities A/B" in reqs or "cross_identity_pair" in reqs:
            found = True
            break
    assert found, "skill identity-pair requirement not attached to any experiment"


def test_ambiguous_incomplete_four_way_matrix():
    """Skills must not confirm incomplete evidence; curated alone already rejects."""
    rows = []
    for know in (KnowledgeCondition.NONE, KnowledgeCondition.CURATED):
        for skills in (False, True):
            ret = build_retriever(know, KROOT)
            runner = ClosedLoopRunner(
                scope_path=SCOPE,
                engagement_id=f"amb_{know.value}_{int(skills)}",
                knowledge_retriever=ret,
                enable_skills=skills,
            )
            r = runner.run(FIXTURE, scenario=ambiguous_incomplete_lab_scenario())
            align = r.experiment_alignment
            if hasattr(align, "to_dict"):
                align = align.to_dict()
            rows.append(
                {
                    "know": know.value,
                    "skills": skills,
                    "status": r.final_status,
                    "accepted": r.referee_accepted,
                    "suff": (align or {}).get("experiment_sufficiency"),
                }
            )
            assert r.referee_accepted is False
            assert r.final_status in ("rejected", "incomplete", "candidate")

    # Skills must not turn incomplete lab into accepted finding
    for row in rows:
        assert row["accepted"] is False


def test_secure_with_skills_still_rejects():
    tr, m, r = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=ScenarioSpec("secure_authz", "secure", "secure", "rejected"),
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=True,
        engagement_suffix="_sec_ev",
    )
    assert m.false_positive is False
    assert r.referee_accepted is False


def test_positive_with_skills_still_confirms_when_pair_present():
    tr, m, r = run_condition(
        condition=KnowledgeCondition.CURATED,
        scenario=ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed"),
        recon_path=FIXTURE,
        scope_path=SCOPE,
        knowledge_root=KROOT,
        enable_skills=True,
        engagement_suffix="_pos_ev",
    )
    assert m.true_positive is True


def test_skills_change_required_evidence_vs_baseline():
    """Measurable difference: skills add identity-pair tokens when enabled."""
    def _reqs(skills: bool) -> set[str]:
        ret = build_retriever(KnowledgeCondition.NONE, KROOT)
        runner = ClosedLoopRunner(
            scope_path=SCOPE,
            engagement_id=f"diff_{int(skills)}",
            knowledge_retriever=ret,
            enable_skills=skills,
        )
        r = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
        out: set[str] = set()
        for exp in r.plan.experiments or []:
            out.update(str(x) for x in (exp.required_evidence or []))
        return out

    base = _reqs(False)
    with_skills = _reqs(True)
    # Skills should add at least one identity-pair related requirement
    assert with_skills - base, f"no new requirements: base={base} skills={with_skills}"
    assert any(
        "Identities" in x or "cross_identity" in x for x in (with_skills - base)
    )
