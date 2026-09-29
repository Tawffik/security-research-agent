"""
Gap-driven external knowledge expansion planner (offline).

[NOTION REQUIREMENT] External expansion is continuous and gap-driven.
Does NOT scrape the web. Produces a prioritized gap list for human/source selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent_core.knowledge.index import KnowledgeIndex


KNOWN_PROPERTIES = [
    "authorization",
    "authentication",
    "business_logic",
    "ssrf",
    "xss",
    "injection",
    "information_disclosure",
]


@dataclass
class PropertyGap:
    security_property: str
    n_cases: int = 0
    n_patterns: int = 0
    n_procedures: int = 0
    n_strategies: int = 0
    n_tips: int = 0
    n_negatives: int = 0
    priority: float = 0.0
    recommended_source_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_knowledge_gaps(knowledge_root: Path) -> list[PropertyGap]:
    idx = KnowledgeIndex(knowledge_root).load()
    by_prop: dict[str, PropertyGap] = {
        p: PropertyGap(security_property=p) for p in KNOWN_PROPERTIES
    }
    for r in idx.records:
        prop = (r.domain or "").lower().replace("-", "_")
        if not prop or prop == "unknown":
            sp = (r.security_property or "").lower()
            if "auth" in sp or "bola" in sp or "idor" in sp or "owner" in sp:
                prop = "authorization"
            elif "ssrf" in sp:
                prop = "ssrf"
            elif "xss" in sp:
                prop = "xss"
            elif "business" in sp:
                prop = "business_logic"
            else:
                prop = "unknown"
        if prop in ("authz", "bola", "idor"):
            prop = "authorization"
        elif prop in ("authn",):
            prop = "authentication"
        if prop not in by_prop:
            by_prop.setdefault(prop, PropertyGap(security_property=prop))
        g = by_prop[prop]
        if r.kind == "case":
            g.n_cases += 1
        elif r.kind == "pattern":
            g.n_patterns += 1
        elif r.kind == "procedure":
            g.n_procedures += 1
        elif r.kind == "strategy":
            g.n_strategies += 1
        elif r.kind == "tip":
            g.n_tips += 1
        elif r.kind == "negative":
            g.n_negatives += 1

    for g in by_prop.values():
        # Higher priority when missing procedures or patterns
        missing = 0
        if g.n_procedures == 0:
            missing += 3
        if g.n_patterns == 0:
            missing += 2
        if g.n_cases == 0:
            missing += 1
        if g.n_negatives == 0:
            missing += 0.5
        g.priority = float(missing)
        g.recommended_source_types = []
        if g.n_cases == 0:
            g.recommended_source_types.append("writeup")
        if g.n_patterns == 0:
            g.recommended_source_types.append("methodology")
        if g.n_procedures == 0:
            g.recommended_source_types.append("procedure_research")
        if g.n_negatives == 0:
            g.recommended_source_types.append("false_positive_guidance")
    return sorted(by_prop.values(), key=lambda x: -x.priority)
