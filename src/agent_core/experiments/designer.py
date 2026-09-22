"""
Experiment Designer (V2 §15–16).

Produces the minimum discriminating experiment for a hypothesis.
No live execution — designs only.
"""

from __future__ import annotations

from agent_core.schemas.research import Experiment, ExperimentStatus, Hypothesis
from agent_core.schemas.target import TargetContext


class ExperimentDesigner:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0
        self._cache: dict[str, Experiment] = {}

    def design(self, hypothesis: Hypothesis, ctx: TargetContext) -> Experiment:
        key = f"{hypothesis.hypothesis_id}:{hypothesis.statement[:40]}"
        if key in self._cache:
            cached = self._cache[key]
            return cached.model_copy(update={"status": ExperimentStatus.CACHED})

        stmt = hypothesis.statement.lower()
        if "ownership" in stmt or "bypass" in stmt:
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
        self, hypotheses: list[Hypothesis], ctx: TargetContext
    ) -> list[Experiment]:
        return [self.design(h, ctx) for h in hypotheses if h.status.value == "open"]

    def _ownership_diff(self, h: Hypothesis, ctx: TargetContext) -> Experiment:
        owners = [r for r in ctx.resources if r.owner_actor_id]
        actors = ctx.actors
        target_path = "/api/orders/{id}"
        for ep in ctx.endpoints:
            if "{id}" in ep.path and "order" in ep.path.lower():
                target_path = f"{ep.method} {ep.path}"
                break
        res_name = owners[0].name if owners else "object-id"
        return self._make(
            hypothesis_id=h.hypothesis_id,
            description=(
                f"Cross-identity access: request {target_path} for {res_name} "
                f"as owner, then replay as non-owner; compare status and body ownership markers"
            ),
            expected_observation="Non-owner receives 403/404; owner receives 200 with resource",
            discriminator="status code + ownership field under two authenticated identities",
            required_evidence=[
                "identity_a_request",
                "identity_b_request",
                "response_diff",
                "ownership_proof",
            ],
            stop_condition="scope_violation OR destructive_mutation OR both identities return identical authorized content with shared ACL",
            risk=0.25,
            cost=0.2,
            information_gain=0.9,
            tool_names=["authenticated_http_request", "diff_response_by_identity"],
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
            description=f"Passive observation supporting or rejecting: {h.statement[:80]}",
            expected_observation="Evidence consistent with primary explanation or an alternative",
            discriminator="qualitative match to alternatives",
            required_evidence=["observation_log"],
            stop_condition="low_information_gain",
            risk=0.1,
            cost=0.1,
            information_gain=0.3,
            tool_names=[],
            skill_names=[],
        )

    def _make(self, hypothesis_id: str, **kwargs) -> Experiment:
        self._counter += 1
        return Experiment(
            experiment_id=f"experiment_{self._counter}",
            hypothesis_id=hypothesis_id,
            status=ExperimentStatus.PLANNED,
            **kwargs,
        )
