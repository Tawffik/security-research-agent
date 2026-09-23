"""
Unified stop conditions (§61).

Stopping intelligently is a feature — not failure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class StopReasonCode(str, Enum):
    HYPOTHESIS_DISPROVEN = "hypothesis_disproven"
    EQUIVALENT_EVIDENCE_EXISTS = "equivalent_evidence_exists"
    INFORMATION_GAIN_TOO_LOW = "information_gain_too_low"
    BUDGET_EXHAUSTED = "budget_exhausted"
    RISK_THRESHOLD = "risk_threshold_exceeded"
    SCOPE_BLOCKED = "scope_blocked"
    EVIDENCE_SUFFICIENT = "sufficient_evidence"
    ROOT_CAUSE_EXHAUSTED = "root_cause_exhausted"
    NO_VALUABLE_VARIANTS = "no_valuable_variants_remain"
    JEV_STOP = "jev_stop"
    HUMAN_STOP = "human_stop"


@dataclass
class StopDecision:
    should_stop: bool
    reason_code: str
    detail: str = ""
    authoritative: bool = True  # system/policy stop vs soft suggestion

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StopPolicy:
    """
    Evaluate whether research should stop given structured signals.
    Does not execute network; pure decision helper.
    """

    def evaluate(
        self,
        *,
        scope_allowed: bool = True,
        referee_accepted: Optional[bool] = None,
        final_status: str = "",
        evidence_count: int = 0,
        has_variants: bool = False,
        adaptive_stop: Optional[bool] = None,
        adaptive_reason: str = "",
        budget_remaining_ratio: float = 1.0,
        mean_action_regret: Optional[float] = None,
        risk_exceeded: bool = False,
    ) -> StopDecision:
        if not scope_allowed:
            return StopDecision(True, StopReasonCode.SCOPE_BLOCKED.value, "ScopeGuard denied")

        if risk_exceeded:
            return StopDecision(True, StopReasonCode.RISK_THRESHOLD.value, "risk policy")

        if budget_remaining_ratio <= 0:
            return StopDecision(True, StopReasonCode.BUDGET_EXHAUSTED.value, "budget")

        if final_status == "rejected" or adaptive_reason == "hypothesis_disproven":
            return StopDecision(
                True,
                StopReasonCode.HYPOTHESIS_DISPROVEN.value,
                "negative evidence — do not re-spray",
            )

        if referee_accepted and evidence_count > 0 and not has_variants:
            return StopDecision(
                True,
                StopReasonCode.EVIDENCE_SUFFICIENT.value,
                "confirmed without further structural variants",
            )

        if referee_accepted and evidence_count > 0 and has_variants is False:
            return StopDecision(True, StopReasonCode.NO_VALUABLE_VARIANTS.value, "")

        if mean_action_regret is not None and mean_action_regret >= 0.55:
            return StopDecision(
                True,
                StopReasonCode.INFORMATION_GAIN_TOO_LOW.value,
                f"mean_regret={mean_action_regret}",
            )

        if adaptive_stop and adaptive_reason:
            code = adaptive_reason
            if adaptive_reason == "jev_stop":
                code = StopReasonCode.JEV_STOP.value
            elif adaptive_reason == "sufficient_evidence":
                code = StopReasonCode.EVIDENCE_SUFFICIENT.value
            return StopDecision(True, code, "adaptive layer")

        if adaptive_stop:
            return StopDecision(True, StopReasonCode.INFORMATION_GAIN_TOO_LOW.value, "adaptive stop")

        return StopDecision(False, "", "continue")
