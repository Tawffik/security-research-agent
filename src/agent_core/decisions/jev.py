"""
JEV — Decision / Prioritization layer (V2 §17).

Structured decisions only. NEVER overrides ScopeGuard, RiskPolicy, or Budget.
Those gates remain in the orchestrator / ScopeGuard path.
"""

from __future__ import annotations

from agent_core.schemas.research import Decision, DecisionAction, Experiment, Hypothesis


class JEV:
    """
    Picks which experiment to run next using information_gain, cost, risk,
    and hypothesis confidence. Pure scoring — no network, no scope mutation.
    """

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0
        self._history: list[Decision] = []

    def choose(
        self,
        experiments: list[Experiment],
        hypotheses: list[Hypothesis],
        *,
        budget_remaining_ratio: float = 1.0,
        stop_requested: bool = False,
    ) -> Decision:
        self._counter += 1
        did = f"decision_{self._counter}"

        if stop_requested or budget_remaining_ratio <= 0:
            d = Decision(
                decision_id=did,
                decision=DecisionAction.STOP,
                confidence=1.0,
                reason_codes=["BUDGET_EXHAUSTED" if budget_remaining_ratio <= 0 else "STOP_REQUESTED"],
            )
            self._history.append(d)
            return d

        open_exps = [e for e in experiments if e.status.value in ("planned", "cached")]
        if not open_exps:
            d = Decision(
                decision_id=did,
                decision=DecisionAction.STOP,
                confidence=0.9,
                reason_codes=["NO_OPEN_EXPERIMENTS"],
            )
            self._history.append(d)
            return d

        hyp_conf = {h.hypothesis_id: h.confidence for h in hypotheses}

        def score(e: Experiment) -> float:
            h_conf = hyp_conf.get(e.hypothesis_id, 0.5)
            # Prefer high info gain, high hyp confidence, low cost/risk
            return (
                e.information_gain * 0.45
                + h_conf * 0.25
                + (1.0 - e.cost) * 0.15
                + (1.0 - e.risk) * 0.15
            ) * (0.5 + 0.5 * budget_remaining_ratio)

        best = max(open_exps, key=score)
        reason_codes = []
        if best.information_gain >= 0.7:
            reason_codes.append("HIGH_INFORMATION_GAIN")
        if best.cost <= 0.3:
            reason_codes.append("LOW_COST")
        if best.risk <= 0.35:
            reason_codes.append("LOW_RISK")
        reason_codes.append("HYPOTHESIS_DISCRIMINATING")
        if budget_remaining_ratio < 0.3:
            reason_codes.append("BUDGET_PRESSURE")

        # High risk → request approval rather than silent execute
        if best.risk >= 0.6:
            action = DecisionAction.REQUEST_APPROVAL
            reason_codes.append("RISK_THRESHOLD")
        else:
            action = DecisionAction.EXECUTE

        d = Decision(
            decision_id=did,
            decision=action,
            candidate=best.experiment_id,
            confidence=min(0.95, 0.5 + best.information_gain * 0.4),
            reason_codes=reason_codes,
            hypothesis_id=best.hypothesis_id,
            experiment_id=best.experiment_id,
        )
        self._history.append(d)
        return d

    def history(self) -> list[Decision]:
        return list(self._history)
