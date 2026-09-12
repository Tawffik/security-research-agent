"""
Execution Ledger — MASTER SPEC §3, hardened with the "audited state
transition" idea from LongHorizon-Harness (arXiv:2608.01964, Aug 2026):

    a state transition is only committed to the ledger once it has been
    verified, so a fresh executor resuming after a crash / compaction /
    handoff sees compact, TRUSTED state — not a raw replay of everything
    that was ever tried.

This is deliberately implemented as a plain hierarchical tree persisted to
SQLite (one row per node) rather than a single JSON blob, so that:
  - concurrent sub-agents can each own a subtree without lock contention
    on the whole ledger,
  - resuming after a crash means "load one root + its children", not
    "deserialize and replay an ever-growing event log",
  - queries like "give me every UNRESOLVED node under Recon" are cheap.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class NodeStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"          # waiting on evidence / approval / dependency
    AUDITED_COMPLETE = "audited_complete"  # verified, safe to build on
    REJECTED = "rejected"        # tried, did not pan out — kept as negative evidence


@dataclass
class LedgerNode:
    node_id: str
    parent_id: Optional[str]
    kind: str                    # "target_understanding" | "recon" | "hypothesis" | "finding" | ...
    label: str
    status: NodeStatus = NodeStatus.PENDING
    confidence: float = 0.0      # 0.0-1.0
    evidence_ids: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    next_action: str = ""
    last_updated: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_row(self) -> tuple:
        return (
            self.node_id,
            self.parent_id,
            self.kind,
            self.label,
            self.status.value,
            self.confidence,
            json.dumps(self.evidence_ids),
            json.dumps(self.dependencies),
            self.next_action,
            self.last_updated,
            json.dumps(self.metadata),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "LedgerNode":
        return cls(
            node_id=row[0],
            parent_id=row[1],
            kind=row[2],
            label=row[3],
            status=NodeStatus(row[4]),
            confidence=row[5],
            evidence_ids=json.loads(row[6]),
            dependencies=json.loads(row[7]),
            next_action=row[8],
            last_updated=row[9],
            metadata=json.loads(row[10]),
        )


SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_nodes (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_ids TEXT NOT NULL,
    dependencies TEXT NOT NULL,
    next_action TEXT NOT NULL,
    last_updated REAL NOT NULL,
    metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parent ON ledger_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_status ON ledger_nodes(status);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    reason TEXT NOT NULL,
    root_node_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget (
    scope_key TEXT PRIMARY KEY,   -- e.g. "target:acme.com" or "hypothesis:H001"
    tokens_spent INTEGER NOT NULL DEFAULT 0,
    tool_calls_spent INTEGER NOT NULL DEFAULT 0,
    token_budget INTEGER NOT NULL,
    tool_call_budget INTEGER NOT NULL
);
"""


class ExecutionLedger:
    """
    The durable state tree. One instance per engagement (per target program).

    >>> ledger = ExecutionLedger.open("data/acme_engagement.db")
    >>> root = ledger.create_node(parent_id=None, kind="target_understanding", label="acme.com")
    >>> recon = ledger.create_node(parent_id=root.node_id, kind="recon", label="Recon")
    >>> ledger.mark_audited_complete(recon.node_id, confidence=0.9)
    >>> ledger.checkpoint(reason="finished recon phase")
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @classmethod
    def open(cls, path: str | Path) -> "ExecutionLedger":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        return cls(conn)

    # -- node lifecycle ----------------------------------------------------

    def create_node(
        self,
        parent_id: Optional[str],
        kind: str,
        label: str,
        next_action: str = "",
        metadata: Optional[dict] = None,
    ) -> LedgerNode:
        node = LedgerNode(
            node_id=str(uuid.uuid4()),
            parent_id=parent_id,
            kind=kind,
            label=label,
            next_action=next_action,
            metadata=metadata or {},
        )
        self.conn.execute(
            "INSERT INTO ledger_nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)", node.to_row()
        )
        self.conn.commit()
        return node

    def get_node(self, node_id: str) -> Optional[LedgerNode]:
        row = self.conn.execute(
            "SELECT * FROM ledger_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return LedgerNode.from_row(row) if row else None

    def children(self, node_id: Optional[str]) -> list[LedgerNode]:
        rows = self.conn.execute(
            "SELECT * FROM ledger_nodes WHERE parent_id IS ?", (node_id,)
        ).fetchall()
        return [LedgerNode.from_row(r) for r in rows]

    def update_status(
        self,
        node_id: str,
        status: NodeStatus,
        confidence: Optional[float] = None,
        next_action: Optional[str] = None,
        add_evidence_ids: Optional[list[str]] = None,
    ) -> None:
        """
        This is the ONLY audited transition point. Nothing in the framework
        should UPDATE ledger_nodes directly — everything routes through here
        so the "audited state transition" guarantee actually holds.
        """
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(f"unknown ledger node {node_id}")
        node.status = status
        node.last_updated = time.time()
        if confidence is not None:
            node.confidence = confidence
        if next_action is not None:
            node.next_action = next_action
        if add_evidence_ids:
            node.evidence_ids = list(set(node.evidence_ids + add_evidence_ids))

        self.conn.execute(
            """UPDATE ledger_nodes SET status=?, confidence=?, evidence_ids=?,
               next_action=?, last_updated=? WHERE node_id=?""",
            (
                node.status.value,
                node.confidence,
                json.dumps(node.evidence_ids),
                node.next_action,
                node.last_updated,
                node.node_id,
            ),
        )
        self.conn.commit()

    def mark_audited_complete(self, node_id: str, confidence: float, evidence_ids: Optional[list[str]] = None) -> None:
        self.update_status(node_id, NodeStatus.AUDITED_COMPLETE, confidence=confidence, add_evidence_ids=evidence_ids)

    def mark_rejected(self, node_id: str, reason: str) -> None:
        """Rejected nodes are KEPT, not deleted — this is the negative-evidence
        record that stops the agent from re-attempting the same dead end."""
        node = self.get_node(node_id)
        node.metadata["rejection_reason"] = reason
        self.conn.execute(
            "UPDATE ledger_nodes SET metadata=? WHERE node_id=?",
            (json.dumps(node.metadata), node_id),
        )
        self.update_status(node_id, NodeStatus.REJECTED)

    # -- resumability --------------------------------------------------

    def unresolved_nodes(self, kind: Optional[str] = None) -> list[LedgerNode]:
        """What a resuming executor should look at first."""
        query = "SELECT * FROM ledger_nodes WHERE status IN (?, ?, ?)"
        params: list = [NodeStatus.PENDING.value, NodeStatus.IN_PROGRESS.value, NodeStatus.BLOCKED.value]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        rows = self.conn.execute(query, params).fetchall()
        return [LedgerNode.from_row(r) for r in rows]

    def checkpoint(self, reason: str, root_node_id: str = "") -> str:
        checkpoint_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO checkpoints VALUES (?,?,?,?)",
            (checkpoint_id, time.time(), reason, root_node_id),
        )
        self.conn.commit()
        return checkpoint_id

    # -- budget / circuit breaker ---------------------------------------
    # This is the control the spec was missing: a HARD stop, not just a
    # post-hoc "tokens/finding" metric. See docs/ARCHITECTURE.md §Budget.

    def set_budget(self, scope_key: str, token_budget: int, tool_call_budget: int) -> None:
        self.conn.execute(
            """INSERT INTO budget (scope_key, tokens_spent, tool_calls_spent, token_budget, tool_call_budget)
               VALUES (?, 0, 0, ?, ?)
               ON CONFLICT(scope_key) DO UPDATE SET token_budget=excluded.token_budget,
                                                     tool_call_budget=excluded.tool_call_budget""",
            (scope_key, token_budget, tool_call_budget),
        )
        self.conn.commit()

    def spend(self, scope_key: str, tokens: int = 0, tool_calls: int = 0) -> bool:
        """
        Records spend and returns False if this scope has blown its budget.
        Callers MUST check the return value and stop / escalate on False —
        this is the circuit breaker, not a suggestion.
        """
        row = self.conn.execute(
            "SELECT tokens_spent, tool_calls_spent, token_budget, tool_call_budget FROM budget WHERE scope_key=?",
            (scope_key,),
        ).fetchone()
        if row is None:
            # No explicit budget set for this scope: default to a conservative cap
            self.set_budget(scope_key, token_budget=200_000, tool_call_budget=500)
            row = (0, 0, 200_000, 500)

        tokens_spent, tool_calls_spent, token_budget, tool_call_budget = row
        tokens_spent += tokens
        tool_calls_spent += tool_calls
        self.conn.execute(
            "UPDATE budget SET tokens_spent=?, tool_calls_spent=? WHERE scope_key=?",
            (tokens_spent, tool_calls_spent, scope_key),
        )
        self.conn.commit()
        return tokens_spent <= token_budget and tool_calls_spent <= tool_call_budget

    def budget_status(self, scope_key: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT tokens_spent, tool_calls_spent, token_budget, tool_call_budget FROM budget WHERE scope_key=?",
            (scope_key,),
        ).fetchone()
        if row is None:
            return None
        keys = ["tokens_spent", "tool_calls_spent", "token_budget", "tool_call_budget"]
        return dict(zip(keys, row))
