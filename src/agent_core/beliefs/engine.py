"""
Unknown Engine + Belief State (V2 §11–12).

Tracks what we don't know, what we believe, and contradictions.
No tool execution — pure state management.
"""

from __future__ import annotations

import time
from typing import Optional

from agent_core.schemas.research import Belief, Opportunity, Unknown
from agent_core.schemas.target import TargetContext


class UnknownEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._unknowns: dict[str, Unknown] = {}
        self._counter = 0

    def seed_from_opportunities(
        self, opportunities: list[Opportunity], ctx: TargetContext
    ) -> list[Unknown]:
        created: list[Unknown] = []
        multi = len(ctx.actors) >= 2
        for opp in opportunities:
            if opp.type == "authorization" and multi:
                for res in ctx.resources:
                    if not res.owner_actor_id:
                        continue
                    others = [a for a in ctx.actors if a.actor_id != res.owner_actor_id]
                    if not others:
                        continue
                    u = self._add(
                        question=f"Can {others[0].name} access {res.name} owned by {res.owner_actor_id}?",
                        why_it_matters="Discriminates ownership-bound authorization vs shared/public access",
                        confidence=0.15,
                    )
                    created.append(u)
            if opp.type == "state_violation":
                u = self._add(
                    question="Can refund occur from a non-PAID or terminal state?",
                    why_it_matters="Business-logic / state-machine integrity",
                    confidence=0.2,
                )
                created.append(u)
            if opp.type == "authentication_lifecycle":
                u = self._add(
                    question="Is password-reset token single-use and identity-bound?",
                    why_it_matters="Auth lifecycle invariants",
                    confidence=0.25,
                )
                created.append(u)
        return created

    def _add(self, question: str, why_it_matters: str, confidence: float) -> Unknown:
        self._counter += 1
        uid = f"U{self._counter}"
        u = Unknown(
            unknown_id=uid,
            question=question,
            why_it_matters=why_it_matters,
            confidence=confidence,
        )
        self._unknowns[uid] = u
        return u

    def list_open(self) -> list[Unknown]:
        return list(self._unknowns.values())

    def get(self, unknown_id: str) -> Optional[Unknown]:
        return self._unknowns.get(unknown_id)


class BeliefEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._beliefs: dict[str, Belief] = {}
        self._counter = 0

    def assert_belief(
        self,
        claim: str,
        confidence: float,
        supporting: Optional[list[str]] = None,
        contradicting: Optional[list[str]] = None,
        source: str = "",
    ) -> Belief:
        self._counter += 1
        bid = f"B-{self._counter:03d}"
        b = Belief(
            belief_id=bid,
            claim=claim,
            confidence=max(0.0, min(1.0, confidence)),
            supporting_evidence_ids=list(supporting or []),
            contradicting_evidence_ids=list(contradicting or []),
            source=source,
            last_updated=time.time(),
        )
        self._beliefs[bid] = b
        return b

    def update_confidence(
        self,
        belief_id: str,
        delta: float,
        evidence_id: Optional[str] = None,
        polarity: str = "support",
    ) -> Optional[Belief]:
        b = self._beliefs.get(belief_id)
        if not b:
            return None
        new_conf = max(0.0, min(1.0, b.confidence + delta))
        supporting = list(b.supporting_evidence_ids)
        contradicting = list(b.contradicting_evidence_ids)
        if evidence_id:
            if polarity == "support":
                supporting.append(evidence_id)
            else:
                contradicting.append(evidence_id)
        updated = b.model_copy(
            update={
                "confidence": new_conf,
                "supporting_evidence_ids": supporting,
                "contradicting_evidence_ids": contradicting,
                "last_updated": time.time(),
            }
        )
        self._beliefs[belief_id] = updated
        return updated

    def contradictions(self) -> list[tuple[Belief, Belief]]:
        """Naive pair-wise: same claim stem with opposite confidence extremes."""
        items = list(self._beliefs.values())
        pairs: list[tuple[Belief, Belief]] = []
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                if a.claim == b.claim and abs(a.confidence - b.confidence) > 0.5:
                    pairs.append((a, b))
                if a.contradicting_evidence_ids and set(a.contradicting_evidence_ids) & set(
                    b.supporting_evidence_ids
                ):
                    pairs.append((a, b))
        return pairs

    def list_all(self) -> list[Belief]:
        return list(self._beliefs.values())
