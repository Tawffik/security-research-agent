"""
Research Twin / hidden-oracle benchmark (M14).

Ground truth is NOT passed into ResearchLoop / ClosedLoopRunner.
Evaluator scores outcomes after the fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent_core.orchestrator.closed_loop import (
    ClosedLoopResult,
    LabScenario,
    default_idor_lab_scenario,
    public_resource_lab_scenario,
    secure_lab_scenario,
    shared_object_lab_scenario,
)


@dataclass
class BenchmarkCase:
    case_id: str
    scenario_factory: str  # name of factory
    # Hidden from agent — evaluator only
    ground_truth: str  # vulnerable | secure | public | shared | ambiguous
    expected_agent_outcome: str  # confirmed | rejected | incomplete | scope_denied


@dataclass
class BenchmarkScore:
    case_id: str
    ground_truth: str
    agent_outcome: str
    true_positive: bool = False
    true_negative: bool = False
    false_positive: bool = False
    false_negative: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkReport:
    scores: list[BenchmarkScore] = field(default_factory=list)

    @property
    def false_positive_rate(self) -> float:
        denom = sum(1 for s in self.scores if s.false_positive or s.true_negative)
        if denom == 0:
            return 0.0
        return sum(1 for s in self.scores if s.false_positive) / denom

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": [s.to_dict() for s in self.scores],
            "false_positive_rate": self.false_positive_rate,
            "n": len(self.scores),
        }


DEFAULT_SUITE = [
    BenchmarkCase("bm_vuln_idor", "default_idor", "vulnerable", "confirmed"),
    BenchmarkCase("bm_secure", "secure", "secure", "rejected"),
    BenchmarkCase("bm_public", "public", "public", "rejected"),
    BenchmarkCase("bm_shared", "shared", "shared", "rejected"),
]


def _scenario(name: str, host: str = "api.acme-demo.test") -> LabScenario:
    if name == "default_idor":
        return default_idor_lab_scenario(host)
    if name == "secure":
        return secure_lab_scenario(host)
    if name == "public":
        return public_resource_lab_scenario(host)
    if name == "shared":
        return shared_object_lab_scenario(host)
    raise ValueError(name)


def evaluate_closed_result(case: BenchmarkCase, result: ClosedLoopResult) -> BenchmarkScore:
    if not result.scope_allowed:
        outcome = "scope_denied"
    elif result.referee_accepted:
        outcome = "confirmed"
    elif result.final_status == "rejected":
        outcome = "rejected"
    else:
        outcome = result.final_status or "incomplete"

    gt = case.ground_truth
    tp = gt == "vulnerable" and outcome == "confirmed"
    tn = gt != "vulnerable" and outcome in ("rejected", "incomplete")
    fp = gt != "vulnerable" and outcome == "confirmed"
    fn = gt == "vulnerable" and outcome != "confirmed"

    return BenchmarkScore(
        case_id=case.case_id,
        ground_truth=gt,
        agent_outcome=outcome,
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        notes="ground_truth hidden from research loop",
    )


def run_lab_benchmark(
    *,
    runner_factory,
    recon_path,
    suite: Optional[list[BenchmarkCase]] = None,
) -> BenchmarkReport:
    """
    runner_factory() -> ClosedLoopRunner
    Ground truth never injected into runner.
    """
    suite = suite or list(DEFAULT_SUITE)
    scores: list[BenchmarkScore] = []
    for case in suite:
        runner = runner_factory()
        scenario = _scenario(case.scenario_factory)
        result = runner.run(recon_path, scenario=scenario)
        scores.append(evaluate_closed_result(case, result))
    return BenchmarkReport(scores=scores)


def attach_benchmark_to_candidates(result: ClosedLoopResult, score: BenchmarkScore) -> None:
    """Persist benchmark outcome onto knowledge candidates (does not change agent prior decisions)."""
    snap = {
        "case_id": score.case_id,
        "ground_truth_hidden_from_agent": True,
        "agent_outcome": score.agent_outcome,
        "true_positive": score.true_positive,
        "true_negative": score.true_negative,
        "false_positive": score.false_positive,
        "false_negative": score.false_negative,
    }
    for c in getattr(result, "knowledge_candidates", None) or []:
        c.benchmark_snapshot = dict(snap)
