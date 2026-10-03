"""
Current Research Brief — bounded reasoning context (offline).

Compresses episode state for next decision without dumping full history.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ResearchBrief:
    episode_id: str = ""
    engagement_id: str = ""
    target_host: str = ""
    active_hypothesis_ids: list[str] = field(default_factory=list)
    belief_summaries: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    evidence_debt: list[str] = field(default_factory=list)
    failed_paths: list[str] = field(default_factory=list)
    stop_reason: str = ""
    next_decision: str = ""
    scope_state: str = ""
    capability_notes: list[str] = field(default_factory=list)
    selected_experiment_id: str = ""
    differential_change_kind: str = ""
    evidence_graph_edge_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_brief_from_closed_loop(result: Any, *, engagement_id: str = "") -> ResearchBrief:
    """Build brief from ClosedLoopResult — no model calls."""
    plan = getattr(result, "plan", None)
    ctx = getattr(plan, "target_context", None) if plan else None
    hyps = list(getattr(plan, "hypotheses", None) or [])
    open_ids = [
        h.hypothesis_id
        for h in hyps
        if getattr(getattr(h, "status", None), "value", str(getattr(h, "status", ""))) == "open"
        or str(getattr(h, "status", "")).endswith("OPEN")
        or getattr(h, "status", None) and str(h.status) == "open"
    ]
    if not open_ids:
        open_ids = [h.hypothesis_id for h in hyps[:5]]

    beliefs = list(getattr(result, "belief_updates", None) or [])
    unknowns: list[str] = []
    if plan and getattr(plan, "unknowns", None):
        unknowns = [getattr(u, "statement", None) or str(u) for u in plan.unknowns[:10]]

    debt: list[str] = []
    diff = getattr(result, "differential_result", None) or {}
    if isinstance(diff, dict) and diff.get("change_kind") in ("insufficient", "no_change", "noisy_change"):
        debt.append(f"differential:{diff.get('change_kind')}")
    if getattr(result, "knowledge_procedure_required_blocked", False):
        debt.append("knowledge_procedure_required")

    failed: list[str] = []
    if not getattr(result, "scope_allowed", True):
        failed.append("scope_denied")
    if getattr(result, "budget_exhausted", False):
        failed.append("budget_exhausted")

    next_decision = "continue"
    if getattr(result, "referee_accepted", False):
        next_decision = "stop_verified"
    elif getattr(result, "final_status", "") == "rejected":
        next_decision = "stop_disproved"
    elif debt:
        next_decision = "design_next_discriminating_experiment"
    elif not getattr(result, "scope_allowed", True):
        next_decision = "scope_blocked"

    return ResearchBrief(
        episode_id=getattr(getattr(result, "episode", None), "episode_id", "") or "",
        engagement_id=engagement_id or getattr(result, "engagement_id", "") or "",
        target_host=getattr(ctx, "primary_host", "") if ctx else "",
        active_hypothesis_ids=open_ids,
        belief_summaries=beliefs[:10],
        unknowns=unknowns,
        evidence_debt=debt,
        failed_paths=failed,
        stop_reason=getattr(result, "stop_reason", "") or "",
        next_decision=next_decision,
        scope_state="allowed" if getattr(result, "scope_allowed", False) else "denied",
        selected_experiment_id=getattr(result, "selected_experiment_id", "") or "",
        differential_change_kind=(diff.get("change_kind") if isinstance(diff, dict) else "") or "",
        evidence_graph_edge_count=len(getattr(result, "evidence_graph", None) or []),
    )
