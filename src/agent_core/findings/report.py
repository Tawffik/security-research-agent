"""
Evidence-only report compiler (V2 §19–20, §45 partial).

A report is blocked or marked incomplete when core claims lack evidence IDs.
No LLM prose-as-authority: only structured fields + cited evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EvidenceReport:
    engagement_id: str
    title: str
    claim: str
    status: str  # confirmed | rejected | needs_more_evidence | scope_denied | incomplete
    evidence_ids: list[str] = field(default_factory=list)
    hypothesis_id: Optional[str] = None
    finding_id: Optional[str] = None
    stop_reason: str = ""
    belief_updates: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    report_blocked: bool = False
    block_reason: str = ""
    markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engagement_id": self.engagement_id,
            "title": self.title,
            "claim": self.claim,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "hypothesis_id": self.hypothesis_id,
            "finding_id": self.finding_id,
            "stop_reason": self.stop_reason,
            "belief_updates": list(self.belief_updates),
            "limitations": list(self.limitations),
            "report_blocked": self.report_blocked,
            "block_reason": self.block_reason,
            "markdown": self.markdown,
        }


def build_evidence_report(
    *,
    engagement_id: str,
    title: str,
    claim: str,
    status: str,
    evidence_ids: list[str],
    hypothesis_id: Optional[str] = None,
    finding_id: Optional[str] = None,
    stop_reason: str = "",
    belief_updates: Optional[list[str]] = None,
    limitations: Optional[list[str]] = None,
    require_evidence_for_confirmed: bool = True,
) -> EvidenceReport:
    """
    Build a report. CONFIRMED without evidence_ids → blocked.
    """
    belief_updates = list(belief_updates or [])
    limitations = list(limitations or [])
    blocked = False
    block_reason = ""

    if require_evidence_for_confirmed and status == "confirmed" and not evidence_ids:
        blocked = True
        block_reason = "CONFIRMED requires at least one evidence_id; report blocked"
        status = "incomplete"

    if status == "confirmed" and not finding_id:
        # soft warning in limitations, not hard block if evidence exists
        limitations.append("confirmed status without finding_id — check EvidenceStore.create_finding")

    lines = [
        f"# Research Report — `{engagement_id}`",
        "",
        f"**Status:** `{status}`",
        f"**Stop reason:** {stop_reason or '(none)'}",
        "",
        "## Claim",
        claim or "(no claim)",
        "",
        "## Title",
        title or "(untitled)",
        "",
        "## Evidence IDs",
    ]
    if evidence_ids:
        for eid in evidence_ids:
            lines.append(f"- `{eid}`")
    else:
        lines.append("- *(none — insufficient for authoritative finding)*")

    lines.extend(
        [
            "",
            f"**Hypothesis:** `{hypothesis_id or 'n/a'}`",
            f"**Finding ID:** `{finding_id or 'n/a'}`",
            "",
            "## Belief updates",
        ]
    )
    if belief_updates:
        for b in belief_updates:
            lines.append(f"- {b}")
    else:
        lines.append("- *(none recorded)*")

    lines.extend(["", "## Limitations"])
    for lim in limitations:
        lines.append(f"- {lim}")

    if blocked:
        lines.extend(["", "## REPORT BLOCKED", block_reason])

    lines.extend(
        [
            "",
            "---",
            "*This report is evidence-linked. It is not authoritative LLM prose.*",
        ]
    )

    return EvidenceReport(
        engagement_id=engagement_id,
        title=title,
        claim=claim,
        status=status,
        evidence_ids=list(evidence_ids),
        hypothesis_id=hypothesis_id,
        finding_id=finding_id,
        stop_reason=stop_reason,
        belief_updates=belief_updates,
        limitations=limitations,
        report_blocked=blocked,
        block_reason=block_reason,
        markdown="\n".join(lines),
    )
