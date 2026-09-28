"""Domain-neutral knowledge query — built by domain adapters, not by the index."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KnowledgeQuery:
    domain: Optional[str] = None
    kinds: list[str] = field(default_factory=lambda: ["pattern", "procedure", "case", "strategy"])
    signals: list[str] = field(default_factory=list)
    tags_any: list[str] = field(default_factory=list)
    tags_prefer: list[str] = field(default_factory=list)
    security_properties: list[str] = field(default_factory=list)
    limit: int = 5
    require_domain_match: bool = False
    # Domain policy may attach extra competitors after retrieval (not used by ranker)
    extra_competing_explanations: list[str] = field(default_factory=list)
