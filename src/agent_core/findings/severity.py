"""
Structured severity fields (§71).

Not free-form LLM severity — explicit dimensions from evidence context.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class SeverityAssessment:
    level: str  # info | low | medium | high | critical
    impact: str
    exploitability: str
    affected_boundary: str
    required_privileges: str
    data_exposure: str
    integrity_effect: str
    availability_effect: str
    confidence: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_authz_finding(
    *,
    confirmed: bool,
    invariant_violated: Optional[bool] = None,
    cross_identity: bool = True,
) -> SeverityAssessment:
    if not confirmed:
        return SeverityAssessment(
            level="info",
            impact="none_confirmed",
            exploitability="n/a",
            affected_boundary="none",
            required_privileges="authenticated",
            data_exposure="none",
            integrity_effect="none",
            availability_effect="none",
            confidence=0.8,
            notes="No confirmed finding",
        )
    level = "high" if invariant_violated else "medium"
    return SeverityAssessment(
        level=level,
        impact="unauthorized_object_access" if cross_identity else "authorization_weakness",
        exploitability="low_complexity_authenticated",
        affected_boundary="object_horizontal",
        required_privileges="authenticated_non_owner",
        data_exposure="object_fields",
        integrity_effect="none_observed",
        availability_effect="none",
        confidence=0.75 if invariant_violated else 0.65,
        notes="Structured from lab evidence context only",
    )
