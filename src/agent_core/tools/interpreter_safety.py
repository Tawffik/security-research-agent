"""
Interpreter / subprocess safety boundary.

The research agent does NOT expose unrestricted shell, eval, or exec.
Any future interpreter capability must pass Tool Contract + ScopeGuard
and never treat retrieved knowledge as permission.

This module encodes the deny-by-default policy for offline verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_core.tools.capability import FailureClass
from agent_core.tools.failure_policy import next_action_for_failure


FORBIDDEN_PRIMITIVES = frozenset(
    {
        "os.system",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "eval",
        "exec",
        "compile",
        "__import__",
    }
)


@dataclass
class InterpreterDecision:
    allowed: bool
    reason: str
    failure_class: str = ""
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "failure_class": self.failure_class,
            "next_action": self.next_action,
        }


def authorize_interpreter_primitive(
    primitive: str,
    *,
    knowledge_grants_permission: bool = False,
    skill_approved: bool = False,
    explicit_tool_contract: bool = False,
    scope_allowed: bool = False,
) -> InterpreterDecision:
    """
    Deny-by-default. Knowledge approval or skill metadata cannot unlock shell/eval.
    Only an explicit Tool Contract + ScopeGuard path could unlock a future safe subset —
    and that path is not implemented here on purpose.
    """
    name = (primitive or "").strip()
    if knowledge_grants_permission:
        return InterpreterDecision(
            allowed=False,
            reason="knowledge_cannot_grant_interpreter_permission",
            failure_class=FailureClass.AUTHORIZATION_DENIED.value,
            next_action=next_action_for_failure(FailureClass.AUTHORIZATION_DENIED),
        )
    if skill_approved and not (explicit_tool_contract and scope_allowed):
        return InterpreterDecision(
            allowed=False,
            reason="skill_approval_without_tool_contract_and_scope",
            failure_class=FailureClass.CAPABILITY_NOT_EXPOSED.value,
            next_action=next_action_for_failure(FailureClass.CAPABILITY_NOT_EXPOSED),
        )
    if name in FORBIDDEN_PRIMITIVES or name.split(".")[-1] in {"system", "eval", "exec", "Popen"}:
        return InterpreterDecision(
            allowed=False,
            reason="forbidden_interpreter_primitive",
            failure_class=FailureClass.CAPABILITY_NOT_EXPOSED.value,
            next_action=next_action_for_failure(FailureClass.CAPABILITY_NOT_EXPOSED),
        )
    return InterpreterDecision(
        allowed=False,
        reason="interpreter_capability_not_exposed",
        failure_class=FailureClass.CAPABILITY_NOT_EXPOSED.value,
        next_action=next_action_for_failure(FailureClass.CAPABILITY_NOT_EXPOSED),
    )
