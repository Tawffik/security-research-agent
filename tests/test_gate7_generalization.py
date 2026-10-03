"""Gate 7 — offline generalization across artifact classes; oracle isolation."""

import json
from pathlib import Path

from agent_core.evaluation.benchmark import DEFAULT_SUITE, evaluate_closed_result, BenchmarkCase
from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    ambiguous_incomplete_lab_scenario,
    secure_lab_scenario,
)
from agent_core.orchestrator.offline_bbci_episode import run_offline_bbci_episode
from agent_core.recon.adapter import ReconResultAdapter, RawRecon
from agent_core.target.opportunity import OpportunityEngine

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SPARSE = ROOT / "examples" / "fixtures" / "sparse_recon.json"
BBCI = ROOT / "examples" / "fixtures" / "bbci" / "oneplus.ch.live.txt"
SCOPE_ACME = ROOT / "examples" / "demo_program_scope.yaml"
SCOPE_OP = ROOT / "examples" / "fixtures" / "bbci" / "oneplus_offline_scope.yaml"


def test_class_rich_structured_recon():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    ctx, graph, _ = ReconResultAdapter("g7_rich").adapt(RawRecon.from_dict(data))
    assert len(ctx.actors) >= 2
    assert ctx.endpoints
    opps = OpportunityEngine("g7_rich").rank(ctx, graph)
    assert opps
    runner = ClosedLoopRunner(scope_path=SCOPE_ACME, engagement_id="g7_rich")
    result = runner.run(SAMPLE, scenario=default_idor_lab_scenario())
    assert result.episode is not None
    assert result.final_status is not None


def test_class_real_bbci_live_txt():
    report = run_offline_bbci_episode(
        BBCI, scope_path=SCOPE_OP, engagement_id="g7_bbci", program_name="oneplus.ch"
    )
    assert report.ok
    assert report.n_opportunities >= 1  # host_surface
    assert report.execution_mode == "offline_lab"


def test_class_sparse_minimal_recon():
    data = json.loads(SPARSE.read_text(encoding="utf-8"))
    ctx, graph, _ = ReconResultAdapter("g7_sparse").adapt(RawRecon.from_dict(data))
    assert ctx.primary_host == "sparse.example.test"
    opps = OpportunityEngine("g7_sparse").rank(ctx, graph)
    assert any(o.type == "host_surface" for o in opps)
    assert not any(o.type in ("authorization", "authorization_mutation") for o in opps)


def test_class_ambiguous_incomplete_no_positive_finding():
    runner = ClosedLoopRunner(scope_path=SCOPE_ACME, engagement_id="g7_amb")
    result = runner.run(SAMPLE, scenario=ambiguous_incomplete_lab_scenario())
    case = BenchmarkCase("bm_ambiguous_incomplete", "ambiguous_incomplete", "ambiguous", "incomplete")
    score = evaluate_closed_result(case, result)
    assert score.true_positive is False
    assert score.false_positive is False


def test_oracle_not_in_plan_fields():
    runner = ClosedLoopRunner(scope_path=SCOPE_ACME, engagement_id="g7_oracle")
    result = runner.run(SAMPLE, scenario=secure_lab_scenario())
    plan = result.plan
    blob = str(plan)
    assert "ground_truth" not in blob
    assert "expected_vulnerability" not in blob
