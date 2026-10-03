"""
Gate 7 offline — trajectory evaluation (not final-answer-only).

Measures research path quality without access to hidden oracle labels
in the decision path. Oracle may be used only in evaluator after the fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class TrajectoryMetrics:
    episode_id: str
    n_experiments: int = 0
    n_observations: int = 0
    n_evidence: int = 0
    n_positive_evidence: int = 0
    n_negative_evidence: int = 0
    n_branches: int = 0
    n_backtracks: int = 0
    redundant_experiments: int = 0
    discriminating_experiments: int = 0
    stop_reason: str = ""
    verified_finding: bool = False
    inconclusive: bool = False
    scope_blocked: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_trajectory(
    *,
    episode_id: str,
    experiment_ids: list[str] | None = None,
    observation_count: int = 0,
    evidence_polarities: list[str] | None = None,
    branch_count: int = 0,
    backtrack_count: int = 0,
    stop_reason: str = "",
    discriminating_experiment_ids: list[str] | None = None,
    tried_experiment_ids: list[str] | None = None,
) -> TrajectoryMetrics:
    experiments = list(experiment_ids or [])
    tried = list(tried_experiment_ids or experiments)
    # redundant = duplicates in tried
    redundant = len(tried) - len(set(tried))
    pols = [p.lower() for p in (evidence_polarities or [])]
    pos = sum(1 for p in pols if p == "positive")
    neg = sum(1 for p in pols if p == "negative")
    stop = (stop_reason or "").lower()
    return TrajectoryMetrics(
        episode_id=episode_id,
        n_experiments=len(set(experiments)) or len(experiments),
        n_observations=observation_count,
        n_evidence=len(pols),
        n_positive_evidence=pos,
        n_negative_evidence=neg,
        n_branches=branch_count,
        n_backtracks=backtrack_count,
        redundant_experiments=max(0, redundant),
        discriminating_experiments=len(discriminating_experiment_ids or []),
        stop_reason=stop_reason,
        verified_finding=stop in ("verified", "evidence_sufficient"),
        inconclusive=stop in ("inconclusive_exhausted", "inconclusive"),
        scope_blocked=stop in ("scope_blocked", "authorization_denied"),
        notes=[],
    )
