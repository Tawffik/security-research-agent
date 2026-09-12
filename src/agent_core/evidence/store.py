"""
Evidence Store — MASTER SPEC §9 (Evidence-First Model).

Every claim a Skill makes must cite an Evidence object here; nothing is
allowed to become a Finding purely from model intuition. The store is
append-only and hash-chained (like a minimal ledger-of-record) so that a
report can prove "this evidence was not edited after the fact" — which
matters when a bounty program disputes a submission's authenticity.

Negative evidence (things that were tried and did NOT confirm a hypothesis)
is stored with equal weight to positive evidence. This is what stops the
agent from re-running a dead-end investigation after a restart.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class EvidencePolarity(str, Enum):
    POSITIVE = "positive"   # supports a hypothesis
    NEGATIVE = "negative"   # refutes a hypothesis / a dead end worth remembering
    NEUTRAL = "neutral"     # an observation with no verdict yet


class FindingStatus(str, Enum):
    CANDIDATE = "candidate"
    LIKELY = "likely"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass
class Evidence:
    evidence_id: str
    target: str
    action: str            # what was done, e.g. "sent GET /api/v1/users/123"
    input_data: str        # what was sent (kept as data, never re-executed)
    expected: str
    observed: str
    artifact_path: Optional[str]   # screenshot / raw response saved to disk
    polarity: EvidencePolarity
    confidence: float
    related_hypothesis: Optional[str]
    source: str             # which skill / tool produced this
    timestamp: float
    prev_hash: str
    self_hash: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "evidence_id": self.evidence_id,
                "target": self.target,
                "action": self.action,
                "input_data": self.input_data,
                "expected": self.expected,
                "observed": self.observed,
                "polarity": self.polarity.value,
                "confidence": self.confidence,
                "timestamp": self.timestamp,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    action TEXT NOT NULL,
    input_data TEXT NOT NULL,
    expected TEXT NOT NULL,
    observed TEXT NOT NULL,
    artifact_path TEXT,
    polarity TEXT NOT NULL,
    confidence REAL NOT NULL,
    related_hypothesis TEXT,
    source TEXT NOT NULL,
    timestamp REAL NOT NULL,
    prev_hash TEXT NOT NULL,
    self_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,
    duplicate_of TEXT,
    severity TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class EvidenceStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @classmethod
    def open(cls, path: str | Path) -> "EvidenceStore":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(str(path)))

    def _last_hash(self) -> str:
        row = self.conn.execute(
            "SELECT self_hash FROM evidence ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else "GENESIS"

    def record(
        self,
        target: str,
        action: str,
        input_data: str,
        expected: str,
        observed: str,
        polarity: EvidencePolarity,
        confidence: float,
        source: str,
        related_hypothesis: Optional[str] = None,
        artifact_path: Optional[str] = None,
    ) -> Evidence:
        ev = Evidence(
            evidence_id=str(uuid.uuid4()),
            target=target,
            action=action,
            input_data=input_data,
            expected=expected,
            observed=observed,
            artifact_path=artifact_path,
            polarity=polarity,
            confidence=confidence,
            related_hypothesis=related_hypothesis,
            source=source,
            timestamp=time.time(),
            prev_hash=self._last_hash(),
        )
        ev.self_hash = ev.compute_hash()
        self.conn.execute(
            """INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ev.evidence_id, ev.target, ev.action, ev.input_data, ev.expected,
                ev.observed, ev.artifact_path, ev.polarity.value, ev.confidence,
                ev.related_hypothesis, ev.source, ev.timestamp, ev.prev_hash, ev.self_hash,
            ),
        )
        self.conn.commit()
        return ev

    def verify_chain(self) -> bool:
        """Detects post-hoc tampering: recomputes every hash and checks linkage."""
        rows = self.conn.execute("SELECT * FROM evidence ORDER BY timestamp ASC").fetchall()
        prev = "GENESIS"
        for row in rows:
            ev = Evidence(
                evidence_id=row[0], target=row[1], action=row[2], input_data=row[3],
                expected=row[4], observed=row[5], artifact_path=row[6],
                polarity=EvidencePolarity(row[7]), confidence=row[8],
                related_hypothesis=row[9], source=row[10], timestamp=row[11],
                prev_hash=row[12], self_hash=row[13],
            )
            if ev.prev_hash != prev:
                return False
            if ev.compute_hash() != ev.self_hash:
                return False
            prev = ev.self_hash
        return True

    def negative_evidence_for(self, hypothesis: str) -> list[Evidence]:
        """Call this BEFORE re-attempting a hypothesis after resume."""
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE related_hypothesis=? AND polarity=?",
            (hypothesis, EvidencePolarity.NEGATIVE.value),
        ).fetchall()
        return [self._row_to_evidence(r) for r in rows]

    def _row_to_evidence(self, row) -> Evidence:
        return Evidence(
            evidence_id=row[0], target=row[1], action=row[2], input_data=row[3],
            expected=row[4], observed=row[5], artifact_path=row[6],
            polarity=EvidencePolarity(row[7]), confidence=row[8],
            related_hypothesis=row[9], source=row[10], timestamp=row[11],
            prev_hash=row[12], self_hash=row[13],
        )

    # -- findings ---------------------------------------------------------

    def create_finding(self, title: str, evidence_ids: list[str], severity: str = "unknown") -> str:
        finding_id = str(uuid.uuid4())
        now = time.time()
        self.conn.execute(
            "INSERT INTO findings VALUES (?,?,?,?,?,?,?,?)",
            (finding_id, title, FindingStatus.CANDIDATE.value, json.dumps(evidence_ids), None, severity, now, now),
        )
        self.conn.commit()
        return finding_id

    def set_finding_status(self, finding_id: str, status: FindingStatus, duplicate_of: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE findings SET status=?, duplicate_of=?, updated_at=? WHERE finding_id=?",
            (status.value, duplicate_of, time.time(), finding_id),
        )
        self.conn.commit()
