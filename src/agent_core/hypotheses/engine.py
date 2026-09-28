"""
Hypothesis Engine (V2 §13–14).

Maintains a portfolio of competing hypotheses with alternative explanations.
"""

from __future__ import annotations

from typing import Any, Optional

from agent_core.knowledge.retrieve import RetrievalResult

from agent_core.schemas.research import (
    AlternativeExplanation,
    Hypothesis,
    HypothesisStatus,
    Opportunity,
    Unknown,
)
from agent_core.schemas.target import TargetContext


class HypothesisEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._portfolio: dict[str, Hypothesis] = {}
        self._counter = 0
        self.last_retrieval: Optional[RetrievalResult] = None
        self.knowledge_refs_by_hyp: dict[str, dict] = {}

    def generate_from_unknowns(
        self,
        unknowns: list[Unknown],
        opportunities: list[Opportunity],
        ctx: TargetContext,
        retrieval: Optional[RetrievalResult] = None,
    ) -> list[Hypothesis]:
        self.last_retrieval = retrieval
        created: list[Hypothesis] = []
        authz_opps = [o for o in opportunities if o.type in ("authorization", "authorization_mutation")]
        mutation_opps = [o for o in opportunities if o.mutation and o.object_surface]
        state_opps = [o for o in opportunities if o.type == "state_violation"]

        if mutation_opps and len(ctx.actors) >= 2:
            created.append(
                self._add(
                    statement=(
                        "Action-level object authorization failure: non-owner can mutate "
                        "(delete/patch) another user's object — not only read it"
                        + (
                            f" [knowledge: patterns={','.join(retrieval.pattern_ids[:3])} "
                            f"procedures={','.join(retrieval.procedure_ids[:3])}]"
                            if retrieval and (retrieval.pattern_ids or retrieval.procedure_ids)
                            else ""
                        )
                    ),
                    primary="Missing ownership check on state-changing object operations",
                    alternatives=[
                        AlternativeExplanation(
                            explanation_id="A_mut_1",
                            description="Mutation is restricted by role rather than ownership (still may be issue)",
                            discriminating_observations=["role claim", "admin-only mutate"],
                        ),
                        AlternativeExplanation(
                            explanation_id="A_mut_2",
                            description="Object is shared ACL allowing both actors to mutate",
                            discriminating_observations=["ACL lists both", "shared workspace"],
                        ),
                    ],
                    confidence=0.6,
                    related_opportunity_ids=[o.opportunity_id for o in mutation_opps[:3]],
                )
            )

        if authz_opps and len(ctx.actors) >= 2:
            created.append(
                self._add(
                    statement=(
                        "Ownership bypass: non-owner can access object via identifier mutation"
                        + (
                            f" [knowledge: patterns={','.join(retrieval.pattern_ids[:3])} "
                            f"procedures={','.join(retrieval.procedure_ids[:3])}]"
                            if retrieval and (retrieval.pattern_ids or retrieval.procedure_ids)
                            else ""
                        )
                    ),
                    primary="Missing server-side ownership check",
                    alternatives=[
                        AlternativeExplanation(
                            explanation_id="A1",
                            description="Resource is intentionally shared between actors",
                            discriminating_observations=[
                                "owner marker in response",
                                "ACL listing both actors",
                            ],
                        ),
                        AlternativeExplanation(
                            explanation_id="A2",
                            description="Role grants broader access than ownership",
                            discriminating_observations=["role claim in token", "role-only endpoint"],
                        ),
                        AlternativeExplanation(
                            explanation_id="A3",
                            description="Endpoint is intentionally public for this object class",
                            discriminating_observations=["auth_required false", "public docs"],
                        ),
                    ],
                    confidence=0.55,
                    related_unknown_ids=[u.unknown_id for u in unknowns if "access" in u.question.lower()],
                    related_opportunity_ids=[o.opportunity_id for o in authz_opps[:3]],
                )
            )
            created.append(
                self._add(
                    statement="Role boundary issue: lower privilege role reaches admin-only action",
                    primary="Missing function-level authorization",
                    alternatives=[
                        AlternativeExplanation(
                            explanation_id="A4",
                            description="Action is allowed for this role by design",
                        ),
                    ],
                    confidence=0.35,
                    related_opportunity_ids=[o.opportunity_id for o in authz_opps[:2]],
                )
            )

        if state_opps:
            created.append(
                self._add(
                    statement="State violation: refund allowed from non-PAID or terminal state",
                    primary="Missing state-transition guard",
                    alternatives=[
                        AlternativeExplanation(
                            explanation_id="A5",
                            description="Refund from that state is a documented business rule",
                        ),
                    ],
                    confidence=0.5,
                    related_opportunity_ids=[o.opportunity_id for o in state_opps],
                )
            )

        # Merge knowledge-derived alternatives into authz hypotheses
        k_alts = self._knowledge_alts(retrieval)
        if k_alts and retrieval:
            enriched = []
            for h in created:
                if "ownership" in h.statement.lower() or "mutat" in h.statement.lower() or "knowledge:" in h.statement:
                    primary = h.primary_explanation
                    if retrieval.patterns:
                        primary = (
                            f"{retrieval.patterns[0].record_id}: "
                            f"{(retrieval.patterns[0].abstraction or primary)[:180]}"
                        )
                    h = h.model_copy(
                        update={
                            "alternatives": k_alts + list(h.alternatives),
                            "primary_explanation": primary,
                        }
                    )
                    self.knowledge_refs_by_hyp[h.hypothesis_id] = {
                        "pattern_ids": list(retrieval.pattern_ids),
                        "procedure_ids": list(retrieval.procedure_ids),
                        "signals": list(retrieval.query_signals),
                    }
                    self._portfolio[h.hypothesis_id] = h
                enriched.append(h)
            created = enriched

        # Always keep a low-confidence "intended behavior" branch for skepticism
        created.append(
            self._add(
                statement="Observed access patterns are intended product behavior",
                primary="No vulnerability — design allows this",
                alternatives=[],
                confidence=0.2,
            )
        )
        return created

    def _add(
        self,
        statement: str,
        primary: str,
        alternatives: list[AlternativeExplanation],
        confidence: float,
        related_unknown_ids: Optional[list[str]] = None,
        related_opportunity_ids: Optional[list[str]] = None,
    ) -> Hypothesis:
        self._counter += 1
        hid = f"H{self._counter}"
        h = Hypothesis(
            hypothesis_id=hid,
            statement=statement,
            primary_explanation=primary,
            alternatives=alternatives,
            confidence=confidence,
            status=HypothesisStatus.OPEN,
            related_unknown_ids=list(related_unknown_ids or []),
            related_opportunity_ids=list(related_opportunity_ids or []),
        )
        self._portfolio[hid] = h
        return h


    def _knowledge_alts(self, retrieval: Optional[RetrievalResult]) -> list[AlternativeExplanation]:
        if not retrieval or not retrieval.competing_explanations:
            return []
        return [
            AlternativeExplanation(
                explanation_id=f"K{i}",
                description=text,
                discriminating_observations=["knowledge_derived"],
            )
            for i, text in enumerate(retrieval.competing_explanations[:6], start=1)
        ]

    def portfolio(self) -> list[Hypothesis]:
        return sorted(self._portfolio.values(), key=lambda h: h.confidence, reverse=True)

    def open_only(self) -> list[Hypothesis]:
        return [h for h in self.portfolio() if h.status == HypothesisStatus.OPEN]

    def update_status(self, hypothesis_id: str, status: HypothesisStatus) -> Optional[Hypothesis]:
        h = self._portfolio.get(hypothesis_id)
        if not h:
            return None
        updated = h.model_copy(update={"status": status})
        self._portfolio[hypothesis_id] = updated
        return updated

    def adjust_confidence(self, hypothesis_id: str, new_confidence: float) -> Optional[Hypothesis]:
        h = self._portfolio.get(hypothesis_id)
        if not h:
            return None
        updated = h.model_copy(update={"confidence": max(0.0, min(1.0, new_confidence))})
        self._portfolio[hypothesis_id] = updated
        return updated
