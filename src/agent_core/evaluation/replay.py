"""
Lightweight research replay (§72 partial).

Reconstruct a summary from checkpoint + episode artifacts for audit.
Not full deterministic re-execution of HTTP (lab limitation).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ReplaySummary:
    engagement_id: str
    source: str
    outcome: str
    stop_reason: str
    hypothesis_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    finding_id: Optional[str] = None
    lessons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    replayable: bool = True
    notes: str = "Artifact-level replay only; not live HTTP re-execution"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def replay_from_engagement_dir(directory: Path) -> ReplaySummary:
    directory = Path(directory)
    eng = {}
    if (directory / "engagement.json").exists():
        eng = json.loads((directory / "engagement.json").read_text())
    ep = {}
    if (directory / "episode.json").exists():
        ep = json.loads((directory / "episode.json").read_text())
    cp = {}
    if (directory / "checkpoint.json").exists():
        cp = json.loads((directory / "checkpoint.json").read_text())
    evidence = {}
    if (directory / "evidence.json").exists():
        evidence = json.loads((directory / "evidence.json").read_text())

    return ReplaySummary(
        engagement_id=eng.get("engagement_id") or ep.get("engagement_id") or cp.get("engagement_id") or "unknown",
        source=str(directory),
        outcome=ep.get("outcome") or cp.get("outcome_so_far") or "unknown",
        stop_reason=ep.get("stop_reason") or cp.get("stop_reason") or "",
        hypothesis_ids=list(ep.get("hypothesis_ids") or cp.get("hypothesis_ids") or []),
        evidence_ids=list(evidence.get("evidence_ids") or ep.get("evidence_ids") or []),
        finding_id=evidence.get("finding_id") or ep.get("finding_id"),
        lessons=list(ep.get("lessons") or []),
        limitations=list(eng.get("limitations") or ep.get("limitations") or []),
    )


def replay_from_objects(
    *,
    engagement_id: str,
    closed: Any,
    checkpoint: Any = None,
) -> ReplaySummary:
    ep = getattr(closed, "episode", None)
    return ReplaySummary(
        engagement_id=engagement_id,
        source="in_memory",
        outcome=ep.outcome if ep else (closed.final_status or ""),
        stop_reason=(ep.stop_reason if ep else None) or closed.stop_reason or "",
        hypothesis_ids=list(ep.hypothesis_ids) if ep else [],
        evidence_ids=list(closed.evidence_ids or []),
        finding_id=closed.finding_id,
        lessons=list(ep.lessons) if ep else [],
        limitations=list(closed.limitations or []),
    )
