"""Research episodes prioritize quality, not request volume."""

from pathlib import Path

from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_confirmed_episode_has_efficiency_and_lessons():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ep_c")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    ep = result.episode
    assert ep is not None
    assert ep.outcome == "confirmed"
    assert ep.finding_id == result.finding_id
    m = ep.metrics
    m.compute()
    assert m.confirmed_findings == 1
    assert m.evidence_items >= 1
    assert m.requests_simulated <= 4  # discriminating, not spray
    assert m.efficiency_proxy > 0
    assert any("variant" in x.lower() or "discriminat" in x.lower() or "root" in x.lower() for x in ep.lessons)


def test_rejected_episode_counts_false_positive_avoided():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ep_r")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    ep = result.episode
    assert ep is not None
    assert ep.outcome == "rejected"
    assert ep.metrics.false_positive_avoided == 1
    assert ep.metrics.confirmed_findings == 0
    assert any("false positive" in x.lower() or "negative" in x.lower() for x in ep.lessons)


def test_episode_write_json(tmp_path):
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ep_w")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    from agent_core.evaluation.episode import EpisodeRecorder

    path = EpisodeRecorder("eng_ep_w").write(result.episode, tmp_path)
    assert path.exists()
    data = path.read_text()
    assert "efficiency_proxy" in data
    assert "lessons" in data
