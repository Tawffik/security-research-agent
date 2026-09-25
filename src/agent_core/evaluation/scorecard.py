"""
Quality scorecard dimensions (§7 Notion V3) — lab aggregation.

Does not claim production benchmark scores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class QualityScorecard:
    engagement_id: str
    validated_finding: bool = False
    false_positive_avoided: bool = False
    evidence_sufficient: bool = False
    scope_safe: bool = True
    intelligent_stop: bool = False
    redundant_risk: float = 0.0
    mean_regret: float = 0.0
    efficiency_proxy: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def summary_label(self) -> str:
        if not self.scope_safe:
            return "unsafe_or_scope_issue"
        if self.validated_finding and self.evidence_sufficient:
            return "validated_lab_finding"
        if self.false_positive_avoided:
            return "clean_reject"
        return "incomplete_or_low_gain"


def build_scorecard(
    *,
    engagement_id: str,
    closed: Any,
    adaptive: Any = None,
    regrets: Optional[list[Any]] = None,
    matrix: Any = None,
) -> QualityScorecard:
    notes: list[str] = []
    validated = bool(getattr(closed, "referee_accepted", False))
    rejected = (getattr(closed, "final_status", None) or "") == "rejected"
    evidence_ok = bool(getattr(closed, "evidence_ids", None))
    scope_safe = bool(getattr(closed, "scope_allowed", True))
    stop_intelligent = False
    if adaptive is not None and getattr(adaptive, "stop", False):
        reason = getattr(adaptive, "stop_reason", "") or ""
        stop_intelligent = reason in (
            "hypothesis_disproven",
            "sufficient_evidence",
            "scope_blocked",
            "information_gain_too_low",
            "jev_stop",
        )
        notes.append(f"stop_reason={reason}")

    mean_reg = 0.0
    if regrets:
        mean_reg = round(sum(getattr(r, "regret", 0) for r in regrets) / max(1, len(regrets)), 4)

    eff = 0.0
    ep = getattr(closed, "episode", None)
    if ep is not None and getattr(ep, "metrics", None) is not None:
        m = ep.metrics
        if hasattr(m, "compute"):
            m.compute()
        eff = float(getattr(m, "efficiency_proxy", 0) or 0)

    matrix_ok = True
    if matrix is not None:
        matrix_ok = bool(getattr(matrix, "report_ready", True))

    return QualityScorecard(
        engagement_id=engagement_id,
        validated_finding=validated and evidence_ok and matrix_ok,
        false_positive_avoided=rejected and evidence_ok,
        evidence_sufficient=evidence_ok and (validated or rejected),
        scope_safe=scope_safe,
        intelligent_stop=stop_intelligent,
        mean_regret=mean_reg,
        efficiency_proxy=eff,
        notes=notes,
    )
