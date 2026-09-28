"""
Hypothesis Engine (V2 §13–14).

Maintains a portfolio of competing hypotheses with alternative explanations.
M3: when RetrievalResult has patterns/procedures, hypothesis families are
selected from knowledge (pattern-driven) rather than only opportunity keywords.
Fallback remains opportunity-driven when knowledge is empty.
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
        self.last_mode: str = "fallback"  # knowledge_driven | fallback

    def generate_from_unknowns(
        self,
        unknowns: list[Unknown],
        opportunities: list[Opportunity],
        ctx: TargetContext,
        retrieval: Optional[RetrievalResult] = None,
    ) -> list[Hypothesis]:
        self.last_retrieval = retrieval
        self._portfolio.clear()
        self._counter = 0
        self.knowledge_refs_by_hyp.clear()

        has_knowledge = bool(
            retrieval
            and (retrieval.patterns or retrieval.procedures or retrieval.cases)
        )
        authz_opps = [
            o for o in opportunities if o.type in ("authorization", "authorization_mutation")
        ]
        mutation_opps = [o for o in opportunities if o.mutation and o.object_surface]
        state_opps = [o for o in opportunities if o.type == "state_violation"]
        multi = len(ctx.actors) >= 2

        if has_knowledge and multi and (authz_opps or mutation_opps):
            self.last_mode = "knowledge_driven"
            created = self._from_knowledge(
                retrieval, unknowns, opportunities, mutation_opps, authz_opps
            )
        else:
            self.last_mode = "fallback"
            created = self._from_opportunities(
                retrieval, unknowns, mutation_opps, authz_opps, state_opps, multi
            )

        # Always skeptical null hypothesis (competing; never a finding)
        created.append(
            self._add(
                statement="Observed access patterns are intended product behavior",
                primary="No vulnerability — design allows this",
                alternatives=[],
                confidence=0.2,
            )
        )
        return created

    def _from_knowledge(
        self,
        retrieval: RetrievalResult,
        unknowns: list[Unknown],
        opportunities: list[Opportunity],
        mutation_opps: list[Opportunity],
        authz_opps: list[Opportunity],
    ) -> list[Hypothesis]:
        """Pattern/procedure-conditioned families + competing explanations."""
        created: list[Hypothesis] = []
        k_alts = self._knowledge_alts(retrieval)
        opp_ids = [o.opportunity_id for o in (mutation_opps or authz_opps)[:3]]
        unk_ids = [u.unknown_id for u in unknowns if "access" in u.question.lower()]

        # Prefer mutation patterns when mutation opportunities exist
        patterns = list(retrieval.patterns)
        if mutation_opps:
            mut_p = [p for p in patterns if "mutation" in [t.lower() for t in p.tags]]
            if mut_p:
                patterns = mut_p + [p for p in patterns if p not in mut_p]

        # Primary vulnerability-side hypothesis from top pattern(s)
        for i, pat in enumerate(patterns[:2]):
            is_mut = "mutation" in [t.lower() for t in pat.tags] or "0003" in pat.record_id
            if is_mut:
                statement = (
                    f"[{pat.record_id}] Action-level object ownership authorization failure: "
                    f"non-owner can mutate another user's object"
                )
                primary = pat.abstraction[:240] or (
                    "Missing ownership check on state-changing object operations"
                )
            else:
                statement = (
                    f"[{pat.record_id}] Ownership / object-level authorization failure: "
                    f"non-owner can access object via controlled identifier"
                )
                primary = pat.abstraction[:240] or "Missing server-side ownership check"

            alts = list(k_alts)
            for j, n in enumerate(pat.not_same_as[:4], start=1):
                alts.append(
                    AlternativeExplanation(
                        explanation_id=f"P{pat.record_id}_{j}",
                        description=n,
                        discriminating_observations=["pattern_not_same_as"],
                    )
                )
            if not alts:
                alts = self._default_authz_alts()

            # Attach related procedure ids into statement for traceability
            related_procs = [
                pr.record_id
                for pr in retrieval.procedures
                if any(
                    rid.upper() in [x.upper() for x in pr.related_ids]
                    or pat.record_id.upper() in pr.raw_excerpt.upper()
                    for rid in [pat.record_id]
                )
            ] or retrieval.procedure_ids[:2]
            statement += (
                f" [knowledge: patterns={pat.record_id}"
                f" procedures={','.join(related_procs[:3])}]"
            )

            h = self._add(
                statement=statement,
                primary=f"{pat.record_id}: {primary}",
                alternatives=alts,
                confidence=0.62 if i == 0 else 0.55,
                related_unknown_ids=unk_ids,
                related_opportunity_ids=opp_ids,
            )
            self.knowledge_refs_by_hyp[h.hypothesis_id] = {
                "pattern_ids": [pat.record_id],
                "procedure_ids": list(related_procs[:3]) or list(retrieval.procedure_ids[:3]),
                "signals": list(retrieval.query_signals),
                "mode": "knowledge_driven",
                "source_pattern": pat.record_id,
            }
            created.append(h)

        # Explicit benign competing hypotheses from competing_explanations (not findings)
        seen = set()
        for i, text in enumerate(retrieval.competing_explanations[:3], start=1):
            key = text.lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            created.append(
                self._add(
                    statement=f"[benign:{i}] {text}",
                    primary="Competing non-vuln explanation from knowledge",
                    alternatives=[],
                    confidence=0.35,
                    related_opportunity_ids=opp_ids,
                )
            )

        return created

    def _from_opportunities(
        self,
        retrieval: Optional[RetrievalResult],
        unknowns: list[Unknown],
        mutation_opps: list[Opportunity],
        authz_opps: list[Opportunity],
        state_opps: list[Opportunity],
        multi: bool,
    ) -> list[Hypothesis]:
        """Legacy/safe opportunity-driven templates when knowledge is missing."""
        created: list[Hypothesis] = []
        if mutation_opps and multi:
            created.append(
                self._add(
                    statement=(
                        "Action-level object ownership authorization failure: non-owner can mutate "
                        "(delete/patch) another user's object — not only read it"
                    ),
                    primary="Missing ownership check on state-changing object operations",
                    alternatives=self._default_authz_alts(mutation=True),
                    confidence=0.6,
                    related_opportunity_ids=[o.opportunity_id for o in mutation_opps[:3]],
                )
            )
        if authz_opps and multi:
            created.append(
                self._add(
                    statement="Ownership bypass: non-owner can access object via identifier mutation",
                    primary="Missing server-side ownership check",
                    alternatives=self._default_authz_alts(),
                    confidence=0.55,
                    related_unknown_ids=[
                        u.unknown_id for u in unknowns if "access" in u.question.lower()
                    ],
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
        return created

    def _default_authz_alts(self, mutation: bool = False) -> list[AlternativeExplanation]:
        if mutation:
            return [
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
            ]
        return [
            AlternativeExplanation(
                explanation_id="A1",
                description="Resource is intentionally shared between actors",
                discriminating_observations=["owner marker in response", "ACL listing both actors"],
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
        ]

    def _knowledge_alts(
        self, retrieval: Optional[RetrievalResult]
    ) -> list[AlternativeExplanation]:
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
        hid = f"hyp_{self._counter}"
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

    def update_status(
        self, hypothesis_id: str, status: HypothesisStatus
    ) -> Optional[Hypothesis]:
        h = self._portfolio.get(hypothesis_id)
        if not h:
            return None
        updated = h.model_copy(update={"status": status})
        self._portfolio[hypothesis_id] = updated
        return updated

    def adjust_confidence(
        self, hypothesis_id: str, new_confidence: float
    ) -> Optional[Hypothesis]:
        h = self._portfolio.get(hypothesis_id)
        if not h:
            return None
        updated = h.model_copy(update={"confidence": max(0.0, min(1.0, new_confidence))})
        self._portfolio[hypothesis_id] = updated
        return updated
