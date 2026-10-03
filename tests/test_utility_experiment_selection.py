"""Utility-aware experiment selection — explainable, not authorization."""

from agent_core.experiments.utility import score_utility, select_by_utility
from agent_core.schemas.research import Experiment, ExperimentStatus, Hypothesis, HypothesisStatus
from agent_core.tools.capability import capability_differential
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ
from agent_core.scope.guard import ScopeGuard
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def _exp(eid, ig=0.5, cost=0.3, risk=0.3, req=None, disc=""):
    return Experiment(
        experiment_id=eid,
        hypothesis_id="h1",
        description=eid,
        information_gain=ig,
        cost=cost,
        risk=risk,
        required_evidence=req or [],
        discriminator=disc,
        status=ExperimentStatus.PLANNED,
    )


def test_utility_prefers_high_ig_low_cost_low_risk():
    high = _exp("e_high", ig=0.9, cost=0.1, risk=0.1, disc="d")
    low = _exp("e_low", ig=0.2, cost=0.8, risk=0.8)
    best, scores = select_by_utility([low, high])
    assert best.experiment_id == "e_high"
    by = {s.experiment_id: s for s in scores}
    assert by["e_high"].utility > by["e_low"].utility
    assert "ig=" in ",".join(by["e_high"].reasons)


def test_evidence_debt_boosts_matching_experiment():
    a = _exp("e_a", ig=0.4, req=["challenge_status"])
    b = _exp("e_b", ig=0.5, req=["other"])
    best, scores = select_by_utility(
        [a, b], evidence_gaps=["challenge_status"]
    )
    by = {s.experiment_id: s for s in scores}
    assert by["e_a"].evidence_debt_reduction > by["e_b"].evidence_debt_reduction


def test_prior_experiment_penalized():
    e = _exp("e_prior", ig=0.9)
    s0 = score_utility(e)
    s1 = score_utility(e, prior_experiment_ids=["e_prior"])
    assert s1.utility < s0.utility
    assert s1.prior_penalty > 0


def test_missing_prerequisite_marks_ineligible():
    e = Experiment(
        experiment_id="e_pre",
        hypothesis_id="h1",
        description="needs multi",
        preconditions=["multi-identity"],
        status=ExperimentStatus.PLANNED,
    )
    s = score_utility(e, available_preconditions=["single-identity"])
    assert s.prerequisite_ok is False
    assert s.eligible is False


def test_utility_ranking_does_not_authorize_execution():
    """Winning utility score never bypasses ExecutionBoundary."""
    best, _ = select_by_utility([_exp("e1", ig=1.0, cost=0.0, risk=0.0)])
    assert best is not None
    guard = ScopeGuard.from_scope_file(SCOPE)
    b = ExecutionBoundary(guard=guard)
    b.register(AUTHENTICATED_HTTP_READ)
    # high utility experiment still needs host/scope
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="",
            experiment_id=best.experiment_id,
        )
    )
    assert d.allowed is False


def test_capability_differential_declared_vs_observed():
    rec = capability_differential(
        name="authenticated_http_request",
        declared_available=True,
        observed_available=False,
        declared_exposed=True,
        observed_exposed=False,
        scope_checked=True,
        scope_allowed=False,
    )
    assert rec.differential == "declared_only"
    assert "llm_decision_neq_authorization" in rec.notes
    assert "skill_metadata_neq_execution_permission" in rec.notes


def test_skill_metadata_cannot_expand_scope():
    rec = capability_differential(
        name="overclaimed_tool",
        declared_available=True,
        observed_available=True,
        scope_checked=False,
        scope_allowed=False,
    )
    assert "scope_not_checked_cannot_execute" in rec.notes
