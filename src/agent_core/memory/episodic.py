"""
Episodic memory (§62) — what happened during research.

Not semantic knowledge. Not the ledger.
Only WriteGuard-approved entries are stored.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent_core.memory.write_guard import MemoryWriteGuard


@dataclass
class EpisodeMemoryEntry:
    entry_id: str
    engagement_id: str
    created_at: str
    kind: str  # lesson | outcome | surprise | adaptive | regret
    summary: str
    evidence_ids: list[str] = field(default_factory=list)
    provenance: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EpisodicMemory:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0
        self._entries: list[EpisodeMemoryEntry] = []
        self.guard = MemoryWriteGuard()

    def try_add(
        self,
        *,
        kind: str,
        summary: str,
        evidence_ids: Optional[list[str]] = None,
        provenance: str = "research_episode",
        confidence: float = 0.6,
        source: str = "episode",
    ) -> Optional[EpisodeMemoryEntry]:
        decision = self.guard.evaluate(
            content=summary,
            source=source,
            has_evidence=bool(evidence_ids),
            is_structured_summary=True,
        )
        if not decision.allowed:
            return None

        self._n += 1
        entry = EpisodeMemoryEntry(
            entry_id=f"EM-{self._n:03d}",
            engagement_id=self.engagement_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            summary=decision.sanitized_summary or summary[:500],
            evidence_ids=list(evidence_ids or []),
            provenance=provenance,
            confidence=confidence,
        )
        self._entries.append(entry)
        return entry

    def list_all(self) -> list[EpisodeMemoryEntry]:
        return list(self._entries)

    def write_jsonl(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in self._entries:
                f.write(json.dumps(e.to_dict()) + "\n")
        return path

    def ingest_from_pipeline(
        self,
        *,
        closed: Any,
        adaptive: Any,
        surprises: Optional[list[Any]] = None,
        episode_lessons: Optional[list[str]] = None,
    ) -> list[EpisodeMemoryEntry]:
        """Pull structured lessons only — never raw observation bodies."""
        added: list[EpisodeMemoryEntry] = []
        evidence = list(getattr(closed, "evidence_ids", None) or [])

        outcome = "confirmed" if closed.referee_accepted else (closed.final_status or "unknown")
        e = self.try_add(
            kind="outcome",
            summary=f"Outcome={outcome}; stop={closed.stop_reason}; finding={closed.finding_id}",
            evidence_ids=evidence,
            provenance="closed_loop",
            confidence=0.8 if evidence else 0.4,
            source="episode",
        )
        if e:
            added.append(e)

        for lesson in episode_lessons or []:
            e = self.try_add(
                kind="lesson",
                summary=lesson,
                evidence_ids=evidence,
                provenance="research_episode.lessons",
                confidence=0.7,
                source="lesson",
            )
            if e:
                added.append(e)

        if adaptive is not None:
            e = self.try_add(
                kind="adaptive",
                summary=f"Adaptive: stop={adaptive.stop} action={adaptive.next_action} reason={adaptive.stop_reason}",
                evidence_ids=evidence,
                provenance="adaptive_loop",
                confidence=0.65,
                source="adaptive_note",
            )
            if e:
                added.append(e)

        for s in surprises or []:
            e = self.try_add(
                kind="surprise",
                summary=f"Surprise {s.surprise_id}: expected {s.expected} observed {s.observed}; hyps={s.candidate_hypotheses[:2]}",
                evidence_ids=evidence,
                provenance="surprise_engine",
                confidence=0.7 if s.severity == "high" else 0.5,
                source="surprise",
            )
            if e:
                added.append(e)

        # Explicitly attempt raw body — must be rejected by guard (for tests/callers)
        return added
