"""
Adaptive research step (§92 Second Vertical Slice).

After observation/verification:
  Belief/hypothesis already updated on ClosedLoopResult
  → Opportunity re-ranking
  → JEV: CONTINUE (one next experiment) | STOP

Quality-first: STOP on reject, on no variants, or low gain — never URL spray.
Lab-oriented; not production HTTP or BugBountyCI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from agent_core.decisions.jev import JEV
from agent_core.experiments.designer import ExperimentDesigner
from agent_core.orchestrator.closed_loop import ClosedLoopResult
from agent_core.schemas.research import Decision, DecisionAction, Experiment, Opportunity
from agent_core.target.opportunity import OpportunityEngine


@dataclass
class AdaptiveStepResult:
    prior_outcome: str
    stop: bool
    stop_reason: str
    next_action: str  # STOP | EXECUTE_VARIANT
    decision: Optional[Decision] = None
    next_experiment: Optional[Experiment] = None
    reranked_opportunities: list[Opportunity] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prior_outcome": self.prior_outcome,
            "stop": self.stop,
            "stop_reason": self.stop_reason,
            "next_action": self.next_action,
            "decision": self.decision.model_dump() if self.decision else None,
            "next_experiment_id": self.next_experiment.experiment_id if self.next_experiment else None,
            "reranked_opportunity_ids": [o.opportunity_id for o in self.reranked_opportunities[:5]],
            "notes": list(self.notes),
        }


class AdaptiveLoop:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self.jev = JEV(engagement_id)
        self.designer = ExperimentDesigner(engagement_id)
        self.opp_engine = OpportunityEngine(engagement_id)

    def step(self, closed: ClosedLoopResult) -> AdaptiveStepResult:
        notes: list[str] = []
        plan = closed.plan
        ranked = list(self.opp_engine.rank(plan.target_context, plan.target_graph))
        notes.append(f"re-ranked {len(ranked)} opportunities")

        if not closed.scope_allowed:
            return AdaptiveStepResult(
                prior_outcome="scope_denied",
                stop=True,
                stop_reason="scope_blocked",
                next_action="STOP",
                reranked_opportunities=ranked,
                notes=notes + ["ScopeGuard blocked; adaptive stop"],
            )

        if closed.stop_reason == "hypothesis_disproven" or (
            not closed.referee_accepted and closed.final_status == "rejected"
        ):
            notes.append(
                "negative evidence preserved — do not re-spray equivalent authorization test"
            )
            return AdaptiveStepResult(
                prior_outcome="rejected",
                stop=True,
                stop_reason="hypothesis_disproven",
                next_action="STOP",
                reranked_opportunities=ranked,
                notes=notes,
            )

        if closed.referee_accepted:
            if closed.variants:
                variant_paths = {v.path for v in closed.variants}
                boosted = [
                    o
                    for o in ranked
                    if any(vp in o.target or o.target in vp for vp in variant_paths)
                ]
                rest = [o for o in ranked if o not in boosted]
                ranked = boosted + rest
                notes.append(f"boosted {len(boosted)} opportunities matching variants")

            if not closed.variants:
                return AdaptiveStepResult(
                    prior_outcome="confirmed",
                    stop=True,
                    stop_reason="sufficient_evidence",
                    next_action="STOP",
                    reranked_opportunities=ranked,
                    notes=notes + ["Confirmed with no structural variants — stop"],
                )

            hyps = list(plan.hypotheses or [])
            experiments = self.designer.design_portfolio(hyps, plan.target_context)
            if not experiments:
                # design from first hypothesis even if status not open
                if hyps:
                    experiments = [self.designer.design(hyps[0], plan.target_context)]
            if not experiments:
                return AdaptiveStepResult(
                    prior_outcome="confirmed",
                    stop=True,
                    stop_reason="no_valuable_variants_experiment",
                    next_action="STOP",
                    reranked_opportunities=ranked,
                    notes=notes,
                )

            top_variant = closed.variants[0]
            next_exp = experiments[0]
            for e in experiments:
                desc = (e.description or "").lower()
                if any(
                    p and p in desc
                    for p in top_variant.path.lower().split("/")
                    if p and p not in ("api", "{id}")
                ):
                    next_exp = e
                    break

            decision = self.jev.choose(
                [next_exp],
                hyps or [],
                budget_remaining_ratio=0.8,
            )
            if decision.decision == DecisionAction.STOP:
                return AdaptiveStepResult(
                    prior_outcome="confirmed",
                    stop=True,
                    stop_reason="jev_stop",
                    next_action="STOP",
                    decision=decision,
                    next_experiment=next_exp,
                    reranked_opportunities=ranked,
                    notes=notes,
                )

            notes.append(
                f"next step = single discriminating experiment toward {top_variant.path} "
                f"(not full enumeration)"
            )
            return AdaptiveStepResult(
                prior_outcome="confirmed",
                stop=False,
                stop_reason="",
                next_action="EXECUTE_VARIANT",
                decision=decision,
                next_experiment=next_exp,
                reranked_opportunities=ranked,
                notes=notes,
            )

        return AdaptiveStepResult(
            prior_outcome=closed.final_status or "incomplete",
            stop=True,
            stop_reason=closed.stop_reason or "information_gain_too_low",
            next_action="STOP",
            reranked_opportunities=ranked,
            notes=notes + ["Default adaptive stop"],
        )
