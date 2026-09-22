"""End-to-end offline research loop tests (Sprint 2–6)."""

from __future__ import annotations

from pathlib import Path

from agent_core.orchestrator.research_loop import ResearchLoop
from agent_core.schemas.research import DecisionAction

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "sample_recon.json"


def test_full_offline_loop():
    loop = ResearchLoop(engagement_id="eng_loop_1")
    result = loop.run_from_recon_file(FIXTURE)

    assert result.engagement_id == "eng_loop_1"
    assert len(result.opportunities) >= 1
    assert len(result.unknowns) >= 1
    assert len(result.hypotheses) >= 2
    assert len(result.experiments) >= 1
    assert result.decision.decision in (
        DecisionAction.EXECUTE,
        DecisionAction.REQUEST_APPROVAL,
        DecisionAction.STOP,
    )
    assert result.decision.candidate or result.decision.decision == DecisionAction.STOP
    assert "authorization" in [o.type for o in result.opportunities] or any(
        "ownership" in h.statement.lower() for h in result.hypotheses
    )
    assert result.target_graph.edges
    assert "endpoints=" in result.summary


def test_opportunity_ranking_prefers_authz():
    loop = ResearchLoop("eng_rank")
    result = loop.run_from_recon_file(FIXTURE)
    # Top opportunities should include authorization surfaces with {id}
    types = [o.type for o in result.opportunities[:5]]
    assert "authorization" in types or "state_violation" in types


def test_jev_picks_high_info_gain_experiment():
    loop = ResearchLoop("eng_jev")
    result = loop.run_from_recon_file(FIXTURE)
    if result.decision.decision == DecisionAction.EXECUTE:
        exp = next(e for e in result.experiments if e.experiment_id == result.decision.candidate)
        assert exp.information_gain >= 0.3
        assert "HIGH_INFORMATION_GAIN" in result.decision.reason_codes or exp.information_gain < 0.7


def test_hypothesis_has_alternatives():
    loop = ResearchLoop("eng_alt")
    result = loop.run_from_recon_file(FIXTURE)
    ownership = [h for h in result.hypotheses if "ownership" in h.statement.lower()]
    assert ownership
    assert len(ownership[0].alternatives) >= 2
