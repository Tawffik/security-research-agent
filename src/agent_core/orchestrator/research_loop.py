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
from agent_core.knowledge.retrieve import KnowledgeRetriever
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
    def __init__(
        self,
        engagement_id: str = "eng_offline_001",
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
    ):
        self.engagement_id = engagement_id
        self.adapter = ReconResultAdapter(engagement_id)
        self.opportunity_engine = OpportunityEngine(engagement_id)
        self.unknown_engine = UnknownEngine(engagement_id)
        self.belief_engine = BeliefEngine(engagement_id)
        self.hypothesis_engine = HypothesisEngine(engagement_id)
        self.experiment_designer = ExperimentDesigner(engagement_id)
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever()
        self.jev = JEV(engagement_id)
        self.last_retrieval = None
        self.preferred_methodology: str | None = None
        self.evidence_gaps: list[str] = []
        self.prior_experiment_ids: list[str] = []

    def run_from_recon_file(self, path: Union[str, Path]) -> ResearchLoopResult:
        recon = RawRecon.from_file(path)
        return self.run(recon)

    def run_from_dict(self, data: dict[str, Any]) -> ResearchLoopResult:
        return self.run(RawRecon.from_dict(data))

    def run(self, recon: RawRecon) -> ResearchLoopResult:
        ctx, graph, normalized = self.adapter.adapt(recon)

        opportunities = self.opportunity_engine.rank(ctx, graph)
        unknowns = self.unknown_engine.seed_from_opportunities(opportunities, ctx)
        # Gate 2: seed retrieval state from unknowns when not pre-set
        if not self.evidence_gaps and unknowns:
            self.evidence_gaps = [
                (getattr(u, "unknown_id", None) or getattr(u, "statement", "") or "")[:40]
                for u in unknowns[:5]
            ]

        # Seed a prior belief from multi-identity presence
        if len(ctx.actors) >= 2 and any(r.owner_actor_id for r in ctx.resources):
            self.belief_engine.assert_belief(
                claim="Object authorization appears ownership-bound (prior from recon structure)",
                confidence=0.45,
                source="recon_structure",
            )

        # Gate 2: seed retrieval state from target context + loop state
        self.knowledge_retriever._evidence_gaps = list(self.evidence_gaps)
        self.knowledge_retriever._prior_experiment_ids = list(self.prior_experiment_ids)
        self.knowledge_retriever._precondition_hints = [
            "multiple identities" if len(ctx.actors) >= 2 else "single identity",
        ]
        if any(
            "{id}" in (getattr(ep, "path", "") or "").lower()
            or ":id" in (getattr(ep, "path", "") or "").lower()
            for ep in (ctx.endpoints or [])
        ):
            self.knowledge_retriever._precondition_hints.append("object identifier")

        meth = self.preferred_methodology
        if meth:
            retrieval = self.knowledge_retriever.retrieve_for_context(
                ctx, opportunities, methodology=meth
            )
        else:
            retrieval = self.knowledge_retriever.retrieve_for_authz(ctx, opportunities)

        # Negatives → competing explanations (not findings)
        if retrieval and getattr(retrieval, "negatives", None):
            for neg in retrieval.negatives:
                note = f"negative:{neg.record_id}:{neg.title[:80]}"
                if note not in retrieval.competing_explanations:
                    retrieval.competing_explanations.append(note)
                self.knowledge_retriever._negative_evidence_ids = list(
                    getattr(self.knowledge_retriever, "_negative_evidence_ids", None) or []
                ) + [neg.record_id]

        hypotheses = self.hypothesis_engine.generate_from_unknowns(
            unknowns, opportunities, ctx, retrieval=retrieval
        )

        # Second pass: hypothesis-aware retrieval for experiment design
        hyp_tokens: list[str] = []
        for h in hypotheses[:5]:
            stmt = (getattr(h, "statement", "") or "").lower()
            for tok in stmt.replace("/", " ").replace("-", " ").split():
                if len(tok) >= 4 and tok not in hyp_tokens:
                    hyp_tokens.append(tok)
        self.knowledge_retriever._hypothesis_tokens = hyp_tokens[:20]
        if hyp_tokens or getattr(self.knowledge_retriever, "_negative_evidence_ids", None):
            if meth:
                retrieval = self.knowledge_retriever.retrieve_for_context(
                    ctx, opportunities, methodology=meth
                )
            else:
                retrieval = self.knowledge_retriever.retrieve_for_authz(ctx, opportunities)
            if retrieval and getattr(retrieval, "negatives", None):
                for neg in retrieval.negatives:
                    note = f"negative:{neg.record_id}:{neg.title[:80]}"
                    if note not in retrieval.competing_explanations:
                        retrieval.competing_explanations.append(note)

        self.last_retrieval = retrieval
        experiments = self.experiment_designer.design_portfolio(
            hypotheses, ctx, retrieval=retrieval
        )
        decision = self.jev.choose(experiments, hypotheses, budget_remaining_ratio=1.0)

        top_h = hypotheses[0].statement if hypotheses else "none"
        summary = (
            f"engagement={self.engagement_id} "
            f"endpoints={len(ctx.endpoints)} actors={len(ctx.actors)} "
            f"opportunities={len(opportunities)} unknowns={len(unknowns)} "
            f"hypotheses={len(hypotheses)} experiments={len(experiments)} "
            f"decision={decision.decision.value} candidate={decision.candidate} "
            f"top_hypothesis={top_h[:60]} "
            f"knowledge_patterns={retrieval.pattern_ids[:3]} "
            f"knowledge_procedures={retrieval.procedure_ids[:3]}"
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
