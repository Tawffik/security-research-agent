"""M14: Hidden-oracle lab benchmark — ground truth not passed to agent."""

from pathlib import Path

from agent_core.evaluation.benchmark import (
    DEFAULT_SUITE,
    evaluate_closed_result,
    run_lab_benchmark,
    BenchmarkCase,
)
from agent_core.orchestrator.closed_loop import ClosedLoopRunner, default_idor_lab_scenario

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_benchmark_suite_runs_without_ground_truth_in_runner():
    def factory():
        return ClosedLoopRunner(scope_path=SCOPE, engagement_id="bm")

    report = run_lab_benchmark(runner_factory=factory, recon_path=FIXTURE)
    assert report.scores
    assert len(report.scores) == len(DEFAULT_SUITE)
    # Vulnerable case should ideally be TP; secure/public/shared not FP
    by_id = {s.case_id: s for s in report.scores}
    assert by_id["bm_vuln_idor"].true_positive or by_id["bm_vuln_idor"].false_negative
    for cid in ("bm_secure", "bm_public", "bm_shared"):
        assert by_id[cid].false_positive is False


def test_ground_truth_only_in_evaluator():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="bm2").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    case = BenchmarkCase("x", "default_idor", "vulnerable", "confirmed")
    score = evaluate_closed_result(case, result)
    assert score.notes.startswith("ground_truth hidden")
    assert not hasattr(result, "ground_truth")


def test_adversarial_oracle_not_on_closed_result_fields():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="bm_adv").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    dumped = str(result.__dict__)
    assert "ground_truth" not in dumped
    assert "vulnerable" not in (result.experiment_alignment or {})
