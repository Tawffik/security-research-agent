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

    def supersede(self, memory_id: str, replacement_id: str, reason: str = "") -> MemoryItem | None:
        item = self.items.get(memory_id)
        if not item:
            return None
        item.trust_state = MemoryTrustState.SUPERSEDED.value
        item.notes.append(f"superseded_by:{replacement_id}:{reason}")
        item.updated_at = _ts()
        self.audit.append(
            {"action": "supersede", "memory_id": memory_id, "replacement": replacement_id, "reason": reason}
        )
        return item

    def trusted_refs(self, *, scope_context: str | None = None) -> list[str]:
        """Trusted refs optionally filtered by scope to prevent cross-target contamination."""
        out = []
        for i in self.items.values():
            if i.trust_state not in (MemoryTrustState.TRUSTED.value, MemoryTrustState.PROMOTED.value):
                continue
            if scope_context is not None and i.scope_context and i.scope_context != scope_context:
                continue
            out.append(i.content_ref)
        return out

    def is_applicable(self, memory_id: str, *, scope_context: str) -> bool:
        """Poisoning resistance: promoted memory must match target scope or be global (empty scope)."""
        item = self.items.get(memory_id)
        if not item:
            return False
        if item.trust_state not in (MemoryTrustState.TRUSTED.value, MemoryTrustState.PROMOTED.value):
            return False
        if not item.scope_context:
            return True  # global
        return item.scope_context == scope_context

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Flag multiple promoted items with same content_ref but different states/evidence."""
        by_ref: dict[str, list[MemoryItem]] = {}
        for i in self.items.values():
            if i.trust_state in (MemoryTrustState.PROMOTED.value, MemoryTrustState.TRUSTED.value):
                by_ref.setdefault(i.content_ref, []).append(i)
        conflicts = []
        for ref, items in by_ref.items():
            if len(items) > 1:
                scopes = {x.scope_context for x in items}
                if len(scopes) > 1 or len(items) > 1:
                    conflicts.append(
                        {
                            "content_ref": ref,
                            "memory_ids": [x.memory_id for x in items],
                            "scopes": list(scopes),
                            "kind": "duplicate_or_cross_scope",
                        }
                    )
        return conflicts


@dataclass
class ConditionalNegativeKnowledge:
    """
    Gate 8: negative knowledge is conditional — never "technique never works".

    Technique + Target/Context + Preconditions + Experiment + Observation + Limitation
    """

    technique: str
    target_context: str
    preconditions: list[str] = field(default_factory=list)
    experiment_id: str = ""
    observation_summary: str = ""
    limitation: str = ""
    provenance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def universal_claim_forbidden(self) -> bool:
        """True if this object must not be generalized into a universal ban."""
        return True
