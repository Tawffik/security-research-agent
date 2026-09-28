"""
Experiment Designer (V2 §15–16).

Produces the minimum discriminating experiment for a hypothesis.
M1: when KnowledgeRetriever provides a procedure, experiment steps/discriminator
come from that procedure (provenance-bearing), not only keyword templates.
"""

from __future__ import annotations

from typing import Optional

from agent_core.knowledge.retrieve import RetrievalResult
from agent_core.schemas.research import (
    Experiment,
    ExperimentStatus,
    ExperimentStep,
    ExperimentStepRole,
    Hypothesis,
)
from agent_core.schemas.target import TargetContext



def _role_from_step_text(text: str) -> ExperimentStepRole:
    low = text.lower()
    if any(x in low for x in ("as owner", "own object key", "baseline:", "actor's own", "a mutates a")):
        return ExperimentStepRole.BASELINE
    if any(x in low for x in ("non-owner", "non owned", "substitute key", "as b ", "b mutates", "challenge")):
        return ExperimentStepRole.CHALLENGE
    if any(x in low for x in ("compare", "discriminator:", "diff")):
        return ExperimentStepRole.COMPARE
    return ExperimentStepRole.OBSERVE


def steps_from_procedure(proc_id: str, step_texts: list[str]) -> list[ExperimentStep]:
    out: list[ExperimentStep] = []
    for i, text in enumerate(step_texts, start=1):
        out.append(
            ExperimentStep(
                step_id=f"{proc_id}-S{i:02d}",
                order=i,
                role=_role_from_step_text(text),
                text=text,
            )
        )
    return out

class ExperimentDesigner:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0
        self._cache: dict[str, Experiment] = {}
        self.last_retrieval: Optional[RetrievalResult] = None
        self.last_procedure_ids: list[str] = []

    def design(
        self,
        hypothesis: Hypothesis,
        ctx: TargetContext,
        retrieval: Optional[RetrievalResult] = None,
    ) -> Experiment:
        self.last_retrieval = retrieval
        mode = "k" if (retrieval and retrieval.procedures) else "f"
        key = f"{hypothesis.hypothesis_id}:{mode}:{hypothesis.statement[:40]}"
        if key in self._cache:
            cached = self._cache[key]
            return cached.model_copy(update={"status": ExperimentStatus.CACHED})

        # Prefer procedure-driven design when knowledge hit exists
        if retrieval and retrieval.procedures:
            exp = self._from_procedure(hypothesis, ctx, retrieval)
            self._cache[key] = exp
            return exp

        stmt = hypothesis.statement.lower()
        # Secondary path: still classify by hypothesis content for non-knowledge cases
        # (state/role) — not a new "if idor" knowledge substitute when retrieval is empty.
        if any(
            k in stmt
            for k in (
                "mutat",
                "delete",
                "patch",
                "modify object",
                "action-level",
                "state-chang",
            )
        ):
            exp = self._mutation_ownership(hypothesis, ctx)
        elif "ownership" in stmt or "bypass" in stmt:
            exp = self._ownership_diff(hypothesis, ctx)
        elif "role boundary" in stmt or "function-level" in stmt:
            exp = self._role_diff(hypothesis, ctx)
        elif "state violation" in stmt or "refund" in stmt:
            exp = self._state_transition(hypothesis, ctx)
        else:
            exp = self._generic_observe(hypothesis)

        self._cache[key] = exp
        return exp

    def design_portfolio(
        self,
        hypotheses: list[Hypothesis],
        ctx: TargetContext,
        retrieval: Optional[RetrievalResult] = None,
    ) -> list[Experiment]:
        return [
            self.design(h, ctx, retrieval=retrieval)
            for h in hypotheses
            if h.status.value == "open"
        ]

    def _from_procedure(
        self,
        h: Hypothesis,
        ctx: TargetContext,
        retrieval: RetrievalResult,
    ) -> Experiment:
        stmt = h.statement.lower()
        procs = list(retrieval.procedures)

        # Prefer procedure referenced by pattern id in hypothesis statement
        for pat_id in retrieval.pattern_ids:
            if pat_id.lower() in stmt:
                matched = [
                    p for p in procs
                    if pat_id.upper() in (p.raw_excerpt or "").upper()
                    or any(pat_id.upper() == r.upper() for r in p.related_ids)
                ]
                if matched:
                    procs = matched + [p for p in procs if p not in matched]
                break

        if any(k in stmt for k in ("mutat", "delete", "patch", "action-level")):
            mut = [p for p in procs if "mutation" in [t.lower() for t in p.tags] or "0003" in p.record_id]
            if mut:
                procs = mut + [p for p in procs if p not in mut]

        proc = procs[0]
        self.last_procedure_ids = [p.record_id for p in procs[:3]]
        structured_steps = steps_from_procedure(
            proc.record_id, list(proc.experiment_steps or [])
        )

        steps = list(proc.experiment_steps) if proc.experiment_steps else [
            "Owner baseline request",
            "Non-owner same object request",
            "Compare status and sensitive fields",
        ]
        evidence = list(proc.evidence_required) if proc.evidence_required else [
            "identity_a_request",
            "identity_b_request",
            "response_diff",
            "ownership_proof",
        ]
        stops = list(proc.stop_conditions) if proc.stop_conditions else [
            "scope_violation",
            "evidence_sufficient",
            "equivalent experiment cached",
        ]
        # Knowledge-conditioned: require procedure-listed evidence, not only defaults
        if proc.evidence_required:
            evidence = list(proc.evidence_required)[:8]
        if proc.stop_conditions:
            stops = list(proc.stop_conditions)[:4]

        target_path = self._pick_path(ctx, mutation="mutat" in stmt or "delete" in stmt)
        pattern_note = (
            f" patterns={','.join(retrieval.pattern_ids[:2])}"
            if retrieval.pattern_ids
            else ""
        )
        description = (
            f"Procedure-driven experiment [{proc.record_id}]: "
            + " → ".join(steps[:4])
            + f" on {target_path}."
            + f" Provenance: {proc.path}.{pattern_note}"
            + f" EvidenceReq={','.join(evidence[:4])}"
        )
        discriminator = (
            f"procedure:{proc.record_id}|steps:{len(steps)}|"
            + (steps[1] if len(steps) > 1 else steps[0])
            + f"|evidence:{','.join(evidence[:3])}"
        )
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description=description,
            expected_observation=(
                "Non-owner denied or lacks private owner-bound fields; "
                "or private fields present under non-owner (violation path)"
            ),
            discriminator=discriminator,
            required_evidence=evidence[:8],
            stop_condition=" OR ".join(stops[:4]),
            risk=0.3 if "mutat" not in stmt else 0.55,
            cost=0.25 if "mutat" not in stmt else 0.35,
            information_gain=0.93,
            tool_names=["authenticated_http_request", "diff_response_by_identity"],
            skill_names=["authz-idor-analysis"],
            steps=structured_steps,
        )

    def _pick_path(self, ctx: TargetContext, mutation: bool = False) -> str:
        for ep in ctx.endpoints:
            if mutation and ep.method.upper() in ("DELETE", "PATCH", "PUT"):
                if "{id}" in ep.path or "id" in (ep.parameters or []):
                    return f"{ep.method} {ep.path}"
        for ep in ctx.endpoints:
            if "{id}" in ep.path or "order" in ep.path.lower():
                return f"{ep.method} {ep.path}"
        return "GET /api/orders/{id}"

    def _ownership_diff(self, h: Hypothesis, ctx: TargetContext) -> Experiment:
        target_path = self._pick_path(ctx, mutation=False)
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description=(
                f"Cross-identity access: request {target_path} as owner, then replay as non-owner; "
                f"compare status and body ownership markers"
            ),
            expected_observation="Non-owner receives 403/404; owner receives 200 with resource",
            discriminator="status code + ownership field under two authenticated identities",
            required_evidence=[
                "identity_a_request",
                "identity_b_request",
                "response_diff",
                "ownership_proof",
            ],
            stop_condition=(
                "scope_violation OR destructive_mutation OR "
                "both identities return identical authorized content with shared ACL"
            ),
            risk=0.25,
            cost=0.2,
            information_gain=0.9,
            tool_names=["authenticated_http_request", "diff_response_by_identity"],
            skill_names=["authz-idor-analysis"],
        )

    def _mutation_ownership(self, h: Hypothesis, ctx: TargetContext) -> Experiment:
        target_path = self._pick_path(ctx, mutation=True)
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description=(
                f"Action-level object authz: as non-owner, attempt one mutating call "
                f"({target_path}) on owner's object; verify side effect (state change), "
                f"not HTTP status alone"
            ),
            expected_observation=(
                "Non-owner mutate denied AND owner object unchanged; "
                "or mutate succeeds with object altered (finding path)"
            ),
            discriminator="before/after object state under two identities",
            required_evidence=[
                "identity_owner_baseline_state",
                "identity_attacker_mutate_request",
                "post_state_or_absence",
                "ownership_proof",
            ],
            stop_condition=(
                "scope_violation OR risk_blocks_destructive OR "
                "side_effect_proven OR solid_denial_with_unchanged_state"
            ),
            risk=0.55,
            cost=0.35,
            information_gain=0.92,
            tool_names=["authenticated_http_request", "observe_object_state"],
            skill_names=["authz-idor-analysis"],
        )

    def _role_diff(self, h: Hypothesis, ctx: TargetContext) -> Experiment:
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description="Replay sensitive action under lower-privilege role vs admin role",
            expected_observation="Lower role blocked; admin allowed",
            discriminator="authorization decision differs by role claim only",
            required_evidence=["role_a_response", "role_b_response"],
            stop_condition="out_of_scope OR approval_required",
            risk=0.35,
            cost=0.3,
            information_gain=0.7,
            tool_names=["authenticated_http_request"],
            skill_names=["authz-idor-analysis"],
        )

    def _state_transition(self, h: Hypothesis, ctx: TargetContext) -> Experiment:
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description="Attempt refund on order in SHIPPED/COMPLETED state as owner",
            expected_observation="Rejected transition (4xx) if invariant holds",
            discriminator="state before/after + refund acceptance",
            required_evidence=["pre_state", "refund_response", "post_state"],
            stop_condition="destructive side effect beyond refund path",
            risk=0.5,
            cost=0.4,
            information_gain=0.75,
            tool_names=["authenticated_http_request"],
            skill_names=[],
        )

    def _generic_observe(self, h: Hypothesis) -> Experiment:
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description=f"Observe endpoint behavior for hypothesis: {h.statement[:80]}",
            expected_observation="Record status and body markers",
            discriminator="baseline observation only",
            required_evidence=["response"],
            stop_condition="scope_violation",
            risk=0.2,
            cost=0.15,
            information_gain=0.4,
            tool_names=["authenticated_http_request"],
            skill_names=[],
        )

    def _make(self, **kwargs) -> Experiment:
        self._counter += 1
        return Experiment(
            experiment_id=f"exp_{self._counter}",
            status=ExperimentStatus.PLANNED,
            **kwargs,
        )
