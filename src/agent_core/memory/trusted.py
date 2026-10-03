"""
Gate 8 foundation — trusted memory lifecycle (offline).

candidate → validated → trusted/promoted → superseded/revoked

Poisoning resistance: untrusted sources cannot auto-promote.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class MemoryTrustState(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    TRUSTED = "trusted"
    PROMOTED = "promoted"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


@dataclass
class MemoryItem:
    memory_id: str
    content_ref: str  # knowledge id / case id / lesson id
    trust_state: str
    provenance: list[str] = field(default_factory=list)
    version: int = 1
    validation_evidence_ids: list[str] = field(default_factory=list)
    promotion_evidence_ids: list[str] = field(default_factory=list)
    scope_context: str = ""
    source_trust: str = "untrusted"  # untrusted | curated | episode | external
    created_at: str = ""
    updated_at: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrustedMemoryStore:
    def __init__(self):
        self.items: dict[str, MemoryItem] = {}
        self.audit: list[dict[str, Any]] = []

    def add_candidate(
        self,
        content_ref: str,
        *,
        provenance: list[str] | None = None,
        source_trust: str = "untrusted",
        scope_context: str = "",
    ) -> MemoryItem:
        mid = f"mem-{uuid4().hex[:10]}"
        item = MemoryItem(
            memory_id=mid,
            content_ref=content_ref,
            trust_state=MemoryTrustState.CANDIDATE.value,
            provenance=list(provenance or []),
            source_trust=source_trust,
            scope_context=scope_context,
            created_at=_ts(),
            updated_at=_ts(),
        )
        self.items[mid] = item
        self.audit.append({"action": "add_candidate", "memory_id": mid})
        return item

    def validate(self, memory_id: str, evidence_ids: list[str]) -> MemoryItem | None:
        item = self.items.get(memory_id)
        if not item:
            return None
        if not evidence_ids:
            self.audit.append({"action": "validate_denied", "reason": "no_evidence", "memory_id": memory_id})
            return item
        item.trust_state = MemoryTrustState.VALIDATED.value
        item.validation_evidence_ids = list(evidence_ids)
        item.updated_at = _ts()
        self.audit.append({"action": "validate", "memory_id": memory_id})
        return item

    def promote(self, memory_id: str, evidence_ids: list[str]) -> MemoryItem | None:
        item = self.items.get(memory_id)
        if not item:
            return None
        # Poisoning resistance: untrusted source cannot promote without validation
        if item.trust_state == MemoryTrustState.CANDIDATE.value:
            self.audit.append({"action": "promote_denied", "reason": "not_validated", "memory_id": memory_id})
            return item
        if item.source_trust == "untrusted" and item.trust_state != MemoryTrustState.VALIDATED.value:
            self.audit.append({"action": "promote_denied", "reason": "untrusted_source", "memory_id": memory_id})
            return item
        if not evidence_ids and not item.validation_evidence_ids:
            self.audit.append({"action": "promote_denied", "reason": "no_promotion_evidence", "memory_id": memory_id})
            return item
        item.trust_state = MemoryTrustState.PROMOTED.value
        item.promotion_evidence_ids = list(evidence_ids or item.validation_evidence_ids)
        item.updated_at = _ts()
        self.audit.append({"action": "promote", "memory_id": memory_id})
        return item

    def revoke(self, memory_id: str, reason: str = "") -> MemoryItem | None:
        item = self.items.get(memory_id)
        if not item:
            return None
        item.trust_state = MemoryTrustState.REVOKED.value
        item.notes.append(reason or "revoked")
        item.updated_at = _ts()
        self.audit.append({"action": "revoke", "memory_id": memory_id, "reason": reason})
        return item

    def trusted_refs(self) -> list[str]:
        return [
            i.content_ref
            for i in self.items.values()
            if i.trust_state in (MemoryTrustState.TRUSTED.value, MemoryTrustState.PROMOTED.value)
        ]
