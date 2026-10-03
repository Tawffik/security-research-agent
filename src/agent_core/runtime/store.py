"""SQLite + JSON persistence for sessions and events."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from agent_core.runtime.events import RuntimeEvent
from agent_core.runtime.session import ResearchSession


class SessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._lock:
            with self._conn() as c:
                c.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        data TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS events (
                        event_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        sequence INTEGER NOT NULL,
                        data TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_events_sess_seq
                        ON events(session_id, sequence);
                    """
                )

    def save_session(self, session: ResearchSession) -> None:
        session.touch()
        payload = json.dumps(session.to_dict())
        with self._lock:
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO sessions(session_id, data) VALUES (?, ?)",
                    (session.session_id, payload),
                )

    def get_session(self, session_id: str) -> Optional[ResearchSession]:
        with self._lock:
            with self._conn() as c:
                row = c.execute(
                    "SELECT data FROM sessions WHERE session_id=?", (session_id,)
                ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row["data"])
            return ResearchSession(**data)
        except Exception:
            return None

    def list_sessions(self) -> list[ResearchSession]:
        with self._lock:
            with self._conn() as c:
                rows = c.execute("SELECT data FROM sessions").fetchall()
        out: list[ResearchSession] = []
        for row in rows:
            try:
                out.append(ResearchSession(**json.loads(row["data"])))
            except Exception:
                continue
        out.sort(key=lambda s: s.updated_at, reverse=True)
        return out

    def append_event(self, event: RuntimeEvent) -> None:
        with self._lock:
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO events(event_id, session_id, sequence, data) VALUES (?,?,?,?)",
                    (event.event_id, event.session_id, event.sequence, json.dumps(event.to_dict())),
                )

    def list_events(self, session_id: str, after_sequence: int = 0) -> list[RuntimeEvent]:
        with self._lock:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT data FROM events WHERE session_id=? AND sequence>? ORDER BY sequence ASC",
                    (session_id, after_sequence),
                ).fetchall()
        out: list[RuntimeEvent] = []
        for row in rows:
            try:
                d = json.loads(row["data"])
                out.append(RuntimeEvent(**d))
            except Exception:
                continue
        return out

    def next_sequence(self, session_id: str) -> int:
        with self._lock:
            with self._conn() as c:
                row = c.execute(
                    "SELECT MAX(sequence) AS m FROM events WHERE session_id=?",
                    (session_id,),
                ).fetchone()
        m = row["m"] if row and row["m"] is not None else 0
        return int(m) + 1
