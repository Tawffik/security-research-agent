"""First-class research session lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    INCONCLUSIVE = "INCONCLUSIVE"


TERMINAL = {
    SessionStatus.COMPLETED,
    SessionStatus.FAILED,
    SessionStatus.BLOCKED,
    SessionStatus.CANCELLED,
    SessionStatus.INCONCLUSIVE,
}


@dataclass
class ResearchSession:
    session_id: str
    created_at: str
    updated_at: str
    status: str = SessionStatus.CREATED.value
    label: str = ""
    recon_path: str = ""
    scope_path: str = ""
    live_http: bool = False  # always false unless explicitly authorized later
    current_phase: str = "idle"
    current_hypothesis: str = ""
    current_experiment: str = ""
    latest_observation: str = ""
    latest_evidence: str = ""
    latest_finding: str = ""
    trajectory_summary: str = ""
    error: str = ""
    checkpoint_reference: str = ""
    evidence_count: int = 0
    negative_evidence_count: int = 0
    outcome: str = ""
    stop_reason: str = ""
    report: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def new(*, label: str = "", recon_path: str = "", scope_path: str = "") -> "ResearchSession":
        now = datetime.now(timezone.utc).isoformat()
        return ResearchSession(
            session_id=f"sess-{uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            status=SessionStatus.CREATED.value,
            label=label or "research",
            recon_path=recon_path,
            scope_path=scope_path,
            live_http=False,
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def is_terminal(self) -> bool:
        try:
            return SessionStatus(self.status) in TERMINAL
        except ValueError:
            return False
