"""
Gate 8 — Memory replay validation (offline).

Ensures trusted-memory lifecycle survives replay without:
- promoting untrusted items
- cross-target contamination
- applying superseded/revoked memory
- granting execution permission from memory presence
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent_core.memory.trusted import MemoryTrustState, TrustedMemoryStore


@dataclass
class MemoryReplayReport:
    ok: bool
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_memory_replay(store: TrustedMemoryStore, *, scope_context: str) -> MemoryReplayReport:
    """Run invariant checks against a store snapshot (as if resumed from checkpoint)."""
    report = MemoryReplayReport(ok=True)

    # 1) Untrusted never in trusted_refs
    for item in store.items.values():
        if item.source_trust == "untrusted" and item.trust_state in (
            MemoryTrustState.TRUSTED.value,
            MemoryTrustState.PROMOTED.value,
        ):
            # only allowed if validated then promoted with evidence
            if not item.validation_evidence_ids:
                report.failures.append(f"untrusted_promoted_without_validation:{item.memory_id}")
                report.ok = False
    report.checks.append("untrusted_promotion_gate")

    # 2) Revoked / superseded not applicable
    for item in store.items.values():
        if item.trust_state in (MemoryTrustState.REVOKED.value, MemoryTrustState.SUPERSEDED.value):
            if store.is_applicable(item.memory_id, scope_context=scope_context):
                report.failures.append(f"revoked_or_superseded_still_applicable:{item.memory_id}")
                report.ok = False
    report.checks.append("revoked_superseded_not_applicable")

    # 3) Cross-target isolation
    for item in store.items.values():
        if item.trust_state in (MemoryTrustState.TRUSTED.value, MemoryTrustState.PROMOTED.value):
            if item.scope_context and item.scope_context != scope_context:
                if store.is_applicable(item.memory_id, scope_context=scope_context):
                    report.failures.append(f"cross_target_leak:{item.memory_id}")
                    report.ok = False
    report.checks.append("cross_target_isolation")

    # 4) Memory presence never implies execution permission (structural check)
    for item in store.items.values():
        if "execution_permission" in (item.content_ref or "").lower():
            report.failures.append(f"memory_claims_execution:{item.memory_id}")
            report.ok = False
        if any("grant_execution" in n.lower() for n in item.notes):
            report.failures.append(f"memory_note_grants_execution:{item.memory_id}")
            report.ok = False
    report.checks.append("memory_neq_execution")

    # 5) Provenance present for promoted
    for item in store.items.values():
        if item.trust_state == MemoryTrustState.PROMOTED.value and not item.provenance and not item.promotion_evidence_ids:
            report.failures.append(f"promoted_without_provenance:{item.memory_id}")
            report.ok = False
    report.checks.append("promoted_has_provenance_or_evidence")

    return report


def simulate_checkpoint_resume(store: TrustedMemoryStore) -> TrustedMemoryStore:
    """Serialize/deserialize memory items to simulate process resume (no DB)."""
    snap = [i.to_dict() for i in store.items.values()]
    restored = TrustedMemoryStore()
    for d in snap:
        from agent_core.memory.trusted import MemoryItem

        item = MemoryItem(**{k: d[k] for k in MemoryItem.__dataclass_fields__ if k in d})
        restored.items[item.memory_id] = item
    restored.audit = list(store.audit)
    return restored
