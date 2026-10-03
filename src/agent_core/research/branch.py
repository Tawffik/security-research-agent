"""
Gate 7 foundation (offline) — explicit research branches + backtracking.

Backtracking must produce a materially different path; do not silently
replay the same failed branch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


@dataclass
class ResearchBranch:
    branch_id: str
    parent_checkpoint: str = ""
    parent_branch_id: str = ""
    hypothesis_path: list[str] = field(default_factory=list)
    experiment_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    termination_reason: str = ""
    return_target: str = ""
    failed_fingerprint: str = ""  # hash of hyp+exp path to avoid identical replay
    active: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineageEvent:
    event_id: str
    parent_event_id: str = ""
    episode_id: str = ""
    event_type: str = ""
    actor: str = ""
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    state_before_hash: str = ""
    state_after_hash: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(hypothesis_ids: list[str], experiment_ids: list[str]) -> str:
    raw = "|".join(sorted(hypothesis_ids)) + "#" + "|".join(sorted(experiment_ids))
    return str(hash(raw))


class BranchManager:
    def __init__(self, episode_id: str = ""):
        self.episode_id = episode_id
        self.branches: list[ResearchBranch] = []
        self.events: list[LineageEvent] = []
        self._fingerprints_tried: set[str] = set()

    def open_branch(
        self,
        *,
        hypothesis_ids: list[str] | None = None,
        parent_checkpoint: str = "",
        parent_branch_id: str = "",
    ) -> ResearchBranch:
        b = ResearchBranch(
            branch_id=f"br-{uuid4().hex[:10]}",
            parent_checkpoint=parent_checkpoint,
            parent_branch_id=parent_branch_id,
            hypothesis_path=list(hypothesis_ids or []),
            created_at=_ts(),
        )
        self.branches.append(b)
        self.record_event(
            "branch_open",
            actor="BranchManager",
            output_refs=[b.branch_id],
            input_refs=[parent_checkpoint] if parent_checkpoint else [],
        )
        return b

    def record_experiment(self, branch_id: str, experiment_id: str) -> None:
        for b in self.branches:
            if b.branch_id == branch_id:
                b.experiment_ids.append(experiment_id)
                break

    def terminate(
        self,
        branch_id: str,
        reason: str,
        *,
        return_target: str = "",
    ) -> ResearchBranch | None:
        for b in self.branches:
            if b.branch_id == branch_id:
                b.termination_reason = reason
                b.return_target = return_target
                b.active = False
                b.failed_fingerprint = _fingerprint(b.hypothesis_path, b.experiment_ids)
                self._fingerprints_tried.add(b.failed_fingerprint)
                self.record_event(
                    "branch_terminate",
                    actor="BranchManager",
                    input_refs=[branch_id],
                    output_refs=[reason],
                )
                return b
        return None

    def can_open_same_path(
        self, hypothesis_ids: list[str], experiment_ids: list[str]
    ) -> bool:
        """False if identical hyp+exp fingerprint already failed."""
        fp = _fingerprint(hypothesis_ids, experiment_ids)
        return fp not in self._fingerprints_tried

    def backtrack(
        self,
        from_branch_id: str,
        *,
        new_hypothesis_ids: list[str],
        parent_checkpoint: str = "",
    ) -> ResearchBranch | None:
        parent = next((b for b in self.branches if b.branch_id == from_branch_id), None)
        if parent is None:
            return None
        # Must differ from failed path
        if not self.can_open_same_path(new_hypothesis_ids, parent.experiment_ids):
            # still blocked if same hyp+exp
            if not self.can_open_same_path(new_hypothesis_ids, []):
                return None
        nb = self.open_branch(
            hypothesis_ids=new_hypothesis_ids,
            parent_checkpoint=parent_checkpoint or parent.parent_checkpoint,
            parent_branch_id=from_branch_id,
        )
        self.record_event(
            "backtrack",
            actor="BranchManager",
            input_refs=[from_branch_id],
            output_refs=[nb.branch_id],
        )
        return nb

    def record_event(
        self,
        event_type: str,
        *,
        actor: str = "",
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
        parent_event_id: str = "",
        state_before_hash: str = "",
        state_after_hash: str = "",
    ) -> LineageEvent:
        ev = LineageEvent(
            event_id=f"evt-{uuid4().hex[:10]}",
            parent_event_id=parent_event_id or (self.events[-1].event_id if self.events else ""),
            episode_id=self.episode_id,
            event_type=event_type,
            actor=actor,
            input_refs=list(input_refs or []),
            output_refs=list(output_refs or []),
            state_before_hash=state_before_hash,
            state_after_hash=state_after_hash,
            timestamp=_ts(),
        )
        self.events.append(ev)
        return ev


def branch_manager_snapshot(manager: "BranchManager") -> dict[str, Any]:
    """Serialize branch graph + lineage for offline replay stress."""
    return {
        "episode_id": manager.episode_id,
        "branches": [b.to_dict() for b in manager.branches],
        "events": [e.to_dict() for e in manager.events],
        "fingerprints_tried": sorted(manager._fingerprints_tried),
    }


def branch_manager_from_snapshot(data: dict[str, Any]) -> "BranchManager":
    """Restore BranchManager from snapshot — deterministic structure, not live re-exec."""
    m = BranchManager(episode_id=str(data.get("episode_id") or ""))
    for bd in data.get("branches") or []:
        b = ResearchBranch(
            branch_id=bd["branch_id"],
            parent_checkpoint=bd.get("parent_checkpoint") or "",
            parent_branch_id=bd.get("parent_branch_id") or "",
            hypothesis_path=list(bd.get("hypothesis_path") or []),
            experiment_ids=list(bd.get("experiment_ids") or []),
            observation_ids=list(bd.get("observation_ids") or []),
            evidence_ids=list(bd.get("evidence_ids") or []),
            termination_reason=bd.get("termination_reason") or "",
            return_target=bd.get("return_target") or "",
            failed_fingerprint=bd.get("failed_fingerprint") or "",
            active=bool(bd.get("active", True)),
            created_at=bd.get("created_at") or "",
        )
        m.branches.append(b)
    for ed in data.get("events") or []:
        m.events.append(
            LineageEvent(
                event_id=ed["event_id"],
                parent_event_id=ed.get("parent_event_id") or "",
                episode_id=ed.get("episode_id") or "",
                event_type=ed.get("event_type") or "",
                actor=ed.get("actor") or "",
                input_refs=list(ed.get("input_refs") or []),
                output_refs=list(ed.get("output_refs") or []),
                state_before_hash=ed.get("state_before_hash") or "",
                state_after_hash=ed.get("state_after_hash") or "",
                timestamp=ed.get("timestamp") or "",
            )
        )
    for fp in data.get("fingerprints_tried") or []:
        m._fingerprints_tried.add(fp)
    return m
