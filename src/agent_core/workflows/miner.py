"""
Workflow Miner + State Machine (V2 §32–33).

Infers order of operations from endpoint paths and resource states offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agent_core.schemas.target import Endpoint, TargetContext


@dataclass
class Transition:
    from_state: str
    action: str
    to_state: str
    requires: list[str] = field(default_factory=list)


@dataclass
class StateMachine:
    name: str
    states: list[str]
    transitions: list[Transition]
    invalid_candidates: list[str] = field(default_factory=list)


class WorkflowMiner:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id

    def mine(self, ctx: TargetContext) -> list[StateMachine]:
        machines: list[StateMachine] = []
        order_eps = [e for e in ctx.endpoints if "order" in e.path.lower()]
        refund = any("refund" in e.path.lower() for e in ctx.endpoints)
        states_from_resources = sorted(
            {r.state for r in ctx.resources if r.state}
        )
        if order_eps or states_from_resources:
            states = states_from_resources or ["CREATED", "PAID", "SHIPPED", "COMPLETED"]
            if "REFUNDED" not in states and refund:
                states = list(states) + ["REFUNDED"]
            transitions = [
                Transition("CREATED", "pay", "PAID", requires=["owner_or_payment"]),
                Transition("PAID", "ship", "SHIPPED", requires=["owner_or_admin"]),
                Transition("SHIPPED", "complete", "COMPLETED", requires=[]),
            ]
            if refund:
                transitions.append(
                    Transition(
                        "PAID",
                        "refund",
                        "REFUNDED",
                        requires=["owner_or_admin", "amount <= paid_amount"],
                    )
                )
            invalid = [
                "CREATED → REFUND",
                "SHIPPED → MODIFY_PRICE",
                "COMPLETED → SHIP",
            ]
            if refund:
                invalid.append("COMPLETED → REFUND")
            machines.append(
                StateMachine(
                    name="ORDER",
                    states=list(states),
                    transitions=transitions,
                    invalid_candidates=invalid,
                )
            )
        return machines
