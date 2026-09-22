"""
Offline Research Loop (Sprint 2–6).

Runs: Recon fixture → Target → Opportunities → Unknowns → Beliefs →
Hypotheses → Experiments → JEV decision.

Does NOT call live HTTP or external BugBountyCI. When real recon arrives,
swap RawRecon.from_file(path) for the same adapt() path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from agent_core.beliefs.engine import BeliefEngine, UnknownEngine
from agent_core.decisions.jev import JEV
from agent_core.experiments.designer import ExperimentDesigner
from agent_core.hypotheses.engine import HypothesisEngine
from agent_core.recon.adapter import RawRecon, ReconResultAdapter
from agent_core.schemas.research import Decision, Experiment, Hypothesis, Opportunity
from agent_core.schemas.target import TargetContext, TargetGraph
from agent_core.target.opportunity import OpportunityEngine


@dataclass
class ResearchLoopResult:
    engagement_id: str
    target_context: TargetContext
    target_graph: TargetGraph
    normalized_recon: dict[str, Any]
    opportunities: list[Opportunity]
    unknowns: list
    beliefs: list
    hypotheses: list[Hypothesis]
    experiments: list[Experiment]
    decision: Decision
    summary: str


class ResearchLoop:
    def __init__(self, engagement_id: str = "eng_offline_001"):
        self.engagement_id = engagement_id
        self.adapter = ReconResultAdapter(engagement_id)
        self.opportunity_engine = OpportunityEngine(engagement_id)
        self.unknown_engine = UnknownEngine(engagement_id)
        self.belief_engine = BeliefEngine(engagement_id)
        self.hypothesis_engine = HypothesisEngine(engagement_id)
        self.experiment_designer = ExperimentDesigner(engagement_id)
        self.jev = JEV(engagement_id)

    def run_from_recon_file(self, path: Union[str, Path]) -> ResearchLoopResult:
        recon = RawRecon.from_file(path)
        return self.run(recon)

    def run_from_dict(self, data: dict[str, Any]) -> ResearchLoopResult:
        return self.run(RawRecon.from_dict(data))

    def run(self, recon: RawRecon) -> ResearchLoopResult:
        ctx, graph, normalized = self.adapter.adapt(recon)

        opportunities = self.opportunity_engine.rank(ctx, graph)
        unknowns = self.unknown_engine.seed_from_opportunities(opportunities, ctx)

        # Seed a prior belief from multi-identity presence
        if len(ctx.actors) >= 2 and any(r.owner_actor_id for r in ctx.resources):
            self.belief_engine.assert_belief(
                claim="Object authorization appears ownership-bound (prior from recon structure)",
                confidence=0.45,
                source="recon_structure",
            )

        hypotheses = self.hypothesis_engine.generate_from_unknowns(unknowns, opportunities, ctx)
        experiments = self.experiment_designer.design_portfolio(hypotheses, ctx)
        decision = self.jev.choose(experiments, hypotheses, budget_remaining_ratio=1.0)

        top_h = hypotheses[0].statement if hypotheses else "none"
        summary = (
            f"engagement={self.engagement_id} "
            f"endpoints={len(ctx.endpoints)} actors={len(ctx.actors)} "
            f"opportunities={len(opportunities)} unknowns={len(unknowns)} "
            f"hypotheses={len(hypotheses)} experiments={len(experiments)} "
            f"decision={decision.decision.value} candidate={decision.candidate} "
            f"top_hypothesis={top_h[:60]}"
        )

        return ResearchLoopResult(
            engagement_id=self.engagement_id,
            target_context=ctx,
            target_graph=graph,
            normalized_recon=normalized,
            opportunities=opportunities,
            unknowns=unknowns,
            beliefs=self.belief_engine.list_all(),
            hypotheses=hypotheses,
            experiments=experiments,
            decision=decision,
            summary=summary,
        )
