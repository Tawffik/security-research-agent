"""Structured runtime events for mobile UI + audit (no raw Python objects)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STARTED = "SESSION_STARTED"
    PHASE_CHANGED = "PHASE_CHANGED"
    HYPOTHESIS_SELECTED = "HYPOTHESIS_SELECTED"
    EXPERIMENT_SELECTED = "EXPERIMENT_SELECTED"
    EXPERIMENT_STARTED = "EXPERIMENT_STARTED"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    NEGATIVE_EVIDENCE_RECORDED = "NEGATIVE_EVIDENCE_RECORDED"
    BRANCH_CREATED = "BRANCH_CREATED"
    BACKTRACK = "BACKTRACK"
    FINDING_VERIFIED = "FINDING_VERIFIED"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    STOPPED = "STOPPED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_FAILED = "SESSION_FAILED"
    SESSION_INCONCLUSIVE = "SESSION_INCONCLUSIVE"
    ERROR = "ERROR"


@dataclass
class RuntimeEvent:
    event_id: str
    session_id: str
    event_type: str
    timestamp: str
    sequence: int
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def create(
        session_id: str,
        event_type: EventType | str,
        *,
        sequence: int,
        message: str = "",
        data: dict[str, Any] | None = None,
    ) -> "RuntimeEvent":
        et = event_type.value if isinstance(event_type, EventType) else str(event_type)
        return RuntimeEvent(
            event_id=f"ev-{uuid4().hex[:12]}",
            session_id=session_id,
            event_type=et,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sequence=sequence,
            message=message,
            data=dict(data or {}),
        )
