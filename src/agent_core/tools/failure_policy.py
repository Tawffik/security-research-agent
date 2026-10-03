"""
Map FailureClass → bounded next research action (offline policy).

Does not grant execution permission. Guides AdaptiveLoop / JEV only.
"""

from __future__ import annotations

from agent_core.tools.capability import FailureClass


# suggested_action values: try_alternative | backtrack | defer | block | stop | fix_precondition
FAILURE_NEXT_ACTION: dict[str, str] = {
    FailureClass.PLANNING_ERROR.value: "fix_precondition",
    FailureClass.PRECONDITION_MISSING.value: "fix_precondition",
    FailureClass.TOOL_FAILURE.value: "try_alternative",
    FailureClass.AUTH_STATE_MISSING.value: "defer",
    FailureClass.CAPABILITY_NOT_EXPOSED.value: "block",
    FailureClass.OBSERVATION_FAILURE.value: "try_alternative",
    FailureClass.INTERPRETATION_ERROR.value: "backtrack",
    FailureClass.DISCRIMINATION_FAILURE.value: "try_alternative",
    FailureClass.VERIFICATION_FAILURE.value: "backtrack",
    FailureClass.BUDGET_EXHAUSTION.value: "stop",
    FailureClass.SCOPE_BLOCK.value: "block",
    FailureClass.ENVIRONMENT_FAILURE.value: "defer",
    FailureClass.AUTHORIZATION_DENIED.value: "block",
    FailureClass.UNKNOWN.value: "try_alternative",
}


def next_action_for_failure(failure_class: str | FailureClass) -> str:
    key = failure_class.value if isinstance(failure_class, FailureClass) else str(failure_class)
    return FAILURE_NEXT_ACTION.get(key, "try_alternative")


def failure_is_terminal(failure_class: str | FailureClass) -> bool:
    return next_action_for_failure(failure_class) in ("stop", "block")
