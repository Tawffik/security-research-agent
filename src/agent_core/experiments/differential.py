"""
Gate 4 — First-class Differential.

Raw Result ≠ Observation ≠ Differential ≠ Interpretation ≠ Finding

Generic baseline vs mutation comparison with noise-aware normalization.
No per-methodology differential engines.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence


class ChangeKind(str, Enum):
    NO_CHANGE = "no_change"
    EXPECTED_CHANGE = "expected_change"
    MEANINGFUL_CHANGE = "meaningful_change"
    NOISY_CHANGE = "noisy_change"
    CONTRADICTORY_CHANGE = "contradictory_change"
    INSUFFICIENT = "insufficient"


# Deterministic noise patterns — explainable, not a giant framework
_NOISE_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    re.compile(r"\b(?:request[_-]?id|trace[_-]?id|x-request-id)[=:\"'\s]+[A-Za-z0-9._-]+\b", re.I),
    re.compile(r"\b[Ee]tag[=:\"'\s]+[^\s,]+\b"),
    re.compile(r"\b\d{10,13}\b"),  # coarse epoch-like numbers
]


def normalize_noise(text: str) -> str:
    """Strip obvious unstable tokens for body comparison."""
    out = text or ""
    for rx in _NOISE_RES:
        out = rx.sub("<N>", out)
    return " ".join(out.split())


@dataclass
class DifferentialResult:
    """Legacy identity-pair result (compat) + Gate 4 fields."""

    baseline_identity: str
    compare_identity: str
    baseline_status: int
    compare_status: int
    status_differs: bool
    body_differs: bool
    same_object_path: bool
    interpretation: str
    notes: list[str] = field(default_factory=list)
    # Gate 4
    change_kind: str = ChangeKind.INSUFFICIENT.value
    baseline_observation_id: str = ""
    challenge_observation_id: str = ""
    experiment_id: str = ""
    noise_normalized: bool = False
    body_differs_after_noise: bool = False
    supports_hypotheses: list[str] = field(default_factory=list)
    contradicts_hypotheses: list[str] = field(default_factory=list)
    unresolved: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_identity_pair(
    baseline: Any,
    other: Any,
    *,
    expect_denial_for_other: bool = True,
    experiment_id: str = "",
    hypothesis_predictions: dict[str, str] | None = None,
) -> DifferentialResult:
    """
    Generic baseline vs challenge comparison.

    hypothesis_predictions: optional map hypothesis_id → expected pattern
      values: 'challenge_denied' | 'challenge_allowed' | 'status_change' | 'body_change'
    Does NOT invent findings — only classifies change and optional support/contradict lists.
    """
    b_status = int(getattr(baseline, "status", 0) or 0)
    o_status = int(getattr(other, "status", 0) or 0)
    b_body = str(getattr(baseline, "body", "") or "")
    o_body = str(getattr(other, "body", "") or "")
    b_path = str(getattr(baseline, "path", "") or "")
    o_path = str(getattr(other, "path", "") or "")
    same_path = b_path == o_path
    status_differs = b_status != o_status
    body_differs = b_body.strip() != o_body.strip()

    b_norm = normalize_noise(b_body)
    o_norm = normalize_noise(o_body)
    body_differs_after_noise = b_norm != o_norm
    noise_only = body_differs and not body_differs_after_noise and not status_differs

    notes: list[str] = []
    change_kind = ChangeKind.INSUFFICIENT

    if not status_differs and not body_differs:
        change_kind = ChangeKind.NO_CHANGE
        notes.append("identical status and body")
    elif noise_only:
        change_kind = ChangeKind.NOISY_CHANGE
        notes.append("only noise tokens differed after normalization")
    elif status_differs or body_differs_after_noise:
        change_kind = ChangeKind.MEANINGFUL_CHANGE
        notes.append("status and/or stable body content differs")

    # Compat interpretation strings (legacy consumers)
    bodies = (b_body + " " + o_body).lower()
    public_marker = any(
        x in bodies
        for x in ('"visibility":"public"', "public resource", '"public"')
    )
    shared_marker = any(x in bodies for x in ('"acl":', "shared acl", "shared-"))
    if public_marker:
        interpretation = "public_or_intended_access"
        notes.append("public visibility marker present — not ownership bypass")
        if change_kind == ChangeKind.MEANINGFUL_CHANGE:
            change_kind = ChangeKind.EXPECTED_CHANGE
    elif shared_marker and o_status < 400 and b_status < 400:
        interpretation = "shared_acl_or_intended_access"
        notes.append("shared ACL marker present — not horizontal IDOR")
        if change_kind == ChangeKind.MEANINGFUL_CHANGE:
            change_kind = ChangeKind.EXPECTED_CHANGE
    elif expect_denial_for_other:
        if o_status < 400 and b_status < 400 and not status_differs:
            interpretation = "possible_authorization_issue"
            notes.append("non-baseline identity received success similar to baseline")
        elif o_status >= 400 and b_status < 400:
            interpretation = "ownership_or_authz_appears_enforced"
            notes.append("compare identity denied while baseline succeeded")
            if change_kind == ChangeKind.MEANINGFUL_CHANGE:
                change_kind = ChangeKind.EXPECTED_CHANGE
        else:
            interpretation = "inconclusive"
            notes.append("status pattern does not clearly separate ownership enforcement")
    else:
        interpretation = "raw_differential"
        notes.append("no enforcement expectation applied")

    supports: list[str] = []
    contradicts: list[str] = []
    for hid, pred in (hypothesis_predictions or {}).items():
        pred_l = pred.lower()
        if pred_l == "challenge_denied":
            if o_status >= 400:
                supports.append(hid)
            elif o_status < 400 and b_status < 400:
                contradicts.append(hid)
        elif pred_l == "challenge_allowed":
            if o_status < 400:
                supports.append(hid)
            elif o_status >= 400:
                contradicts.append(hid)
        elif pred_l == "status_change":
            if status_differs:
                supports.append(hid)
            else:
                contradicts.append(hid)
        elif pred_l == "body_change":
            if body_differs_after_noise:
                supports.append(hid)
            else:
                contradicts.append(hid)

    unresolved = not supports and not contradicts
    if supports and contradicts:
        change_kind = ChangeKind.CONTRADICTORY_CHANGE
        notes.append("supports and contradicts different hypotheses")

    return DifferentialResult(
        baseline_identity=str(getattr(baseline, "identity", "") or ""),
        compare_identity=str(getattr(other, "identity", "") or ""),
        baseline_status=b_status,
        compare_status=o_status,
        status_differs=status_differs,
        body_differs=body_differs,
        same_object_path=same_path,
        interpretation=interpretation,
        notes=notes,
        change_kind=change_kind.value,
        baseline_observation_id=str(getattr(baseline, "observation_id", "") or ""),
        challenge_observation_id=str(getattr(other, "observation_id", "") or ""),
        experiment_id=experiment_id,
        noise_normalized=True,
        body_differs_after_noise=body_differs_after_noise,
        supports_hypotheses=supports,
        contradicts_hypotheses=contradicts,
        unresolved=unresolved,
    )


def compare_lab_observations(
    observations: Sequence[Any],
    *,
    experiment_id: str = "",
    hypothesis_predictions: dict[str, str] | None = None,
) -> Optional[DifferentialResult]:
    if len(observations) < 2:
        return None
    # Prefer role baseline/challenge if present
    baseline = next((o for o in observations if str(getattr(o, "role", "")).lower() == "baseline"), None)
    challenge = next((o for o in observations if str(getattr(o, "role", "")).lower() == "challenge"), None)
    if baseline is not None and challenge is not None:
        return compare_identity_pair(
            baseline,
            challenge,
            experiment_id=experiment_id,
            hypothesis_predictions=hypothesis_predictions,
        )
    ordered = sorted(
        observations,
        key=lambda o: (0 if str(getattr(o, "identity", "")).endswith("_a") else 1),
    )
    return compare_identity_pair(
        ordered[0],
        ordered[1],
        experiment_id=experiment_id,
        hypothesis_predictions=hypothesis_predictions,
    )


def differential_to_polarity(diff: Optional[DifferentialResult]) -> str:
    """Map change kind to coarse polarity for hypothesis update — not a finding."""
    if diff is None:
        return "insufficient"
    ck = diff.change_kind
    if ck == ChangeKind.NO_CHANGE.value:
        return "neutral"
    if ck == ChangeKind.NOISY_CHANGE.value:
        return "neutral"
    if ck == ChangeKind.INSUFFICIENT.value:
        return "insufficient"
    if ck == ChangeKind.CONTRADICTORY_CHANGE.value:
        return "neutral"
    if ck == ChangeKind.EXPECTED_CHANGE.value:
        return "negative"  # enforcement observed relative to expect-denial path
    if ck == ChangeKind.MEANINGFUL_CHANGE.value:
        # Meaningful without enforcement label → unresolved research signal
        if diff.interpretation == "possible_authorization_issue":
            return "positive"
        if diff.interpretation == "ownership_or_authz_appears_enforced":
            return "negative"
        return "neutral"
    if getattr(diff, "interpretation", "") in (
        "ownership_or_authz_appears_enforced",
        "public_or_intended_access",
        "shared_acl_or_intended_access",
    ):
        return "negative"
    return "neutral"
