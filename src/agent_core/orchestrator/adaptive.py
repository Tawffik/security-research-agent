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
from agent_core.research.branch import BranchManager
from agent_core.schemas.research import HypothesisStatus


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
    branch_id: str = ""
    parent_branch_id: str = ""
    backtracked: bool = False
    active_hypothesis_ids: list[str] = field(default_factory=list)
    rejected_hypothesis_ids: list[str] = field(default_factory=list)

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
            "branch_id": self.branch_id,
            "parent_branch_id": self.parent_branch_id,
            "backtracked": self.backtracked,
            "active_hypothesis_ids": list(self.active_hypothesis_ids),
            "rejected_hypothesis_ids": list(self.rejected_hypothesis_ids),
        }


class AdaptiveLoop:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self.jev = JEV(engagement_id)
        self.designer = ExperimentDesigner(engagement_id)
        self.opp_engine = OpportunityEngine(engagement_id)
        self.tried_experiment_ids: set[str] = set()
        self.branches = BranchManager(episode_id=engagement_id)
        self._root_branch_id: str = ""

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
            # Contextual retrieval signal (ranking only — not execution permission)
            notes.append(
                f"retrieval_context evidence_gap_roles={gap.target_roles}"
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
            hyps = list(plan.hypotheses or [])
            rejected_ids = []
            active_ids = []
            for h in hyps:
                st = h.status.value if hasattr(h.status, "value") else str(h.status)
                stmt = (h.statement or "").lower()
                if st in ("rejected",) or (
                    st == "supported" and ("null" in stmt or "not a vulnerability" in stmt)
                ):
                    # supported null is viable; claim hyps with negative evidence → reject list if rejected
                    if st == "rejected":
                        rejected_ids.append(h.hypothesis_id)
                if st in ("open", "supported"):
                    active_ids.append(h.hypothesis_id)
                if st == "open" and h.hypothesis_id not in active_ids:
                    active_ids.append(h.hypothesis_id)

            # From hypothesis_updates on closed result
            for u in list(getattr(closed, "hypothesis_updates", None) or []):
                hid = getattr(u, "hypothesis_id", None) or (u.get("hypothesis_id") if isinstance(u, dict) else None)
                reason = getattr(u, "reason", None) or (u.get("reason") if isinstance(u, dict) else "")
                if hid and reason and "negative" in str(reason):
                    if hid not in rejected_ids and "null" not in str(reason):
                        rejected_ids.append(str(hid))

            # Open root branch once
            if not self._root_branch_id:
                root = self.branches.open_branch(
                    hypothesis_ids=[h.hypothesis_id for h in hyps[:5]],
                )
                self._root_branch_id = root.branch_id
            if current_exp_id:
                self.branches.record_experiment(self._root_branch_id, current_exp_id)

            alt_hyps = [
                h for h in hyps
                if h.hypothesis_id not in rejected_ids
                and (h.status.value if hasattr(h.status, "value") else str(h.status))
                in ("open", "supported")
            ]
            # Prefer null / alternate explanations when primary claim was rejected
            alt_hyps_sorted = sorted(
                alt_hyps,
                key=lambda h: (
                    0 if "null" in (h.statement or "").lower() or "intended" in (h.statement or "").lower() else 1
                ),
            )

            if alt_hyps_sorted:
                nb = self.branches.backtrack(
                    self._root_branch_id,
                    new_hypothesis_ids=[h.hypothesis_id for h in alt_hyps_sorted],
                )
                experiments = self.designer.design_portfolio(
                    alt_hyps_sorted, plan.target_context, retrieval=getattr(self, "_retrieval", None)
                )
                candidates = [
                    e for e in experiments if e.experiment_id not in self.tried_experiment_ids
                ]
                if not candidates:
                    notes.append("backtrack: no discriminating experiment left on alternate branch")
                    return AdaptiveStepResult(
                        prior_outcome="rejected",
                        stop=True,
                        stop_reason="no_discriminating_experiment",
                        next_action="STOP",
                        reranked_opportunities=ranked,
                        notes=notes,
                        branch_id=nb.branch_id if nb else self._root_branch_id,
                        parent_branch_id=self._root_branch_id,
                        backtracked=bool(nb),
                        active_hypothesis_ids=[h.hypothesis_id for h in alt_hyps_sorted],
                        rejected_hypothesis_ids=list(rejected_ids),
                    )
                next_exp = candidates[0]
                decision = self.jev.choose(candidates, alt_hyps_sorted, budget_remaining_ratio=0.7)
                if decision.decision == DecisionAction.STOP or not candidates:
                    return AdaptiveStepResult(
                        prior_outcome="rejected",
                        stop=True,
                        stop_reason="no_discriminating_experiment",
                        next_action="STOP",
                        decision=decision,
                        reranked_opportunities=ranked,
                        notes=notes + ["JEV stop after backtrack"],
                        branch_id=nb.branch_id if nb else "",
                        parent_branch_id=self._root_branch_id,
                        backtracked=True,
                        active_hypothesis_ids=[h.hypothesis_id for h in alt_hyps_sorted],
                        rejected_hypothesis_ids=list(rejected_ids),
                    )
                if decision.candidate:
                    next_exp = next(
                        (e for e in candidates if e.experiment_id == decision.candidate),
                        candidates[0],
                    )
                notes.append(
                    f"backtrack to branch={nb.branch_id if nb else '?'} "
                    f"active_hyps={[h.hypothesis_id for h in alt_hyps_sorted[:3]]} "
                    f"next_exp={next_exp.experiment_id}"
                )
                return AdaptiveStepResult(
                    prior_outcome="rejected",
                    stop=False,
                    stop_reason="",
                    next_action="EXECUTE_FOLLOWUP",
                    decision=decision,
                    next_experiment=next_exp,
                    reranked_opportunities=ranked,
                    notes=notes,
                    selection_reason="evidence_driven_backtrack",
                    branch_id=nb.branch_id if nb else "",
                    parent_branch_id=self._root_branch_id,
                    backtracked=True,
                    active_hypothesis_ids=[h.hypothesis_id for h in alt_hyps_sorted],
                    rejected_hypothesis_ids=list(rejected_ids),
                )

            # No alternate hypotheses → stop with evidence preserved
            return AdaptiveStepResult(
                prior_outcome="rejected",
                stop=True,
                stop_reason="hypothesis_disproven",
                next_action="STOP",
                reranked_opportunities=ranked,
                notes=notes + ["no alternate hypothesis branch"],
                branch_id=self._root_branch_id,
                backtracked=False,
                rejected_hypothesis_ids=list(rejected_ids),
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
