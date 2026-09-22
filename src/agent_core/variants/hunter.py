"""
Variant Hunter (V2 §43).

After confirmed finding + root cause: search *structurally similar*
components on the Target Graph — not every URL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agent_core.schemas.target import Endpoint, TargetContext, TargetGraph
from agent_core.variants.root_cause import RootCause


@dataclass
class VariantCandidate:
    variant_id: str
    endpoint_id: str
    method: str
    path: str
    reason: str
    priority: str = "medium"
    related_root_cause_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "endpoint_id": self.endpoint_id,
            "method": self.method,
            "path": self.path,
            "reason": self.reason,
            "priority": self.priority,
            "related_root_cause_id": self.related_root_cause_id,
        }


class VariantHunter:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0

    def find_structural(
        self,
        *,
        ctx: TargetContext,
        graph: TargetGraph,
        root_cause: Optional[RootCause],
        seed_path_substr: str = "orders",
        limit: int = 5,
    ) -> list[VariantCandidate]:
        """
        Prefer endpoints with {id} (or id param) that are *not* the seed resource class.
        """
        out: list[VariantCandidate] = []
        for ep in ctx.endpoints:
            if "{id}" not in ep.path and "id" not in ep.parameters:
                continue
            path_l = ep.path.lower()
            if seed_path_substr and seed_path_substr in path_l:
                continue  # same family as original finding — skip duplicate surface
            if not ep.auth_required:
                continue
            self._counter += 1
            reason = "auth-required object identifier path; structurally similar to confirmed ownership issue"
            if root_cause and root_cause.signature != "unclassified":
                reason += f"; root_cause_signature={root_cause.signature}"
            out.append(
                VariantCandidate(
                    variant_id=f"VAR-{self._counter:03d}",
                    endpoint_id=ep.endpoint_id,
                    method=ep.method,
                    path=ep.path,
                    reason=reason,
                    priority="high" if root_cause else "medium",
                    related_root_cause_id=root_cause.root_cause_id if root_cause else None,
                )
            )
            if len(out) >= limit:
                break
        return out
