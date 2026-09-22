"""
Hypothesis Engine (V2 §13–14).

Maintains a portfolio of competing hypotheses with alternative explanations.
"""

from __future__ import annotations

from typing import Optional

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

    def generate_from_unknowns(
        self,
        unknowns: list[Unknown],
        opportunities: list[Opportunity],
        ctx: TargetContext,
    ) -> list[Hypothesis]:
        created: list[Hypothesis] = []
        authz_opps = [o for o in opportunities if o.type == "authorization"]
        state_opps = [o for o in opportunities if o.type == "state_violation"]

        if authz_opps and len(ctx.actors) >= 2:
            created.append(
                self._add(
                    statement="Ownership bypass: non-owner can access object via identifier mutation",
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
