"""Explicit falsification contract for security hypotheses.

A hypothesis is not confirmed because a response looked interesting.
It is rejected when observations match its falsification_condition
(counter-evidence / expected-secure behavior observed).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional, Sequence

from agent_core.evidence.store import Evidence, EvidencePolarity
from agent_core.schemas.research import Hypothesis, HypothesisStatus


@dataclass
class FalsificationResult:
    hypothesis_id: str
    falsified: bool
    reason: str
    matching_evidence_ids: list[str]
    expected_security_property: str
    falsification_condition: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_authz_falsification(statement: str) -> tuple[str, str]:
    """Canonical expected property + falsification for ownership/authz hyps."""
    prop = (
        "Object access and mutation are restricted to the owner (or explicitly "
        "authorized roles); non-owners receive denial without private fields."
    )
    condition = (
        "Observe that a non-owner request for the same object is denied "
        "(401/403/empty) without private fields, OR baseline owner access and "
        "challenge non-owner access are equivalent to intended public/shared behavior."
    )
    if "role" in statement.lower():
        prop = "Lower-privilege roles cannot invoke admin-only actions."
        condition = (
            "Observe that the lower-privilege identity receives an authorization "
            "denial on the admin action without side effects."
        )
    return prop, condition


def ensure_falsification_fields(h: Hypothesis) -> Hypothesis:
    """Fill falsification contract when missing (backward compatible)."""
    if h.falsification_condition and h.expected_security_property:
        return h
    prop, cond = default_authz_falsification(h.statement)
    data = h.model_dump()
    if not data.get("expected_security_property"):
        data["expected_security_property"] = prop
    if not data.get("falsification_condition"):
        data["falsification_condition"] = cond
    return Hypothesis(**data)


def evaluate_falsification(
    hypothesis: Hypothesis,
    evidence: Sequence[Evidence],
) -> FalsificationResult:
    """
    Negative / contradicting evidence that matches the secure property
    falsifies the vulnerability hypothesis.
    """
    h = ensure_falsification_fields(hypothesis)
    neg_ids: list[str] = []
    for ev in evidence:
        pol = getattr(ev, "polarity", None)
        if pol == EvidencePolarity.NEGATIVE or (
            hasattr(pol, "value") and str(pol.value).lower() == "negative"
        ):
            neg_ids.append(ev.evidence_id)
        # notes may explicitly mark secure/denied
        observed = str(getattr(ev, "observed", "") or getattr(ev, "notes", "") or "")
        if observed and any(
            k in observed.lower() for k in ("denied", "403", "401", "expected_secure", "falsified")
        ):
            if ev.evidence_id not in neg_ids:
                neg_ids.append(ev.evidence_id)

    if neg_ids:
        return FalsificationResult(
            hypothesis_id=h.hypothesis_id,
            falsified=True,
            reason="counter_evidence_matches_falsification_condition",
            matching_evidence_ids=neg_ids,
            expected_security_property=h.expected_security_property,
            falsification_condition=h.falsification_condition,
        )
    return FalsificationResult(
        hypothesis_id=h.hypothesis_id,
        falsified=False,
        reason="no_matching_counter_evidence",
        matching_evidence_ids=[],
        expected_security_property=h.expected_security_property,
        falsification_condition=h.falsification_condition,
    )


def apply_falsification_to_hypothesis(
    hypothesis: Hypothesis,
    evidence: Sequence[Evidence],
) -> Hypothesis:
    """Return updated hypothesis; REJECTED when falsified; preserve evidence ids."""
    h = ensure_falsification_fields(hypothesis)
    result = evaluate_falsification(h, evidence)
    data = h.model_dump()
    if result.falsified:
        data["status"] = HypothesisStatus.REJECTED.value
        data["falsification_evidence_ids"] = list(result.matching_evidence_ids)
        # keep confidence low when falsified
        data["confidence"] = min(float(data.get("confidence") or 0.5), 0.2)
    return Hypothesis(**data)
