"""Offline lab + knowledge utility for injection and XSS domains."""

from __future__ import annotations

from pathlib import Path

from agent_core.evaluation.capability_readiness import build_readiness_matrix
from agent_core.evaluation.research_utility import (
    KnowledgeCondition,
    build_retriever,
    run_condition,
)
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    hard_sqli_lab_scenario,
    hard_xss_lab_scenario,
    secure_sqli_lab_scenario,
    secure_xss_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"
KROOT = ROOT / "knowledge"
SKILLS = ROOT / "skills"


def test_hard_sqli_curated_knowledge_can_confirm():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="sqli_curated",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=hard_sqli_lab_scenario())
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True
    procs = []
    for exp in r.plan.experiments or []:
        desc = exp.description or ""
        if "PROC-0018" in desc or "sql" in desc.lower() or "boolean" in desc.lower():
            procs.append(exp.experiment_id)
    # Prefer knowledge-driven procedure; at minimum confirmation under curated knowledge
    assert r.final_status == "confirmed"


def test_hard_sqli_without_knowledge_is_not_confirmed():
    ret = build_retriever(KnowledgeCondition.NONE, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="sqli_none",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=hard_sqli_lab_scenario())
    # requires_knowledge_procedure → blocked or non-confirmed without procedure
    assert r.final_status != "confirmed" or r.knowledge_procedure_required_blocked


def test_secure_sqli_no_false_positive():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="sqli_secure",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=secure_sqli_lab_scenario())
    assert r.referee_accepted is False
    assert r.final_status in ("rejected", "candidate", "inconclusive", None) or r.final_status != "confirmed"


def test_hard_xss_curated_knowledge_can_confirm():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="xss_curated",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=hard_xss_lab_scenario())
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_hard_xss_without_knowledge_not_confirmed():
    ret = build_retriever(KnowledgeCondition.NONE, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="xss_none",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=hard_xss_lab_scenario())
    assert r.final_status != "confirmed" or r.knowledge_procedure_required_blocked


def test_secure_xss_no_false_positive():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    runner = ClosedLoopRunner(
        scope_path=SCOPE,
        engagement_id="xss_secure",
        knowledge_retriever=ret,
    )
    r = runner.run(FIXTURE, scenario=secure_xss_lab_scenario())
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_readiness_matrix_injection_and_xss_have_labs():
    matrix = build_readiness_matrix(KROOT, skills_root=SKILLS)
    assert matrix["injection"].knowledge_procedures >= 1
    assert any("sqli" in x for x in matrix["injection"].lab_scenarios)
    assert matrix["injection"].readiness in ("LAB_TESTED", "BENCHMARKED")
    assert matrix["xss"].knowledge_procedures >= 1
    assert any("xss" in x for x in matrix["xss"].lab_scenarios)
    assert matrix["authorization"].readiness in ("LAB_TESTED", "BENCHMARKED")
    assert matrix["authorization"].knowledge_cases >= 1


def test_hard_jwt_curated_confirms():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    from agent_core.orchestrator.closed_loop import hard_jwt_lab_scenario

    r = ClosedLoopRunner(
        scope_path=SCOPE, engagement_id="jwt_curated", knowledge_retriever=ret
    ).run(FIXTURE, scenario=hard_jwt_lab_scenario())
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_secure_jwt_no_fp():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    from agent_core.orchestrator.closed_loop import secure_jwt_lab_scenario

    r = ClosedLoopRunner(
        scope_path=SCOPE, engagement_id="jwt_secure", knowledge_retriever=ret
    ).run(FIXTURE, scenario=secure_jwt_lab_scenario())
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_hard_csrf_curated_confirms():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    from agent_core.orchestrator.closed_loop import hard_csrf_lab_scenario

    r = ClosedLoopRunner(
        scope_path=SCOPE, engagement_id="csrf_curated", knowledge_retriever=ret
    ).run(FIXTURE, scenario=hard_csrf_lab_scenario())
    assert r.final_status == "confirmed"
    assert r.referee_accepted is True


def test_secure_csrf_no_fp():
    ret = build_retriever(KnowledgeCondition.CURATED, KROOT)
    from agent_core.orchestrator.closed_loop import secure_csrf_lab_scenario

    r = ClosedLoopRunner(
        scope_path=SCOPE, engagement_id="csrf_secure", knowledge_retriever=ret
    ).run(FIXTURE, scenario=secure_csrf_lab_scenario())
    assert r.referee_accepted is False
    assert r.final_status != "confirmed"


def test_authentication_domain_readiness():
    matrix = build_readiness_matrix(KROOT, skills_root=SKILLS)
    authn = matrix["authentication"]
    assert authn.knowledge_procedures >= 1
    assert len(authn.lab_scenarios) >= 2
    assert authn.readiness in ("LAB_TESTED", "BENCHMARKED")
