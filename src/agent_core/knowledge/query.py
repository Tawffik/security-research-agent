"""Domain-neutral knowledge query — built by domain adapters, not by the index."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KnowledgeQuery:
    domain: Optional[str] = None
    methodologies: list[str] = field(default_factory=list)
    kinds: list[str] = field(
        default_factory=lambda: [
            "pattern",
            "procedure",
            "case",
            "strategy",
            "tip",
            "negative",
        ]
    )
    signals: list[str] = field(default_factory=list)
    tags_any: list[str] = field(default_factory=list)
    tags_prefer: list[str] = field(default_factory=list)
    security_properties: list[str] = field(default_factory=list)
    limit: int = 5
    require_domain_match: bool = False
    require_methodology_match: bool = False
    extra_competing_explanations: list[str] = field(default_factory=list)

    # Gate 2 research state (affect ranking; never grant execution)
    hypothesis_tokens: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    prior_experiment_ids: list[str] = field(default_factory=list)
    negative_evidence_ids: list[str] = field(default_factory=list)
    precondition_hints: list[str] = field(default_factory=list)
    # Target context hints already partly in signals; keep explicit
    actor_count: int = 0
    has_object_id_param: bool = False
