"""Evidence report + closed-loop belief/stop-reason tests."""

from __future__ import annotations

from pathlib import Path

from agent_core.findings.report import build_evidence_report
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)
from agent_core.skills.lifecycle import SkillLifecycleState, can_transition

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_report_blocks_confirmed_without_evidence():
    r = build_evidence_report(
        engagement_id="e1",
        title="x",
        claim="y",
        status="confirmed",
        evidence_ids=[],
    )
    assert r.report_blocked is True
    assert r.status == "incomplete"


def test_closed_loop_records_stop_and_beliefs_and_report():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_report_idor")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.stop_reason == "sufficient_evidence"
    assert result.belief_updates
    assert result.report is not None
    assert result.report.report_blocked is False
    assert result.report.evidence_ids
    assert "Evidence IDs" in result.report.markdown
    assert result.final_status == "confirmed"


def test_closed_loop_rejected_stop_reason():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_report_secure")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    assert result.stop_reason == "hypothesis_disproven"
    assert result.report is not None
    assert result.final_status == "rejected"


def test_skill_lifecycle_no_skip_to_approved():
    assert can_transition(SkillLifecycleState.DRAFT, SkillLifecycleState.APPROVED) is False
    assert can_transition(SkillLifecycleState.DRAFT, SkillLifecycleState.CANDIDATE) is True
    assert can_transition(SkillLifecycleState.REVIEW, SkillLifecycleState.APPROVED) is True
