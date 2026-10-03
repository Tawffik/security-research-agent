"""
Trajectory security / influence analysis (lightweight, no graph DB).

Untrusted source → state/memory → decision → capability → tool → action
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence


@dataclass
class InfluenceFinding:
    kind: str
    detail: str
    severity: str = "info"  # info | warn | critical

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrajectorySecurityReport:
    findings: list[InfluenceFinding] = field(default_factory=list)
    source_to_action_links: int = 0
    denied_action_attempts: int = 0
    memory_contamination_flags: int = 0
    capability_escalation_flags: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_trajectory_security(
    *,
    untrusted_source_ids: Sequence[str] | None = None,
    memory_refs_used: Sequence[str] | None = None,
    memory_trust_states: dict[str, str] | None = None,
    decisions: Sequence[dict[str, Any]] | None = None,
    execution_audit: Sequence[dict[str, Any]] | None = None,
    capability_differentials: Sequence[dict[str, Any]] | None = None,
) -> TrajectorySecurityReport:
    report = TrajectorySecurityReport()
    untrusted = set(untrusted_source_ids or [])
    mem_states = memory_trust_states or {}

    for mid in memory_refs_used or []:
        st = mem_states.get(mid, "unknown")
        if st in ("candidate", "untrusted", "revoked") or mid in untrusted:
            report.memory_contamination_flags += 1
            report.findings.append(
                InfluenceFinding("memory_contamination", f"untrusted_or_weak_memory:{mid}", "warn")
            )

    for d in decisions or []:
        if d.get("source") in untrusted or d.get("influenced_by_untrusted"):
            report.source_to_action_links += 1
            report.findings.append(
                InfluenceFinding("source_to_decision", str(d.get("decision_id", d)), "warn")
            )

    for a in execution_audit or []:
        if a.get("decision") == "DENY" or a.get("allowed") is False:
            report.denied_action_attempts += 1
        if a.get("allowed") and a.get("source") in untrusted:
            report.source_to_action_links += 1
            report.findings.append(
                InfluenceFinding("source_to_action", "untrusted_influenced_allow", "critical")
            )

    for c in capability_differentials or []:
        if c.get("differential") in ("declared_only", "mismatch"):
            report.capability_escalation_flags += 1
            report.findings.append(
                InfluenceFinding("capability_escalation", str(c.get("capability_name")), "warn")
            )
        if c.get("declared_available") and not c.get("scope_allowed"):
            report.findings.append(
                InfluenceFinding("capability_without_scope", str(c.get("capability_name")), "info")
            )

    return report
