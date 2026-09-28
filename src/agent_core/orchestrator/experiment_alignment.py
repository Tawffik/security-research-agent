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
        if non_owner_ok and scenario.suggests_authz_issue:
            return "contradicts", "discriminator expected denial; non-owner got 200"
        if non_owner_ok:
            return "contradicts", "expected denial; observed success for non-owner"
        return "ambiguous", "denial expectation not clearly resolved"

    if expects_differential or "procedure:" in d:
        if len(observations) >= 2 and len(set(statuses)) >= 1:
            if scenario.suggests_authz_issue and non_owner_ok:
                return "supports", "differential access consistent with issue-oriented experiment"
            if not scenario.suggests_authz_issue and non_owner_denied:
                return "supports", "differential denial consistent with secure-oriented experiment"
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
    )


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
