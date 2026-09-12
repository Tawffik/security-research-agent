"""Tests for Phase-A EngagementOrchestrator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.orchestrator import EngagementConfig, EngagementOrchestrator
from agent_core.scope.guard import ScopeViolation

ROOT = Path(__file__).parent.parent
SKILLS = ROOT / "skills"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def _config(tmp_path, **kwargs) -> EngagementConfig:
    base = dict(
        scope_path=SCOPE,
        skills_dir=SKILLS,
        data_dir=tmp_path / "data",
        engagement_id="test-eng",
    )
    base.update(kwargs)
    return EngagementConfig(**base)


def test_happy_path_confirms_finding(tmp_path):
    orch = EngagementOrchestrator(_config(tmp_path))
    result = orch.run()
    assert result.evidence_chain_valid is True
    assert result.accepted is True
    assert result.finding_id is not None
    assert result.final_status == "confirmed"
    assert "recon-js-surface" in result.skills_run
    assert "authz-idor-analysis" in result.skills_run
    assert "report-generator" in result.skills_run
    assert result.budget["tool_calls_spent"] >= 1


def test_steering_skip_skill(tmp_path):
    orch = EngagementOrchestrator(
        _config(tmp_path, steering=["skip:authz-idor-analysis"])
    )
    result = orch.run()
    assert "authz-idor-analysis" in result.skills_skipped
    assert result.accepted is False
    assert result.finding_id is None


def test_steering_reject_hypothesis(tmp_path):
    orch = EngagementOrchestrator(
        _config(tmp_path, steering=["reject:H-idor-invoices"])
    )
    result = orch.run()
    assert result.accepted is False
    assert result.finding_id is None
    assert "steering" in result.reason.lower() or "reject" in result.reason.lower()


def test_out_of_scope_host_raises(tmp_path):
    orch = EngagementOrchestrator(
        _config(tmp_path, primary_host="billing.acme-demo.test")
    )
    try:
        orch.run()
        assert False, "expected ScopeViolation"
    except ScopeViolation:
        pass


def test_budget_is_tracked(tmp_path):
    orch = EngagementOrchestrator(_config(tmp_path, tool_call_budget=100))
    result = orch.run()
    assert result.budget["tool_calls_spent"] > 0
    assert result.budget["tool_calls_spent"] <= result.budget["tool_call_budget"]
