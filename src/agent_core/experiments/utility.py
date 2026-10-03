"""
Utility-aware experiment selection (explainable).

Utility ≈ discrimination/information_gain + evidence_debt_reduction − cost − risk

Subject to: prerequisites, capability availability, prior experiments.
Does NOT grant execution permission — ScopeGuard / ExecutionBoundary remain authoritative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Sequence

from agent_core.schemas.research import Experiment, Hypothesis


@dataclass
class UtilityBreakdown:
    experiment_id: str
    information_gain: float
    evidence_debt_reduction: float
    cost: float
    risk: float
    prior_penalty: float
    prerequisite_ok: bool
    capability_available: bool
    utility: float
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    formula: str = (
        "utility = information_gain + evidence_debt_reduction - cost - risk - prior_penalty"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gap_reduction(exp: Experiment, evidence_gaps: Sequence[str]) -> float:
    req = [str(x).lower() for x in (getattr(exp, "required_evidence", None) or [])]
    if not evidence_gaps:
        return 0.0
    hits = 0
    for g in evidence_gaps:
        gl = str(g).lower()
        if any(gl in r or r in gl for r in req):
            hits += 1
        # structured steps address baseline/challenge gaps
        steps = list(getattr(exp, "steps", None) or [])
        roles = {getattr(s, "role", "") for s in steps}
        if "challenge" in gl and "challenge" in roles:
            hits += 1
        if "baseline" in gl and "baseline" in roles:
            hits += 1
    return min(1.5, 0.5 * hits)


def _prerequisites_satisfied(exp: Experiment, available_preconditions: Sequence[str]) -> bool:
    needed = list(getattr(exp, "preconditions", None) or [])
    if not needed:
        return True
    avail = {str(p).lower() for p in available_preconditions}
    for n in needed:
        if str(n).lower() not in avail and not any(str(n).lower() in a for a in avail):
            return False
    return True


def score_utility(
    exp: Experiment,
    *,
    hypotheses: list[Hypothesis] | None = None,
    evidence_gaps: Sequence[str] | None = None,
    prior_experiment_ids: Sequence[str] | None = None,
    available_preconditions: Sequence[str] | None = None,
    available_capabilities: Sequence[str] | None = None,
    required_capability: str | None = None,
) -> UtilityBreakdown:
    reasons: list[str] = []
    ig = float(getattr(exp, "information_gain", 0.5) or 0.5)
    cost = float(getattr(exp, "cost", 0.3) or 0.3)
    risk = float(getattr(exp, "risk", 0.3) or 0.3)
    debt = _gap_reduction(exp, evidence_gaps or [])
    if debt > 0:
        reasons.append(f"evidence_debt_reduction={debt:.2f}")

    prior = {str(p).lower() for p in (prior_experiment_ids or [])}
    eid = (exp.experiment_id or "").lower()
    prior_penalty = 0.0
    if eid in prior or any(p and p in eid for p in prior):
        prior_penalty = 3.0
        reasons.append("prior_experiment_penalty")

    if getattr(exp, "discriminator", None):
        ig = min(1.0, ig + 0.15)
        reasons.append("has_discriminator")

    steps = list(getattr(exp, "steps", None) or [])
    roles = {getattr(s, "role", "") for s in steps}
    if "baseline" in roles and "challenge" in roles:
        ig = min(1.0, ig + 0.1)
        reasons.append("baseline_challenge_pair")

    if hypotheses and len(hypotheses) >= 2:
        ig = min(1.0, ig + 0.05)
        reasons.append("multi_hypothesis_portfolio")

    pre_ok = _prerequisites_satisfied(exp, available_preconditions or [])
    if not pre_ok:
        reasons.append("prerequisite_missing")

    cap_ok = True
    if required_capability:
        caps = {str(c).lower() for c in (available_capabilities or [])}
        cap_ok = required_capability.lower() in caps
        if not cap_ok:
            reasons.append("capability_not_available")

    utility = ig + debt - cost - risk - prior_penalty
    eligible = pre_ok and cap_ok and prior_penalty < 3.0

    reasons.append(f"ig={ig:.2f}")
    reasons.append(f"cost={cost:.2f}")
    reasons.append(f"risk={risk:.2f}")

    return UtilityBreakdown(
        experiment_id=exp.experiment_id,
        information_gain=ig,
        evidence_debt_reduction=debt,
        cost=cost,
        risk=risk,
        prior_penalty=prior_penalty,
        prerequisite_ok=pre_ok,
        capability_available=cap_ok,
        utility=utility,
        eligible=eligible,
        reasons=reasons,
    )


def select_by_utility(
    experiments: list[Experiment],
    *,
    hypotheses: list[Hypothesis] | None = None,
    evidence_gaps: Sequence[str] | None = None,
    prior_experiment_ids: Sequence[str] | None = None,
    available_preconditions: Sequence[str] | None = None,
    available_capabilities: Sequence[str] | None = None,
) -> tuple[Optional[Experiment], list[UtilityBreakdown]]:
    if not experiments:
        return None, []
    scored = [
        score_utility(
            e,
            hypotheses=hypotheses,
            evidence_gaps=evidence_gaps,
            prior_experiment_ids=prior_experiment_ids,
            available_preconditions=available_preconditions,
            available_capabilities=available_capabilities,
            required_capability=None,
        )
        for e in experiments
    ]
    eligible = [s for s in scored if s.eligible]
    pool = eligible if eligible else scored  # fail open to scored only for ranking display; prefer eligible
    pool.sort(key=lambda s: s.utility, reverse=True)
    best_id = pool[0].experiment_id
    best = next((e for e in experiments if e.experiment_id == best_id), None)
    # Prefer eligible winner
    if eligible:
        eligible.sort(key=lambda s: s.utility, reverse=True)
        best_id = eligible[0].experiment_id
        best = next((e for e in experiments if e.experiment_id == best_id), best)
    scored.sort(key=lambda s: s.utility, reverse=True)
    return best, scored
