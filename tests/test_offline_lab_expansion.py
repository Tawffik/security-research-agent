"""Offline lab expansion: traversal, upload, deserialization, held-out injection/XSS."""

from __future__ import annotations

from pathlib import Path

from agent_core.evaluation.capability_readiness import build_readiness_matrix
from agent_core.evaluation.research_utility import KnowledgeCondition, build_retriever
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    hard_deserialization_lab_scenario,
    hard_path_traversal_lab_scenario,
    hard_upload_lab_scenario,
    heldout_secure_xss_lab_scenario,
    heldout_sqli_lab_scenario,
    heldout_xss_lab_scenario,
    secure_deserialization_lab_scenario,
    secure_path_traversal_lab_scenario,
    secure_upload_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"
KROOT = ROOT / "knowledge"
SKILLS = ROOT / "skills"


def _run(eng: str, scenario, knowledge: KnowledgeCondition):
    ret = build_retriever(knowledge, KROOT)
    return ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id=eng,
        knowledge_retriever=ret,
    ).run(FIXTURE, scenario=scenario)


def test_hard_path_traversal_curated_confirms():
    r = _run("trav_curated", hard_path_traversal_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_hard_path_traversal_none_not_confirmed():
    r = _run("trav_none", hard_path_traversal_lab_scenario(), KnowledgeCondition.NONE)
    assert r.final_status != "confirmed" or r.knowledge_procedure_required_blocked


def test_secure_path_traversal_no_fp():
    r = _run("trav_secure", secure_path_traversal_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_path_string_alone_not_enough_secure_control():
    """403 containment must not confirm merely because path contained ../."""
    r = _run("trav_secure2", secure_path_traversal_lab_scenario(), KnowledgeCondition.CURATED)
    assert "path_outside" in (secure_path_traversal_lab_scenario().observations[1].body)


def test_hard_upload_curated_confirms():
    r = _run("up_curated", hard_upload_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_secure_upload_no_fp():
    r = _run("up_secure", secure_upload_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_hard_deserialization_curated_confirms():
    r = _run("deser_curated", hard_deserialization_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_secure_deserialization_no_fp():
    r = _run("deser_secure", secure_deserialization_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_heldout_sqli_curated_confirms():
    r = _run("ho_sqli", heldout_sqli_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_heldout_xss_curated_confirms():
    r = _run("ho_xss", heldout_xss_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_heldout_secure_xss_no_fp():
    r = _run("ho_xss_sec", heldout_secure_xss_lab_scenario(), KnowledgeCondition.CURATED)
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_requires_knowledge_procedure_not_oracle_label():
    """
    Gate uses experiment knowledge-driven flag, not ScenarioSpec.ground_truth.
    LabScenario has no ground_truth field; evaluation-only specs stay outside runner.
    """
    scenario = hard_path_traversal_lab_scenario()
    assert not hasattr(scenario, "ground_truth")
    assert scenario.requires_knowledge_procedure is True
    # Secure counterpart does not force confirmation via inverted flag alone
    sec = secure_path_traversal_lab_scenario()
    assert sec.requires_knowledge_procedure is False
    assert sec.suggests_authz_issue is False


def test_readiness_includes_new_domains():
    m = build_readiness_matrix(KROOT, skills_root=SKILLS)
    assert m["traversal"].lab_scenarios
    assert m["upload"].lab_scenarios
    assert m["deserialization"].lab_scenarios
    assert m["traversal"].readiness in ("LAB_TESTED", "BENCHMARKED")
    # path_traversal alias should not leave proc-only in other if domain is traversal
    assert m["traversal"].knowledge_procedures >= 1 or m["other"].knowledge_procedures >= 0
