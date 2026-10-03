"""Gate 7 expanded hidden-oracle benchmark suite."""

from pathlib import Path

from agent_core.evaluation.benchmark import DEFAULT_SUITE, run_lab_benchmark, _scenario
from agent_core.orchestrator.closed_loop import ClosedLoopRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_expanded_suite_has_behavioral_gaps():
    ids = {c.case_id for c in DEFAULT_SUITE}
    assert "bm_ambiguous_incomplete" in ids
    assert "bm_role_authorized" in ids
    assert "bm_cache_artifact" in ids


def test_scenario_factories_resolve():
    for name in (
        "ambiguous_incomplete",
        "role_authorized",
        "cache_artifact",
        "default_idor",
        "secure",
    ):
        sc = _scenario(name)
        assert sc.observations is not None


def test_run_expanded_benchmark_offline():
    report = run_lab_benchmark(runner_factory=lambda: ClosedLoopRunner(scope_path=SCOPE, engagement_id="bm_expand"), recon_path=FIXTURE, suite=DEFAULT_SUITE)
    assert len(report.scores) == len(DEFAULT_SUITE)
    # Oracle not injected into runner — scores are post-hoc
    by_id = {s.case_id: s for s in report.scores}
    # Incomplete case must not be scored as true_positive
    amb = by_id["bm_ambiguous_incomplete"]
    assert amb.true_positive is False
