"""
Origin-bound memory authority.

Untrusted source → summary/tool echo → memory must NOT become trusted original.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class SourceTrustClass(str):
    UNTRUSTED = "untrusted"
    TARGET_ORIGIN = "target_origin"
    TOOL_ECHO = "tool_echo"
    SUMMARY = "summary"
    CURATED = "curated"
    EPISODE = "episode"
    EXTERNAL = "external"


@dataclass
class MemoryOriginChain:
    source_identity: str
    source_trust_class: str
    artifact_identity: str = ""
    content_hash: str = ""
    derivation_channel: str = ""  # direct | summary | tool_echo | transform
    parent_evidence_refs: list[str] = field(default_factory=list)
    parent_event_refs: list[str] = field(default_factory=list)
    target_scope: str = ""
    writer_actor: str = ""
    authorization_context: str = ""
    validation_evidence_ids: list[str] = field(default_factory=list)
    promotion_evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_laundering_risk(self) -> bool:
        """True if derivation could hide untrusted origin."""
        if self.source_trust_class in (
            SourceTrustClass.UNTRUSTED,
            SourceTrustClass.TARGET_ORIGIN,
            SourceTrustClass.TOOL_ECHO,
            SourceTrustClass.SUMMARY,
        ):
            if self.derivation_channel in ("summary", "tool_echo", "transform"):
                return True
        return False

    def may_auto_promote(self) -> bool:
        """Untrusted / laundered origins never auto-promote."""
        if self.is_laundering_risk():
            return False
        if self.source_trust_class in (
            SourceTrustClass.UNTRUSTED,
            SourceTrustClass.TARGET_ORIGIN,
            SourceTrustClass.TOOL_ECHO,
            SourceTrustClass.SUMMARY,
        ):
            return False
        return self.source_trust_class in (SourceTrustClass.CURATED, SourceTrustClass.EPISODE)


def detect_laundering(
    origin: MemoryOriginChain,
    *,
    claimed_trust: str,
) -> list[str]:
    """Return violation codes if untrusted origin is claimed as trusted."""
    violations: list[str] = []
    if origin.is_laundering_risk() and claimed_trust in ("trusted", "promoted", "curated"):
        violations.append("summary_or_echo_laundering")
    if origin.source_trust_class == SourceTrustClass.TARGET_ORIGIN and claimed_trust in (
        "trusted",
        "promoted",
    ):
        violations.append("target_origin_claimed_trusted")
    if origin.derivation_channel == "tool_echo" and claimed_trust in ("trusted", "promoted"):
        violations.append("trusted_tool_echo_laundering")
    if not origin.parent_evidence_refs and claimed_trust in ("trusted", "promoted"):
        if origin.source_trust_class != SourceTrustClass.CURATED:
            violations.append("manufactured_corroboration_risk")
    return violations
