"""Gate 3 — generic knowledge contracts, discrimination, hypothesis update."""

from pathlib import Path

from agent_core.experiments.discriminate import (
    select_minimum_discriminating,
    score_discriminating_power,
)
from agent_core.hypotheses.update import apply_evidence_to_hypotheses
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.retrieve import KnowledgeRetriever
from agent_core.orchestrator.closed_loop import ClosedLoopRunner, default_idor_lab_scenario
from agent_core.orchestrator.research_loop import ResearchLoop
from agent_core.research.contracts import contract_from_retrieval, experiment_contract_view
from agent_core.schemas.research import Experiment, ExperimentStatus, Hypothesis, HypothesisStatus

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_contract_from_retrieval_generic():
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

    ctx = TargetContext(
        engagement_id="e",
        primary_host="api.acme-demo.test",
        actors=[
            Actor(actor_id="a", name="a", actor_type=ActorType.USER),
            Actor(actor_id="b", name="b", actor_type=ActorType.USER),
        ],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/api/x/{id}")],
    )
    ret = r.retrieve_for_context(ctx, [], methodology="authorization")
    c = contract_from_retrieval(ret, property_hint="authorization")
    assert c.procedure_ids or c.pattern_ids
    assert c.property


def test_discrimination_prefers_baseline_challenge_and_avoids_prior():
    h = Hypothesis(hypothesis_id="h1", statement="ownership missing", status=HypothesisStatus.OPEN)
    e1 = Experiment(
        experiment_id="exp_prior",
        hypothesis_id="h1",
        description="old",
        status=ExperimentStatus.PLANNED,
        information_gain=0.9,
        cost=0.1,
        discriminator="d",
        required_evidence=["x"],
    )
    e2 = Experiment(
        experiment_id="exp_new",
        hypothesis_id="h1",
        description="new",
        status=ExperimentStatus.PLANNED,
        information_gain=0.7,
        cost=0.2,
        discriminator="d2",
        required_evidence=["gap"],
    )
    # attach fake steps via attribute if model allows extra - use model fields only
    best, scores = select_minimum_discriminating(
        [e1, e2],
        [h],
        prior_experiment_ids=["exp_prior"],
        evidence_gaps=["gap"],
    )
    assert best is not None
    assert best.experiment_id == "exp_new"
    assert score_discriminating_power(e1, hypotheses=[h], prior_experiment_ids=["exp_prior"]).score < \
        score_discriminating_power(e2, hypotheses=[h], evidence_gaps=["gap"]).score


def test_negative_evidence_updates_null_not_secure_claim():
    claim = Hypothesis(
        hypothesis_id="h_claim",
        statement="Object ownership bypass exists",
        status=HypothesisStatus.OPEN,
    )
    null = Hypothesis(
        hypothesis_id="h_null",
        statement="Null: observed access is intended or not a vulnerability",
        status=HypothesisStatus.OPEN,
    )
    recs = apply_evidence_to_hypotheses(
        [claim, null], polarity="negative", evidence_ids=["e1"]
    )
    by = {r.hypothesis_id: r for r in recs}
    assert by["h_null"].new_status == "supported"
    assert by["h_claim"].reason.startswith("negative_evidence")


def test_research_loop_discrimination_wired():
    loop = ResearchLoop(engagement_id="g3_disc")
    loop.preferred_methodology = "authorization"
    result = loop.run_from_recon_file(FIXTURE)
    assert result.experiments
    assert loop.last_knowledge_contract is not None
    assert loop.last_discrimination_scores


def test_closed_loop_hypothesis_updates():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="g3_upd").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    assert hasattr(r, "hypothesis_updates")
    assert isinstance(r.hypothesis_updates, list)


def test_methodology_substitution_same_engine():
    """Same retriever path for different methodologies — no separate engines."""
    r = KnowledgeRetriever(KnowledgeIndex(KROOT).load())
    from agent_core.schemas.target import TargetContext, Actor, ActorType, Endpoint

    ctx = TargetContext(
        engagement_id="e",
        primary_host="api.acme-demo.test",
        actors=[Actor(actor_id="a", name="a", actor_type=ActorType.USER)],
        endpoints=[Endpoint(endpoint_id="e1", method="GET", path="/x")],
    )
    a = r.retrieve_for_context(ctx, [], methodology="authorization")
    b = r.retrieve_for_context(ctx, [], methodology="xss")
    c = r.retrieve_for_context(ctx, [], methodology="ssrf")
    assert type(a) is type(b) is type(c)
    # different top procedures when corpus has them
    if a.procedure_ids and b.procedure_ids:
        assert a.procedure_ids[0] != b.procedure_ids[0] or a.pattern_ids != b.pattern_ids
