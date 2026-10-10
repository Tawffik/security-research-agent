"""
M4: bind selected Experiment intent to lab scenario observations.

Scenario = fixture observations (what happened).
Experiment = research intent (what was being tested).
Does not execute network; does not fabricate evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from agent_core.schemas.research import Experiment


@dataclass
class EvidenceRequirementStatus:
    requirement: str
    status: str  # satisfied | missing | ambiguous
    reason: str = ""



@dataclass
class CoverageGap:
    """Decision-oriented summary of what coverage is still needed (M6.6)."""

    prior_experiment_id: Optional[str] = None
    missing_step_ids: list[str] = field(default_factory=list)
    ambiguous_step_ids: list[str] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)
    ambiguous_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prior_experiment_id": self.prior_experiment_id,
            "missing_step_ids": list(self.missing_step_ids),
            "ambiguous_step_ids": list(self.ambiguous_step_ids),
            "missing_roles": list(self.missing_roles),
            "ambiguous_roles": list(self.ambiguous_roles),
        }

    @property
    def target_roles(self) -> list[str]:
        """Roles that still need coverage (missing first, then ambiguous)."""
        out: list[str] = []
        for r in self.missing_roles + self.ambiguous_roles:
            if r and r not in out:
                out.append(r)
        return out


def derive_coverage_gap(
    experiment: Optional[Experiment],
    coverage: list,
    *,
    prior_experiment_id: Optional[str] = None,
) -> CoverageGap:
    gap = CoverageGap(
        prior_experiment_id=prior_experiment_id
        or (experiment.experiment_id if experiment else None)
    )
    for c in coverage:
        role = c.role if isinstance(getattr(c, "role", None), str) else str(getattr(c, "role", ""))
        status = getattr(c, "status", "")
        sid = getattr(c, "step_id", "")
        if status == "missing":
            if sid:
                gap.missing_step_ids.append(sid)
            if role and role not in gap.missing_roles:
                gap.missing_roles.append(role)
        elif status == "ambiguous":
            if sid:
                gap.ambiguous_step_ids.append(sid)
            if role and role not in gap.ambiguous_roles:
                gap.ambiguous_roles.append(role)
    return gap


def experiment_addresses_gap(experiment: Experiment, gap: CoverageGap) -> bool:
    """True if experiment.steps include any target role from the gap."""
    if not gap.target_roles:
        return False
    roles = set()
    for s in getattr(experiment, "steps", None) or []:
        r = s.role.value if hasattr(s.role, "value") else str(s.role)
        roles.add(r)
    return bool(roles.intersection(gap.target_roles))


def prefer_gap_covering_candidates(
    candidates: list[Experiment],
    gap: CoverageGap,
) -> tuple[list[Experiment], list[Experiment]]:
    """Split into (covering, other). Prefer covering for JEV input order."""
    covering: list[Experiment] = []
    other: list[Experiment] = []
    for e in candidates:
        if experiment_addresses_gap(e, gap):
            covering.append(e)
        else:
            other.append(e)
    return covering, other


@dataclass
class ExperimentAlignment:
    experiment_id: Optional[str]
    hypothesis_id: Optional[str]
    scenario_name: str
    procedure_ref: Optional[str] = None
    required_evidence: list[EvidenceRequirementStatus] = field(default_factory=list)
    discriminator: str = ""
    discriminator_outcome: str = "indeterminate"  # supports | contradicts | ambiguous | indeterminate
    stop_condition: str = ""
    stop_condition_status: str = "indeterminate"  # satisfied | not_satisfied | indeterminate
    interpretation_notes: list[str] = field(default_factory=list)
    step_coverage: list = field(default_factory=list)
    baseline_ref: Optional[str] = None
    challenge_ref: Optional[str] = None
    experiment_sufficiency: str = "sufficient"  # sufficient | insufficient | ambiguous
    coverage_gap: Optional[CoverageGap] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "scenario_name": self.scenario_name,
            "procedure_ref": self.procedure_ref,
            "required_evidence": [
                {"requirement": r.requirement, "status": r.status, "reason": r.reason}
                for r in self.required_evidence
            ],
            "discriminator": self.discriminator,
            "discriminator_outcome": self.discriminator_outcome,
            "stop_condition": self.stop_condition,
            "stop_condition_status": self.stop_condition_status,
            "interpretation_notes": list(self.interpretation_notes),
            "step_coverage": [
                s.to_dict() if hasattr(s, "to_dict") else s for s in self.step_coverage
            ],
            "baseline_ref": self.baseline_ref,
            "challenge_ref": self.challenge_ref,
            "experiment_sufficiency": self.experiment_sufficiency,
            "coverage_gap": self.coverage_gap.to_dict() if self.coverage_gap else None,
            "all_required_satisfied": all(
                r.status == "satisfied" for r in self.required_evidence
            )
            if self.required_evidence
            else True,
        }


def extract_procedure_ref(experiment: Optional[Experiment]) -> Optional[str]:
    if not experiment:
        return None
    blob = f"{experiment.description} {experiment.discriminator}"
    m = re.search(r"PROC-\d{4}", blob, re.I)
    if m:
        return m.group(0).upper()
    m = re.search(r"procedure:([A-Za-z0-9_-]+)", blob, re.I)
    if m:
        return m.group(1)
    return None


def _obs_blob(observations: list) -> str:
    parts = []
    for o in observations:
        parts.append(f"{o.identity}:{o.status}:{o.method}:{o.path}:{o.body[:200]}")
    return " | ".join(parts).lower()


def evaluate_required_evidence(
    requirements: list[str],
    observations: list,
    scenario,
) -> list[EvidenceRequirementStatus]:
    """Map procedure requirements to presence in fixture observations — never invent obs."""
    blob = _obs_blob(observations)
    identities = {o.identity for o in observations}
    statuses = {o.status for o in observations}
    out: list[EvidenceRequirementStatus] = []

    for req in requirements:
        key = req.lower().strip()
        status = "missing"
        reason = "not observed in scenario fixtures"

        # Cross-identity / two identities
        if any(
            t in key
            for t in (
                "cross_identity",
                "cross-identity",
                "identity_a",
                "identity_b",
                "identities a/b",
                "two identities",
                "both identities",
            )
        ):
            if len(identities) >= 2:
                status, reason = "satisfied", f"identities={sorted(identities)}"
            else:
                status, reason = "missing", "fewer than two identities in observations"

        elif any(t in key for t in ("response", "status", "http")):
            if observations:
                status, reason = "satisfied", f"status_codes={sorted(statuses)}"
            else:
                status, reason = "missing", "no observations"

        elif any(t in key for t in ("ownership", "owner", "object")):
            if any("owner" in o.body.lower() or "user_a" in o.body.lower() for o in observations):
                status, reason = "satisfied", "ownership markers in body"
            elif observations:
                status, reason = "ambiguous", "observations present but no explicit ownership marker"
            else:
                status, reason = "missing", "no observations"

        elif any(t in key for t in ("authorization", "authz", "deny", "403", "decision")):
            if any(s in (401, 403, 404) for s in statuses) or scenario.suggests_authz_issue is not None:
                if any(s in (401, 403, 404) for s in statuses):
                    status, reason = "satisfied", "denial status present"
                elif scenario.suggests_authz_issue:
                    status, reason = "satisfied", "authz differential present (issue path)"
                else:
                    status, reason = "ambiguous", "scenario authz flag set without denial status"
            else:
                status, reason = "missing", "no authz decision signal in observations"

        elif any(t in key for t in ("before", "after", "state", "side effect", "mutate")):
            # Lab IDOR scenarios are mostly GET pairs — mutation side-effect often missing
            if "delete" in blob or "patch" in blob or "mutate" in blob:
                status, reason = "satisfied", "mutation-like observation present"
            else:
                status, reason = "missing", "no before/after mutation state in fixtures"

        elif key in blob or any(key in o.body.lower() for o in observations):
            status, reason = "satisfied", "token matched observation blob"
        else:
            # Unknown requirement: if we have multi-obs, ambiguous; else missing
            if len(observations) >= 2:
                status, reason = "ambiguous", "requirement not mapped; multi-obs present"
            else:
                status, reason = "missing", "requirement not mapped and insufficient obs"

        out.append(EvidenceRequirementStatus(requirement=req, status=status, reason=reason))
    return out


def interpret_discriminator(
    discriminator: str,
    observations: list,
    scenario,
) -> tuple[str, str]:
    """
    Compare fixture outcomes to experiment discriminator text.
    Returns (outcome, note). Never yields a finding by itself.
    """
    if not discriminator:
        return "indeterminate", "no discriminator"

    d = discriminator.lower()
    statuses = [o.status for o in observations]
    non_owner = [o for o in observations if o.identity not in ("user_a", "owner", "a")]
    non_owner_ok = any(o.status == 200 for o in non_owner)
    non_owner_denied = any(o.status in (401, 403, 404) for o in non_owner)

    expects_denial = any(
        t in d for t in ("403", "404", "denied", "blocked", "not authorized", "ownership markers only for owner")
    )
    expects_differential = any(
        t in d for t in ("diff", "two identities", "cross", "compare", "discriminator", "status code")
    )
    expects_side_effect = any(t in d for t in ("side effect", "before/after", "state change", "mutate"))

    if expects_side_effect and not any(
        "delete" in (o.method or "").lower() or "patch" in (o.method or "").lower() for o in observations
    ):
        return "ambiguous", "discriminator expects side-effect; fixtures lack mutate method"

    if expects_denial:
        if non_owner_denied and not non_owner_ok:
            return "supports", "non-owner denied as discriminator suggested"
        if non_owner_ok:
            return "contradicts", "expected denial; observed success for non-owner"
        return "ambiguous", "denial expectation not clearly resolved"

    if expects_differential or "procedure:" in d:
        if len(observations) >= 2 and len(set(statuses)) >= 1:
            if non_owner_ok:
                return "supports", "differential access: non-owner success observed"
            if non_owner_denied:
                return "supports", "differential denial: non-owner denied observed"
            return "ambiguous", "differential observed but alignment unclear"
        return "missing" if not observations else "ambiguous", "insufficient differential"

    return "indeterminate", "discriminator not classified"


def evaluate_stop_condition(stop_condition: str, scenario) -> str:
    if not stop_condition:
        return "indeterminate"
    s = stop_condition.lower()
    if "scope_violation" in s:
        # Scope checked outside; if we reached interpretation, scope was ok → not this stop
        return "not_satisfied"
    if "evidence_sufficient" in s or "sufficient" in s:
        return "satisfied" if scenario.observations else "not_satisfied"
    if "cached" in s:
        return "indeterminate"
    return "indeterminate"


def align_experiment_to_scenario(
    experiment: Optional[Experiment],
    scenario,
    *,
    hypothesis_id: Optional[str] = None,
) -> ExperimentAlignment:
    exp_id = experiment.experiment_id if experiment else None
    hyp_id = (experiment.hypothesis_id if experiment else None) or hypothesis_id
    disc = experiment.discriminator if experiment else ""
    stop = experiment.stop_condition if experiment else ""
    reqs = list(experiment.required_evidence) if experiment else []

    req_status = evaluate_required_evidence(reqs, list(scenario.observations), scenario)
    outcome, note = interpret_discriminator(disc, list(scenario.observations), scenario)
    stop_status = evaluate_stop_condition(stop, scenario)

    notes = [note]
    if experiment:
        notes.append(f"intent={experiment.description[:120]}")

    coverage = cover_steps(experiment, scenario)
    base, chal = baseline_challenge_pair(scenario)

    # When structured steps exist and baseline+challenge covered, refine discriminator via pair
    if coverage and base is not None and chal is not None:
        pair_outcome, pair_note = interpret_discriminator_pair(disc, base, chal, scenario)
        if pair_outcome != "indeterminate":
            outcome, note = pair_outcome, pair_note
            notes.append(f"pair:{pair_note}")

    sufficiency = compute_experiment_sufficiency(experiment, coverage)
    # Identity-pair requirements are decision-critical for authorization experiments.
    # Other missing reqs (e.g. mutation side-effects on GET labs) must not blanket
    # reclassify sufficiency — that regresses adaptive stop semantics.
    _identity_critical = (
        "identities a/b",
        "cross_identity",
        "cross-identity",
        "both identities",
        "two identities",
        "identity_a",
        "identity_b",
    )

    def _is_identity_req(req: str) -> bool:
        k = (req or "").lower()
        return any(t in k for t in _identity_critical)

    if any(
        r.status == "missing" and _is_identity_req(r.requirement) for r in req_status
    ):
        if sufficiency == "sufficient":
            sufficiency = "insufficient"
            notes.append("identity_pair_evidence_missing→insufficient")
    elif any(
        r.status == "ambiguous" and _is_identity_req(r.requirement) for r in req_status
    ):
        if sufficiency == "sufficient":
            sufficiency = "ambiguous"
            notes.append("identity_pair_evidence_ambiguous→ambiguous")
    gap = None
    if sufficiency != "sufficient":
        notes.append(f"experiment_sufficiency={sufficiency}")
        gap = derive_coverage_gap(
            experiment,
            coverage,
            prior_experiment_id=exp_id,
        )
        notes.append(f"coverage_gap_roles={gap.target_roles}")

    return ExperimentAlignment(
        experiment_id=exp_id,
        hypothesis_id=hyp_id,
        scenario_name=scenario.name,
        procedure_ref=extract_procedure_ref(experiment),
        required_evidence=req_status,
        discriminator=disc,
        discriminator_outcome=outcome,
        stop_condition=stop,
        stop_condition_status=stop_status,
        interpretation_notes=notes,
        step_coverage=coverage,
        baseline_ref=_obs_ref(base) if base else None,
        challenge_ref=_obs_ref(chal) if chal else None,
        experiment_sufficiency=sufficiency,
        coverage_gap=gap,
    )


def interpret_discriminator_pair(discriminator, baseline_obs, challenge_obs, scenario) -> tuple[str, str]:
    """Pair-aware discriminator using explicit baseline/challenge observations."""
    if baseline_obs is None or challenge_obs is None:
        return "indeterminate", "pair incomplete"
    d = (discriminator or "").lower()
    b_st, c_st = baseline_obs.status, challenge_obs.status
    if any(t in d for t in ("403", "404", "denied", "blocked")):
        if c_st in (401, 403, 404) and b_st == 200:
            return "supports", "challenge denied while baseline allowed"
        if c_st == 200 and b_st == 200:
            return "contradicts", "challenge allowed same as baseline (denial expected)"
        return "ambiguous", "pair denial expectation unresolved"
    # differential / procedure default
    if b_st != c_st or (baseline_obs.body != challenge_obs.body):
        if getattr(scenario, "suggests_authz_issue", False) and c_st == 200:
            return "supports", "baseline vs challenge differential consistent with issue path"
        if not getattr(scenario, "suggests_authz_issue", False) and c_st in (401, 403, 404):
            return "supports", "baseline vs challenge differential consistent with secure path"
        return "ambiguous", "differential present"
    return "indeterminate", "no differential in pair"


def resolve_selected_experiment(plan) -> Optional[Experiment]:
    """Use JEV decision candidate / experiment_id — no second selector."""
    decision = getattr(plan, "decision", None)
    experiments = list(getattr(plan, "experiments", None) or [])
    if not decision or not experiments:
        return experiments[0] if experiments else None
    eid = decision.experiment_id or decision.candidate
    if eid:
        for e in experiments:
            if e.experiment_id == eid:
                return e
    return experiments[0]


# --- M5 structured step coverage -------------------------------------------------

@dataclass
class StepCoverage:
    step_id: str
    role: str
    status: str  # covered | missing | ambiguous
    observation_refs: list[str] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "role": self.role,
            "status": self.status,
            "observation_refs": list(self.observation_refs),
            "text": self.text,
        }


def _obs_ref(o) -> str:
    return f"{getattr(o, 'role', '') or 'unset'}:{o.identity}:{o.method}:{o.path}:{o.status}"




def compute_experiment_sufficiency(
    experiment: Optional[Experiment],
    coverage: list,
) -> str:
    """
    sufficient | insufficient | ambiguous

    Only discriminator-relevant roles (baseline, challenge, compare) are mandatory
    when those steps exist on the experiment. observe steps are optional.
    """
    if not experiment or not getattr(experiment, "steps", None):
        return "sufficient"  # no structured steps → M4 path; not marked insufficient

    relevant = [
        c
        for c in coverage
        if (c.role if not hasattr(c, "role") else c.role) in ("baseline", "challenge", "compare")
        or (getattr(c, "role", None) in ("baseline", "challenge", "compare"))
    ]
    # normalize
    statuses = []
    for c in coverage:
        role = c.role if isinstance(c.role, str) else getattr(c, "role", "")
        if role in ("baseline", "challenge", "compare"):
            statuses.append(getattr(c, "status", "missing"))

    if not statuses:
        # only observe steps or empty → sufficient (nothing required)
        return "sufficient"
    # Missing dominates ambiguity: incomplete experiment first
    if any(s == "missing" for s in statuses):
        return "insufficient"
    if any(s == "ambiguous" for s in statuses):
        return "ambiguous"
    if all(s == "covered" for s in statuses):
        return "sufficient"
    return "ambiguous"

def cover_steps(experiment: Optional[Experiment], scenario) -> list[StepCoverage]:
    if not experiment or not getattr(experiment, "steps", None):
        return []
    observations = list(getattr(scenario, "observations", []) or [])
    by_role: dict[str, list] = {}
    for o in observations:
        role = (getattr(o, "role", None) or "").lower()
        if role:
            by_role.setdefault(role, []).append(o)

    out: list[StepCoverage] = []
    for step in experiment.steps:
        role = step.role.value if hasattr(step.role, "value") else str(step.role)
        refs: list[str] = []
        status = "missing"

        if role in ("baseline", "challenge"):
            matched = by_role.get(role, [])
            if len(matched) == 1:
                status = "covered"
                refs = [_obs_ref(matched[0])]
            elif len(matched) > 1:
                status = "ambiguous"
                refs = [_obs_ref(m) for m in matched]
            else:
                status = "missing"
        elif role == "compare":
            b = by_role.get("baseline", [])
            c = by_role.get("challenge", [])
            if len(b) == 1 and len(c) == 1:
                status = "covered"
                refs = [_obs_ref(b[0]), _obs_ref(c[0])]
            elif b or c:
                status = "ambiguous"
                refs = [_obs_ref(x) for x in b + c]
            else:
                status = "missing"
        else:  # observe
            if observations:
                status = "covered"
                refs = [_obs_ref(o) for o in observations]
            else:
                status = "missing"

        out.append(
            StepCoverage(
                step_id=step.step_id,
                role=role,
                status=status,
                observation_refs=refs,
                text=step.text,
            )
        )
    return out


def baseline_challenge_pair(scenario) -> tuple[Optional[Any], Optional[Any]]:
    """Explicit role-based pair — does not use list index."""
    baseline = None
    challenge = None
    for o in getattr(scenario, "observations", []) or []:
        role = (getattr(o, "role", None) or "").lower()
        if role == "baseline" and baseline is None:
            baseline = o
        elif role == "challenge" and challenge is None:
            challenge = o
    return baseline, challenge
