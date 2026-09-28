"""
Source quality layer — external/Notion sources are never auto-trusted.

States: UNVERIFIED | REVIEWED | ACCEPTED | REJECTED | DUPLICATE
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SourceStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class SourceType(str, Enum):
    WRITEUP = "writeup"
    ADVISORY = "advisory"
    ACADEMY = "academy"
    STANDARD = "standard"
    NOTION = "notion"
    RESEARCH_PAPER = "research_paper"
    AGENT_EPISODE = "agent_episode"
    OTHER = "other"


@dataclass
class SourceQualitySignals:
    technical_depth: float = 0.0  # 0..1 heuristic
    reproducibility: float = 0.0
    concrete_evidence: float = 0.0
    clear_preconditions: float = 0.0
    clear_root_cause: float = 0.0
    demonstrated_impact: float = 0.0
    novelty: float = 0.0
    source_reliability: float = 0.5
    relevance: float = 0.5
    duplication_risk: float = 0.0

    def priority_score(self) -> float:
        """Higher = process sooner. Penalize duplication."""
        raw = (
            0.15 * self.technical_depth
            + 0.15 * self.reproducibility
            + 0.15 * self.concrete_evidence
            + 0.1 * self.clear_preconditions
            + 0.1 * self.clear_root_cause
            + 0.1 * self.demonstrated_impact
            + 0.1 * self.novelty
            + 0.1 * self.source_reliability
            + 0.05 * self.relevance
        )
        return max(0.0, min(1.0, raw * (1.0 - 0.5 * self.duplication_risk)))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority_score"] = self.priority_score()
        return d


@dataclass
class SourceRecord:
    source_id: str
    source_type: SourceType
    origin: str
    title: str = ""
    author: str = ""
    url: str = ""
    publication_date: str = ""
    acquired_at: str = ""
    status: SourceStatus = SourceStatus.UNVERIFIED
    extraction_status: str = "pending"  # pending | extracted | failed
    validation_status: str = "none"
    reliability: float = 0.5
    signals: SourceQualitySignals = field(default_factory=SourceQualitySignals)
    provenance: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "origin": self.origin,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "publication_date": self.publication_date,
            "acquired_at": self.acquired_at or datetime.now(timezone.utc).isoformat(),
            "status": self.status.value,
            "extraction_status": self.extraction_status,
            "validation_status": self.validation_status,
            "reliability": self.reliability,
            "signals": self.signals.to_dict(),
            "provenance": dict(self.provenance),
            "notes": self.notes,
        }


def score_writeup_text(text: str, *, origin: str = "") -> SourceQualitySignals:
    """Deterministic heuristics only — not trust assignment."""
    low = (text or "").lower()
    sig = SourceQualitySignals()
    # depth markers
    depth_hits = sum(
        1
        for k in (
            "request",
            "response",
            "status",
            "payload",
            "parameter",
            "authorization",
            "ownership",
            "root cause",
            "reproduction",
        )
        if k in low
    )
    sig.technical_depth = min(1.0, depth_hits / 6.0)
    sig.reproducibility = 0.7 if "repro" in low or "steps to" in low else 0.3
    sig.concrete_evidence = 0.7 if "http" in low or "status" in low else 0.2
    sig.clear_preconditions = 0.6 if "precondition" in low or "require" in low else 0.25
    sig.clear_root_cause = 0.7 if "root cause" in low or "because" in low else 0.2
    sig.demonstrated_impact = 0.6 if "impact" in low or "access" in low else 0.2
    if "portswigger" in origin.lower() or "owasp" in origin.lower():
        sig.source_reliability = 0.85
    elif "hackerone" in origin.lower():
        sig.source_reliability = 0.7
    sig.relevance = 0.6 if any(x in low for x in ("bola", "idor", "ssrf", "xss", "auth")) else 0.4
    return sig


def accept_source(record: SourceRecord, *, reviewer: str) -> SourceRecord:
    if record.status == SourceStatus.REJECTED:
        return record
    record.status = SourceStatus.ACCEPTED
    record.validation_status = f"accepted_by:{reviewer}"
    return record


def reject_source(record: SourceRecord, *, reason: str) -> SourceRecord:
    record.status = SourceStatus.REJECTED
    record.validation_status = f"rejected:{reason}"
    return record
