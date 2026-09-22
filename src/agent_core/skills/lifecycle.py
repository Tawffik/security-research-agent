"""
Skill lifecycle states (V2 skill supply chain).

Does not auto-promote. Runtime may only execute APPROVED skills above passive
risk unless policy says otherwise (enforced elsewhere via trust_score).
"""

from __future__ import annotations

from enum import Enum


class SkillLifecycleState(str, Enum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    BENCHMARKED = "benchmarked"
    REVIEW = "review"
    APPROVED = "approved"
    FAILED = "failed"
    REJECTED = "rejected"
    REGRESSION = "regression"
    DEPRECATED = "deprecated"


# Allowed transitions (documentation + light validation helper)
ALLOWED_TRANSITIONS: dict[SkillLifecycleState, set[SkillLifecycleState]] = {
    SkillLifecycleState.DRAFT: {SkillLifecycleState.CANDIDATE, SkillLifecycleState.REJECTED},
    SkillLifecycleState.CANDIDATE: {
        SkillLifecycleState.BENCHMARKED,
        SkillLifecycleState.FAILED,
        SkillLifecycleState.REJECTED,
    },
    SkillLifecycleState.BENCHMARKED: {
        SkillLifecycleState.REVIEW,
        SkillLifecycleState.FAILED,
        SkillLifecycleState.REJECTED,
    },
    SkillLifecycleState.REVIEW: {
        SkillLifecycleState.APPROVED,
        SkillLifecycleState.REJECTED,
    },
    SkillLifecycleState.APPROVED: {
        SkillLifecycleState.REGRESSION,
        SkillLifecycleState.DEPRECATED,
    },
    SkillLifecycleState.REGRESSION: {
        SkillLifecycleState.DEPRECATED,
        SkillLifecycleState.REVIEW,
    },
    SkillLifecycleState.FAILED: {SkillLifecycleState.CANDIDATE},
    SkillLifecycleState.REJECTED: set(),
    SkillLifecycleState.DEPRECATED: set(),
}


def can_transition(current: SkillLifecycleState, new: SkillLifecycleState) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, set())
