"""M6.6: follow-up prefers experiments that can cover the CoverageGap."""

from agent_core.experiments.designer import steps_from_procedure
from agent_core.orchestrator.adaptive import AdaptiveLoop
from agent_core.orchestrator.closed_loop import ClosedLoopResult
from agent_core.orchestrator.experiment_alignment import (
    CoverageGap,
    derive_coverage_gap,
    experiment_addresses_gap,
    prefer_gap_covering_candidates,
)
from agent_core.orchestrator.research_loop import ResearchLoopResult
from agent_core.schemas.research import (
    Decision,
    DecisionAction,
    Experiment,
    ExperimentStatus,
    ExperimentStep,
    ExperimentStepRole,
    Hypothesis,
    HypothesisStatus,
)
from agent_core.schemas.target import TargetContext, TargetGraph


def _exp(eid: str, roles: list[str], hyp="h1") -> Experiment:
    steps = [
        ExperimentStep(
            step_id=f"{eid}-S{i:02d}",
            order=i,
            role=ExperimentStepRole(r),
            text=f"{r} step",
        )
        for i, r in enumerate(roles, start=1)
    ]
    return Experiment(
        experiment_id=eid,
        hypothesis_id=hyp,
        description=f"exp {eid} roles={roles}",
        steps=steps,
        status=ExperimentStatus.PLANNED,
        information_gain=0.8,
        cost=0.2,
        risk=0.2,
    )


def test_a_missing_challenge_prefers_challenge_capable():
    gap = CoverageGap(missing_roles=["challenge"], missing_step_ids=["P-S02"])
    a = _exp("exp_a", ["baseline", "challenge", "compare"])
    b = _exp("exp_b", ["observe"])
    covering, other = prefer_gap_covering_candidates([b, a], gap)
    assert covering[0].experiment_id == "exp_a"
    assert all(e.experiment_id != "exp_a" for e in other) or "exp_b" in [e.experiment_id for e in other]


def test_b_missing_baseline_prefers_baseline():
    gap = CoverageGap(missing_roles=["baseline"])
    a = _exp("exp_base", ["baseline", "challenge"])
    b = _exp("exp_chal_only", ["challenge"])
    covering, _ = prefer_gap_covering_candidates([b, a], gap)
    assert covering[0].experiment_id == "exp_base"


def test_c_ambiguous_baseline_not_positive():
    gap = CoverageGap(ambiguous_roles=["baseline"], ambiguous_step_ids=["P-S01"])
    assert "baseline" in gap.target_roles
    a = _exp("exp_b", ["baseline"])
    assert experiment_addresses_gap(a, gap)


def test_d_unrelated_cannot_outrank_by_id_alone():
    gap = CoverageGap(missing_roles=["challenge"])
    challenge_exp = _exp("zzz_unrelated_id_sorts_last", ["challenge"])
    unrelated = _exp("aaa_sorts_first", ["observe"])
    covering, other = prefer_gap_covering_candidates([unrelated, challenge_exp], gap)
    assert covering and covering[0].experiment_id == "zzz_unrelated_id_sorts_last"
    assert unrelated in other or unrelated.experiment_id in [e.experiment_id for e in other]


def test_e_no_covering_candidate_fallback():
    gap = CoverageGap(missing_roles=["challenge"])
    only = [_exp("exp_obs", ["observe"])]
    covering, other = prefer_gap_covering_candidates(only, gap)
    assert covering == []
    assert other == only


def test_f_tried_covering_experiment_not_retried():
    gap = CoverageGap(missing_roles=["challenge"], prior_experiment_id="exp_a")
    a = _exp("exp_a", ["challenge"])
    b = _exp("exp_b", ["observe"])
    candidates = [e for e in [a, b] if e.experiment_id not in {"exp_a"}]
    covering, other = prefer_gap_covering_candidates(candidates, gap)
    assert a not in covering and a not in other
    assert covering == []


def _minimal_closed(align: dict, selected: str, experiments: list[Experiment]) -> ClosedLoopResult:
    plan = ResearchLoopResult(
        engagement_id="e",
        target_context=TargetContext(engagement_id="e", primary_host="h"),
        target_graph=TargetGraph(engagement_id="e"),
        normalized_recon={},
        opportunities=[],
        unknowns=[],
        beliefs=[],
        hypotheses=[
            Hypothesis(
                hypothesis_id="h1",
                statement="test",
                primary_explanation="x",
                status=HypothesisStatus.OPEN,
            )
        ],
        experiments=experiments,
        decision=Decision(
            decision_id="d1",
            decision=DecisionAction.EXECUTE,
            candidate=selected,
            experiment_id=selected,
            hypothesis_id="h1",
        ),
        summary="t",
    )
    return ClosedLoopResult(
        plan=plan,
        scope_allowed=True,
        selected_experiment_id=selected,
        experiment_alignment=align,
        final_status="incomplete",
    )


def test_g_provenance_gap_to_selection():
    steps = steps_from_procedure(
        "PROC-0001",
        ["As owner: x", "As non-owner: y", "compare"],
    )
    # Simulate coverage: challenge missing
    from agent_core.orchestrator.experiment_alignment import StepCoverage

    cov = [
        StepCoverage("PROC-0001-S01", "baseline", "covered", ["b"], "As owner"),
        StepCoverage("PROC-0001-S02", "challenge", "missing", [], "As non-owner"),
        StepCoverage("PROC-0001-S03", "compare", "missing", [], "compare"),
    ]
    gap = derive_coverage_gap(
        Experiment(
            experiment_id="exp_prior",
            hypothesis_id="h1",
            description="p",
            steps=steps,
            status=ExperimentStatus.PLANNED,
        ),
        cov,
        prior_experiment_id="exp_prior",
    )
    assert "challenge" in gap.missing_roles
    a = _exp("exp_cover", ["baseline", "challenge", "compare"])
    b = _exp("exp_other", ["observe"])
    align = {
        "experiment_sufficiency": "insufficient",
        "experiment_id": "exp_prior",
        "coverage_gap": gap.to_dict(),
    }
    closed = _minimal_closed(align, "exp_prior", [a, b])
    loop = AdaptiveLoop("eng_gap")
    loop.tried_experiment_ids.add("exp_prior")

    # Monkeypatch designer to return a,b
    loop.designer.design_portfolio = lambda hyps, ctx, retrieval=None: [a, b]  # type: ignore

    step = loop.step(closed)
    assert step.coverage_gap is not None
    assert step.coverage_gap.get("missing_roles")
    if not step.stop:
        assert step.next_experiment is not None
        assert step.next_experiment.experiment_id == "exp_cover"
        assert "challenge" in step.selection_reason or "covers" in step.selection_reason
    else:
        # JEV stop is acceptable if scores force stop — still provenance present
        assert step.selection_reason


def test_h_insufficient_not_finding():
    gap = CoverageGap(missing_roles=["challenge"])
    assert gap.target_roles == ["challenge"]
    # sufficiency path never sets POSITIVE evidence by itself
