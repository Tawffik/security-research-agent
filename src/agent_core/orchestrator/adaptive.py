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
from agent_core.knowledge.retrieve import KnowledgeRetriever
from agent_core.orchestrator.closed_loop import ClosedLoopResult
from agent_core.orchestrator.experiment_alignment import (
    CoverageGap,
    prefer_gap_covering_candidates,
)
from agent_core.schemas.research import Decision, DecisionAction, Experiment, Opportunity
from agent_core.target.opportunity import OpportunityEngine


@dataclass
class AdaptiveStepResult:
    prior_outcome: str
    stop: bool
    stop_reason: str
    next_action: str  # STOP | EXECUTE_VARIANT | EXECUTE_FOLLOWUP
    decision: Optional[Decision] = None
    next_experiment: Optional[Experiment] = None
    reranked_opportunities: list[Opportunity] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    coverage_gap: Optional[dict[str, Any]] = None
    selection_reason: str = ""

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
            "coverage_gap": self.coverage_gap,
            "selection_reason": self.selection_reason,
        }


class AdaptiveLoop:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self.jev = JEV(engagement_id)
        self.designer = ExperimentDesigner(engagement_id)
        self.opp_engine = OpportunityEngine(engagement_id)
        self.tried_experiment_ids: set[str] = set()

    def step(self, closed: ClosedLoopResult) -> AdaptiveStepResult:
        notes: list[str] = []
        plan = closed.plan
        ranked = list(self.opp_engine.rank(plan.target_context, plan.target_graph))
        notes.append(f"re-ranked {len(ranked)} opportunities")

        # M6: coverage-driven sufficiency (not a vulnerability verdict)
        align = closed.experiment_alignment or {}
        sufficiency = align.get("experiment_sufficiency") or "sufficient"
        current_exp_id = closed.selected_experiment_id or align.get("experiment_id")
        if current_exp_id:
            self.tried_experiment_ids.add(current_exp_id)
        notes.append(f"experiment_sufficiency={sufficiency}")

        if sufficiency in ("insufficient", "ambiguous") and closed.scope_allowed:
            notes.append(
                f"M6.6: experiment {sufficiency} — not a finding; gap-aware follow-up"
            )
            gap_dict = align.get("coverage_gap") or {}
            gap = CoverageGap(
                prior_experiment_id=gap_dict.get("prior_experiment_id") or current_exp_id,
                missing_step_ids=list(gap_dict.get("missing_step_ids") or []),
                ambiguous_step_ids=list(gap_dict.get("ambiguous_step_ids") or []),
                missing_roles=list(gap_dict.get("missing_roles") or []),
                ambiguous_roles=list(gap_dict.get("ambiguous_roles") or []),
            )
            hyps = list(plan.hypotheses or [])
            retrieval = getattr(self, "_retrieval", None)
            experiments = self.designer.design_portfolio(
                hyps, plan.target_context, retrieval=retrieval
            )
            candidates = [
                e
                for e in experiments
                if e.experiment_id not in self.tried_experiment_ids
            ]
            if not candidates:
                return AdaptiveStepResult(
                    prior_outcome=f"coverage_{sufficiency}",
                    stop=True,
                    stop_reason=f"coverage_{sufficiency}_no_followup",
                    next_action="STOP",
                    reranked_opportunities=ranked,
                    notes=notes + ["no valid follow-up experiment after coverage gap"],
                    coverage_gap=gap.to_dict(),
                    selection_reason="no_untried_candidates",
                )
            covering, other = prefer_gap_covering_candidates(candidates, gap)
            # Prefer covering for JEV; if none, fallback to all candidates
            jev_pool = covering if covering else candidates
            selection_reason = (
                f"covers missing/ambiguous roles {gap.target_roles}"
                if covering
                else "no_gap_covering_candidate_fallback"
            )
            notes.append(
                f"gap_roles={gap.target_roles} covering={len(covering)} other={len(other)}"
            )
            decision = self.jev.choose(
                jev_pool, hyps, budget_remaining_ratio=0.8
            )
            if decision.decision == DecisionAction.STOP or not decision.candidate:
                return AdaptiveStepResult(
                    prior_outcome=f"coverage_{sufficiency}",
                    stop=True,
                    stop_reason=f"coverage_{sufficiency}_jev_stop",
                    next_action="STOP",
                    decision=decision,
                    reranked_opportunities=ranked,
                    notes=notes,
                    coverage_gap=gap.to_dict(),
                    selection_reason=selection_reason + "|jev_stop",
                )
            next_exp = next(
                (e for e in jev_pool if e.experiment_id == decision.candidate),
                jev_pool[0],
            )
            if next_exp.experiment_id == current_exp_id:
                return AdaptiveStepResult(
                    prior_outcome=f"coverage_{sufficiency}",
                    stop=True,
                    stop_reason="coverage_same_experiment_blocked",
                    next_action="STOP",
                    decision=decision,
                    next_experiment=next_exp,
                    reranked_opportunities=ranked,
                    notes=notes + ["refused to re-select same experiment"],
                    coverage_gap=gap.to_dict(),
                    selection_reason="same_experiment_blocked",
                )
            notes.append(
                f"M6.6 follow-up next_experiment_id={next_exp.experiment_id} "
                f"hypothesis_id={next_exp.hypothesis_id} reason={selection_reason}"
            )
            return AdaptiveStepResult(
                prior_outcome=f"coverage_{sufficiency}",
                stop=False,
                stop_reason="",
                next_action="EXECUTE_FOLLOWUP",
                decision=decision,
                next_experiment=next_exp,
                reranked_opportunities=ranked,
                notes=notes,
                coverage_gap=gap.to_dict(),
                selection_reason=selection_reason,
            )


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
            experiments = self.designer.design_portfolio(hyps, plan.target_context, retrieval=getattr(self, '_retrieval', None))
            if not experiments:
                # design from first hypothesis even if status not open
                if hyps:
                    experiments = [self.designer.design(hyps[0], plan.target_context, retrieval=getattr(self, '_retrieval', None))]
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
            # M4: keep identity for closed-loop resolve_selected_experiment compatibility
            notes.append(
                f"M4 provenance next_experiment_id={next_exp.experiment_id} "
                f"hypothesis_id={next_exp.hypothesis_id}"
            )
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
                    next_experiment=next_exp,  # provenance: experiment_id + hypothesis_id on Experiment
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
                next_experiment=next_exp,  # provenance: experiment_id + hypothesis_id on Experiment
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
