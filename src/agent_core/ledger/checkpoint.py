"""
Research checkpoints (§66).

Before important adaptive decisions, snapshot:
  beliefs, hypotheses statuses, opportunities summary,
  evidence ids, budget hint, stop/outcome, execution position.

Enables future backtracking when evidence invalidates a path.
Does not claim full replay engine yet.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class Checkpoint:
    checkpoint_id: str
    engagement_id: str
    created_at: str
    label: str
    outcome_so_far: str
    stop_reason: str
    hypothesis_ids: list[str] = field(default_factory=list)
    hypothesis_statuses: dict[str, str] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    opportunity_ids: list[str] = field(default_factory=list)
    finding_id: Optional[str] = None
    belief_summaries: list[str] = field(default_factory=list)
    execution_position: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class CheckpointStore:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0
        self._items: list[Checkpoint] = []

    def create(
        self,
        *,
        label: str,
        outcome_so_far: str = "",
        stop_reason: str = "",
        hypothesis_ids: Optional[list[str]] = None,
        hypothesis_statuses: Optional[dict[str, str]] = None,
        evidence_ids: Optional[list[str]] = None,
        opportunity_ids: Optional[list[str]] = None,
        finding_id: Optional[str] = None,
        belief_summaries: Optional[list[str]] = None,
        execution_position: str = "",
        notes: Optional[list[str]] = None,
    ) -> Checkpoint:
        self._n += 1
        cp = Checkpoint(
            checkpoint_id=f"CP-{self._n:03d}",
            engagement_id=self.engagement_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            label=label,
            outcome_so_far=outcome_so_far,
            stop_reason=stop_reason,
            hypothesis_ids=list(hypothesis_ids or []),
            hypothesis_statuses=dict(hypothesis_statuses or {}),
            evidence_ids=list(evidence_ids or []),
            opportunity_ids=list(opportunity_ids or []),
            finding_id=finding_id,
            belief_summaries=list(belief_summaries or []),
            execution_position=execution_position,
            notes=list(notes or []),
        )
        self._items.append(cp)
        return cp

    def latest(self) -> Optional[Checkpoint]:
        return self._items[-1] if self._items else None

    def list_all(self) -> list[Checkpoint]:
        return list(self._items)

    def write(self, checkpoint: Checkpoint, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{checkpoint.checkpoint_id}.json"
        path.write_text(checkpoint.to_json())
        return path

    def from_closed_and_adaptive(
        self,
        closed: Any,
        adaptive: Any,
        *,
        label: str = "pre_adaptive_decision",
    ) -> Checkpoint:
        hyps = list(getattr(closed.plan, "hypotheses", None) or [])
        statuses = {}
        ids = []
        for h in hyps:
            hid = getattr(h, "hypothesis_id", None)
            if not hid:
                continue
            ids.append(hid)
            st = getattr(h, "status", None)
            statuses[hid] = st.value if hasattr(st, "value") else str(st)

        opp_ids = [o.opportunity_id for o in (adaptive.reranked_opportunities or [])[:10]]

        return self.create(
            label=label,
            outcome_so_far=adaptive.prior_outcome,
            stop_reason=adaptive.stop_reason or closed.stop_reason or "",
            hypothesis_ids=ids,
            hypothesis_statuses=statuses,
            evidence_ids=list(closed.evidence_ids or []),
            opportunity_ids=opp_ids,
            finding_id=closed.finding_id,
            belief_summaries=list(closed.belief_updates or []),
            execution_position=(
                "adaptive_stop" if adaptive.stop else f"adaptive_{adaptive.next_action}"
            ),
            notes=list(adaptive.notes or [])[:8],
        )
