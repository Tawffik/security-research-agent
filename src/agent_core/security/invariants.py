"""
Security invariants (§44) — first-class properties to test, not skill names.

Example: user accesses only owned objects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Invariant:
    invariant_id: str
    statement: str
    domain: str  # authorization | authentication | workflow | session
    severity_if_violated: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InvariantCheck:
    invariant_id: str
    holds: Optional[bool]  # None = untested
    evidence_ids: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InvariantRegistry:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._items: dict[str, Invariant] = {}
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        defaults = [
            ("I-001", "User can only access owned objects", "authorization", "high"),
            ("I-002", "Client-side role does not determine server authorization", "authorization", "high"),
            ("I-003", "Refund cannot exceed paid amount", "workflow", "high"),
            ("I-004", "Reset token is single-use and identity-bound", "authentication", "high"),
        ]
        for iid, stmt, domain, sev in defaults:
            self._items[iid] = Invariant(iid, stmt, domain, sev)

    def list_all(self) -> list[Invariant]:
        return list(self._items.values())

    def check_ownership_from_lab(
        self,
        *,
        non_owner_status: int,
        evidence_ids: list[str],
    ) -> InvariantCheck:
        """I-001: non-owner 200 → violated; 403/404 → holds."""
        if non_owner_status < 400:
            return InvariantCheck("I-001", False, list(evidence_ids), "non-owner obtained object")
        if non_owner_status in (401, 403, 404):
            return InvariantCheck("I-001", True, list(evidence_ids), "non-owner denied")
        return InvariantCheck("I-001", None, list(evidence_ids), f"inconclusive status {non_owner_status}")
