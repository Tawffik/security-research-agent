"""
Claim–Evidence Matrix (§53).

Finding-ready claims must link: Claim → Evidence → Observation refs.
Blocks confirmation packaging when core claims lack evidence IDs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ClaimEvidenceRow:
    claim_id: str
    claim: str
    evidence_ids: list[str] = field(default_factory=list)
    observation_refs: list[str] = field(default_factory=list)
    action_summary: str = ""
    tool: str = "lab_fixture"
    sufficient: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimEvidenceMatrix:
    engagement_id: str
    rows: list[ClaimEvidenceRow] = field(default_factory=list)
    report_ready: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engagement_id": self.engagement_id,
            "rows": [r.to_dict() for r in self.rows],
            "report_ready": self.report_ready,
            "block_reason": self.block_reason,
        }


class ClaimEvidenceBuilder:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0

    def build(
        self,
        *,
        claim: str,
        evidence_ids: list[str],
        observation_refs: Optional[list[str]] = None,
        action_summary: str = "",
        require_evidence: bool = True,
    ) -> ClaimEvidenceMatrix:
        self._n += 1
        sufficient = bool(evidence_ids) if require_evidence else True
        row = ClaimEvidenceRow(
            claim_id=f"CLM-{self._n:03d}",
            claim=claim,
            evidence_ids=list(evidence_ids),
            observation_refs=list(observation_refs or []),
            action_summary=action_summary,
            sufficient=sufficient,
        )
        blocked = require_evidence and not evidence_ids
        return ClaimEvidenceMatrix(
            engagement_id=self.engagement_id,
            rows=[row],
            report_ready=not blocked and sufficient,
            block_reason="core_claim_missing_evidence" if blocked else "",
        )
