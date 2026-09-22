"""
Root Cause Engine (V2 §42 / Phase 13 partial).

Only meaningful AFTER a finding is confirmed with evidence.
Produces a structural hypothesis about *why* the issue exists — still
evidence-linked, not free-form speculation promoted to truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agent_core.schemas.target import TargetContext


@dataclass
class RootCause:
    root_cause_id: str
    finding_id: str
    summary: str
    signature: str
    confidence: float
    evidence_ids: list[str] = field(default_factory=list)
    structural_hints: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "root_cause_id": self.root_cause_id,
            "finding_id": self.finding_id,
            "summary": self.summary,
            "signature": self.signature,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "structural_hints": list(self.structural_hints),
            "notes": self.notes,
        }


class RootCauseEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0

    def analyze_confirmed(
        self,
        *,
        finding_id: str,
        claim: str,
        evidence_ids: list[str],
        ctx: TargetContext,
        scenario_name: str = "",
    ) -> Optional[RootCause]:
        """
        Derive a root-cause candidate from confirmed authz-style findings.
        Returns None if evidence is empty (cannot root-cause without evidence).
        """
        if not evidence_ids or not finding_id:
            return None

        self._counter += 1
        rid = f"RC-{self._counter:03d}"

        claim_l = (claim or "").lower()
        # Authorization / ownership pattern
        if "ownership" in claim_l or "object" in claim_l or "cross-identity" in claim_l:
            summary = "Missing or inconsistent server-side ownership enforcement on object access"
            signature = "resource_resolver + missing_ownership_middleware"
            hints = [
                "Same controller/pattern may serve multiple resource types",
                "Check whether authorization middleware is applied per-route inconsistently",
            ]
            # Structural: multiple {id} endpoints with auth_required
            id_eps = [e for e in ctx.endpoints if "{id}" in e.path and e.auth_required]
            if len(id_eps) > 1:
                hints.append(
                    f"{len(id_eps)} auth-required object endpoints share identifier pattern"
                )
            conf = 0.7 if len(evidence_ids) >= 2 else 0.55
            return RootCause(
                root_cause_id=rid,
                finding_id=finding_id,
                summary=summary,
                signature=signature,
                confidence=conf,
                evidence_ids=list(evidence_ids),
                structural_hints=hints,
                notes=f"Derived after confirmation; scenario={scenario_name or 'n/a'}",
            )

        return RootCause(
            root_cause_id=rid,
            finding_id=finding_id,
            summary="Confirmed finding; structural root cause not yet classified",
            signature="unclassified",
            confidence=0.4,
            evidence_ids=list(evidence_ids),
            structural_hints=[],
            notes="Generic fallback — expand classifiers as domains grow",
        )
