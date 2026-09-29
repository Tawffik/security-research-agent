"""
Minimum discriminating experiment selection (Gate 3).

Prefer experiments that separate competing hypotheses and address evidence gaps,
while avoiding repetition of prior experiment IDs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent_core.schemas.research import Experiment, Hypothesis


@dataclass
class DiscriminationScore:
    experiment_id: str
    score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_discriminating_power(
    exp: Experiment,
    *,
    hypotheses: list[Hypothesis],
    prior_experiment_ids: list[str] | None = None,
    evidence_gaps: list[str] | None = None,
    open_hypothesis_ids: list[str] | None = None,
) -> DiscriminationScore:
    reasons: list[str] = []
    score = 0.0
    prior = {p.lower() for p in (prior_experiment_ids or [])}
    eid = (exp.experiment_id or "").lower()

    if eid in prior or any(p in eid for p in prior if p):
        score -= 3.0
        reasons.append("prior_experiment_penalty")

    # Prefer open hypothesis linkage
    open_ids = set(open_hypothesis_ids or [h.hypothesis_id for h in hypotheses if h.status.value == "open"])
    if exp.hypothesis_id in open_ids:
        score += 1.5
        reasons.append("linked_open_hypothesis")

    # Discriminator present
    if getattr(exp, "discriminator", None):
        score += 1.2
        reasons.append("has_discriminator")

    # Required evidence addresses gaps
    req = [str(x).lower() for x in (getattr(exp, "required_evidence", None) or [])]
    for g in evidence_gaps or []:
        gl = str(g).lower()
        if any(gl in r or r in gl for r in req):
            score += 0.8
            reasons.append(f"addresses_gap:{g[:40]}")

    # Procedure-driven / structured steps → more discriminating baseline/challenge
    steps = list(getattr(exp, "steps", None) or [])
    roles = {getattr(s, "role", "") for s in steps}
    if "baseline" in roles and "challenge" in roles:
        score += 1.5
        reasons.append("baseline_challenge_pair")

    # Information gain / cost if present
    score += float(getattr(exp, "information_gain", 0.5) or 0.5)
    score -= 0.3 * float(getattr(exp, "cost", 0.3) or 0.3)

    # Competing hyp portfolio size increases value of discrimination
    if len(hypotheses) >= 2:
        score += 0.5
        reasons.append("multi_hypothesis_portfolio")

    return DiscriminationScore(experiment_id=exp.experiment_id, score=score, reasons=reasons)


def select_minimum_discriminating(
    experiments: list[Experiment],
    hypotheses: list[Hypothesis],
    *,
    prior_experiment_ids: list[str] | None = None,
    evidence_gaps: list[str] | None = None,
) -> tuple[Optional[Experiment], list[DiscriminationScore]]:
    if not experiments:
        return None, []
    scored = [
        score_discriminating_power(
            e,
            hypotheses=hypotheses,
            prior_experiment_ids=prior_experiment_ids,
            evidence_gaps=evidence_gaps,
        )
        for e in experiments
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    best_id = scored[0].experiment_id
    best = next((e for e in experiments if e.experiment_id == best_id), experiments[0])
    return best, scored
