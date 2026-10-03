"""
Skill Assurance record — trust_score ≠ security boundary.

Lifecycle: DRAFT → CANDIDATE → BENCHMARKED → SECURITY_EVALUATED → REVIEW → APPROVED
Material updates require revalidation. Execution still via Tool Contract + ScopeGuard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class SkillAssuranceState(str, Enum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    BENCHMARKED = "benchmarked"
    SECURITY_EVALUATED = "security_evaluated"
    REVIEW = "review"
    APPROVED = "approved"
    REVALIDATION = "revalidation"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


@dataclass
class SkillAssuranceRecord:
    skill_id: str
    version: str
    artifact_hash: str = ""
    provenance: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    declared_capabilities: list[str] = field(default_factory=list)
    benchmark_evidence_ids: list[str] = field(default_factory=list)
    security_evidence_ids: list[str] = field(default_factory=list)
    assurance_state: str = SkillAssuranceState.DRAFT.value
    supersedes: str = ""
    revoked_reason: str = ""
    material_change: bool = False
    trust_score: float = 0.0  # informational only — never authorization
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillAssuranceRegistry:
    def __init__(self):
        self.records: dict[str, SkillAssuranceRecord] = {}
        self.audit: list[dict[str, Any]] = []

    def _key(self, skill_id: str, version: str) -> str:
        return f"{skill_id}@{version}"

    def register_draft(self, skill_id: str, version: str, **kwargs) -> SkillAssuranceRecord:
        rec = SkillAssuranceRecord(
            skill_id=skill_id,
            version=version,
            assurance_state=SkillAssuranceState.DRAFT.value,
            updated_at=datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in kwargs.items() if k in SkillAssuranceRecord.__dataclass_fields__},
        )
        self.records[self._key(skill_id, version)] = rec
        self.audit.append({"action": "register_draft", "key": self._key(skill_id, version)})
        return rec

    def advance(self, skill_id: str, version: str, new_state: SkillAssuranceState, evidence_ids: list[str] | None = None) -> SkillAssuranceRecord | None:
        rec = self.records.get(self._key(skill_id, version))
        if not rec:
            return None
        # Cannot approve without benchmark + security evaluation path
        if new_state == SkillAssuranceState.APPROVED:
            if rec.assurance_state not in (
                SkillAssuranceState.REVIEW.value,
                SkillAssuranceState.SECURITY_EVALUATED.value,
            ):
                self.audit.append({"action": "approve_denied", "reason": "not_ready", "key": self._key(skill_id, version)})
                return rec
            if not rec.benchmark_evidence_ids and not (evidence_ids):
                self.audit.append({"action": "approve_denied", "reason": "no_benchmark", "key": self._key(skill_id, version)})
                return rec
        if new_state == SkillAssuranceState.BENCHMARKED and evidence_ids:
            rec.benchmark_evidence_ids = list(evidence_ids)
        if new_state == SkillAssuranceState.SECURITY_EVALUATED and evidence_ids:
            rec.security_evidence_ids = list(evidence_ids)
        rec.assurance_state = new_state.value
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        self.audit.append({"action": "advance", "state": new_state.value, "key": self._key(skill_id, version)})
        return rec

    def material_update(self, skill_id: str, old_version: str, new_version: str, capability_diff: list[str]) -> SkillAssuranceRecord:
        """Material change forces revalidation — does not inherit approval."""
        old = self.records.get(self._key(skill_id, old_version))
        rec = SkillAssuranceRecord(
            skill_id=skill_id,
            version=new_version,
            assurance_state=SkillAssuranceState.REVALIDATION.value,
            material_change=True,
            supersedes=old_version,
            declared_capabilities=list(capability_diff),
            provenance=list(old.provenance) if old else [],
            trust_score=0.0,  # reset — trust_score ≠ boundary
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.records[self._key(skill_id, new_version)] = rec
        self.audit.append({"action": "material_update_revalidation", "key": self._key(skill_id, new_version)})
        return rec

    def is_execution_eligible(self, skill_id: str, version: str) -> bool:
        """Assurance APPROVED is necessary but not sufficient for execution."""
        rec = self.records.get(self._key(skill_id, version))
        if not rec:
            return False
        return rec.assurance_state == SkillAssuranceState.APPROVED.value

    def trust_score_grants_execution(self, skill_id: str, version: str) -> bool:
        """Always False — trust_score is never an authorization mechanism."""
        return False
