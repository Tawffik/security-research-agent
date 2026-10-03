"""
Lightweight evidence graph relations (Gate 5.3 / 7 offline).

Not a graph database — explicit typed edges over evidence/claim IDs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class EvidenceRelationType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    VERIFIED_BY = "verified_by"
    REQUIRES = "requires"
    INVALIDATES = "invalidates"
    SUPERSEDES = "supersedes"


@dataclass
class EvidenceRelation:
    relation_id: str
    relation_type: str
    from_id: str  # evidence or claim id
    to_id: str
    episode_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceGraph:
    def __init__(self):
        self.relations: list[EvidenceRelation] = []

    def link(
        self,
        relation_type: EvidenceRelationType | str,
        from_id: str,
        to_id: str,
        *,
        episode_id: str = "",
        notes: str = "",
    ) -> EvidenceRelation:
        rt = relation_type.value if isinstance(relation_type, EvidenceRelationType) else str(relation_type)
        rel = EvidenceRelation(
            relation_id=f"rel-{uuid4().hex[:10]}",
            relation_type=rt,
            from_id=from_id,
            to_id=to_id,
            episode_id=episode_id,
            notes=notes,
        )
        self.relations.append(rel)
        return rel

    def supports_of(self, claim_id: str) -> list[EvidenceRelation]:
        return [r for r in self.relations if r.to_id == claim_id and r.relation_type == EvidenceRelationType.SUPPORTS.value]

    def contradicts_of(self, claim_id: str) -> list[EvidenceRelation]:
        return [
            r
            for r in self.relations
            if r.to_id == claim_id and r.relation_type == EvidenceRelationType.CONTRADICTS.value
        ]

    def has_contradiction(self, claim_id: str) -> bool:
        return bool(self.supports_of(claim_id) and self.contradicts_of(claim_id))
