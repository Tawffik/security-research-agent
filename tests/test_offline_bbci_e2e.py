"""Gate 6A — Real BBCI artifact → offline full research episode."""

from pathlib import Path

from agent_core.orchestrator.offline_bbci_episode import (
    lab_scenario_from_bbci_live_txt,
    run_offline_bbci_episode,
)
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ
from agent_core.scope.guard import ScopeGuard

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "examples" / "fixtures" / "bbci" / "oneplus.ch.live.txt"
SCOPE = ROOT / "examples" / "fixtures" / "bbci" / "oneplus_offline_scope.yaml"


def test_real_bbci_artifact_exists():
    assert ARTIFACT.is_file()
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "oneplus.ch" in text
    assert "http" in text


def test_offline_bbci_full_episode_pipeline():
    report = run_offline_bbci_episode(
        ARTIFACT,
        scope_path=SCOPE,
        engagement_id="bbci_e2e_1",
        program_name="oneplus.ch",
    )
    assert report.execution_mode == "offline_lab"
    assert "no_live_http" in report.notes
    assert report.contract_ok is True
    assert report.artifact_provenance.get("source_shape") == "live_txt" or report.artifact_path.endswith(
        "live.txt"
    )
    for stage in (
        "ingestion",
        "adaptation",
        "observation",
        "evidence",
        "verification",
        "episode",
        "execution_boundary",
    ):
        assert report.stages.get(stage) is True, stage
    assert report.ok is True
    assert report.episode_id
    assert report.evidence_ids
    assert report.decision
    # Oracle isolation: suggests_authz_issue false on artifact-derived scenario
    assert report.closed_loop is not None
    # Differential may be present
    assert report.differential_change_kind or report.stages.get("differential")


def test_live_mode_never_allowed_on_offline_episode():
    guard = ScopeGuard.from_scope_file(SCOPE)
    b = ExecutionBoundary(guard=guard)
    b.register(AUTHENTICATED_HTTP_READ)
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="oneplus.ch",
            live_mode=True,
        )
    )
    assert d.allowed is False


def test_lab_scenario_from_artifact_not_oracle_label():
    text = ARTIFACT.read_text(encoding="utf-8")
    sc = lab_scenario_from_bbci_live_txt(text, primary_host="oneplus.ch")
    assert sc.suggests_authz_issue is False
    assert len(sc.observations) >= 2
    assert all(getattr(o, "notes", "").startswith("bbci") for o in sc.observations)


def test_malformed_artifact_fails_safely(tmp_path):
    bad = tmp_path / "bad.live.txt"
    bad.write_text("not a url line\n@@@\n", encoding="utf-8")
    report = run_offline_bbci_episode(bad, scope_path=SCOPE, engagement_id="bad")
    # may warn but should not raise
    assert report.execution_mode == "offline_lab"
