"""§92 adaptive loop: re-rank + next experiment or intelligent stop."""

from pathlib import Path

from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_rejected_adaptive_stops_no_spray():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ad_r")
    closed = runner.run(FIXTURE, scenario=secure_lab_scenario())
    step = AdaptiveLoop("eng_ad_r").step(closed)
    assert step.stop is True
    assert step.next_action == "STOP"
    assert step.stop_reason == "hypothesis_disproven"
    assert any("negative" in n.lower() or "spray" in n.lower() for n in step.notes)


def test_confirmed_with_variants_may_continue_once():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ad_c")
    closed = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert closed.referee_accepted
    assert closed.variants
    step = AdaptiveLoop("eng_ad_c").step(closed)
    # Either continue with one variant experiment or stop with explicit reason
    if not step.stop:
        assert step.next_action == "EXECUTE_VARIANT"
        assert step.next_experiment is not None
        assert step.decision is not None
        assert any("variant" in n.lower() or "discriminat" in n.lower() for n in step.notes)
    else:
        assert step.stop_reason in (
            "sufficient_evidence",
            "jev_stop",
            "no_valuable_variants_experiment",
            "no_open_hypothesis",
        )


def test_adaptive_reranks_opportunities():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_ad_rank")
    closed = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    step = AdaptiveLoop("eng_ad_rank").step(closed)
    assert isinstance(step.reranked_opportunities, list)
