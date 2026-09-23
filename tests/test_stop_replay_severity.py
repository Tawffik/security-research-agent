from pathlib import Path

from agent_core.decisions.stop_conditions import StopPolicy, StopReasonCode
from agent_core.evaluation.replay import replay_from_engagement_dir, replay_from_objects
from agent_core.findings.severity import assess_authz_finding
from agent_core.orchestrator.artifacts import write_engagement_artifacts
from agent_core.orchestrator.closed_loop import default_idor_lab_scenario, secure_lab_scenario
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_stop_policy_scope_and_reject():
    p = StopPolicy()
    assert p.evaluate(scope_allowed=False).reason_code == StopReasonCode.SCOPE_BLOCKED.value
    d = p.evaluate(final_status="rejected", adaptive_reason="hypothesis_disproven")
    assert d.should_stop and d.reason_code == StopReasonCode.HYPOTHESIS_DISPROVEN.value


def test_pipeline_stop_severity_replay(tmp_path):
    result = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_srs",
        scenario=default_idor_lab_scenario(),
    )
    closed, adaptive, cp, regrets, surprises, mem, matrix, inv, stop, severity, replay = result
    assert stop.should_stop is True or adaptive.next_action == "EXECUTE_VARIANT"
    assert severity.level in ("medium", "high", "info")
    assert replay.engagement_id == "eng_srs"
    assert replay.evidence_ids

    written = write_engagement_artifacts(
        tmp_path / "engagement",
        engagement_id="eng_srs",
        closed=closed,
        adaptive=adaptive,
        checkpoint=cp,
        regrets=regrets,
        surprises=surprises,
        memory_entries=mem,
        claim_matrix=matrix,
        invariant_checks=inv,
    )
    # also dump stop/severity/replay
    import json
    (tmp_path / "engagement" / "stop_decision.json").write_text(json.dumps(stop.to_dict(), indent=2))
    (tmp_path / "engagement" / "severity.json").write_text(json.dumps(severity.to_dict(), indent=2))
    (tmp_path / "engagement" / "replay_summary.json").write_text(json.dumps(replay.to_dict(), indent=2))
    r2 = replay_from_engagement_dir(tmp_path / "engagement")
    assert r2.engagement_id == "eng_srs"


def test_severity_info_when_not_confirmed():
    s = assess_authz_finding(confirmed=False)
    assert s.level == "info"
