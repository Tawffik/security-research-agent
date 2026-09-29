"""
Writeup / episode text → structured Case draft.

Unknown fields stay empty. Never fabricates evidence or root cause.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class StructuredCase:
    case_id: str
    source_id: str = ""
    title: str = ""
    target_context: str = ""
    technology: list[str] = field(default_factory=list)
    security_property: str = ""
    actor: str = ""
    action: str = ""
    resource: str = ""
    preconditions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    hypothesis: str = ""
    experiment: str = ""
    observation: str = ""
    evidence: list[str] = field(default_factory=list)
    root_cause: str = ""
    impact: str = ""
    alternative_explanations: list[str] = field(default_factory=list)
    confirmed_why: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    unknowns: list[str] = field(default_factory=list)
    false_positive_guidance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PROP_MAP = [
    (r"\b(bola|idor|object.?level|cross.?identit)\b", "authorization"),
    (r"\b(ssrf|server.?side request)\b", "ssrf"),
    (r"\b(xss|cross.?site scripting)\b", "xss"),
    (r"\b(sqli|sql injection|os command)\b", "injection"),
    (r"\b(session fixation|authn|authentication|login)\b", "authentication"),
    (r"\b(business logic|workflow|race)\b", "business_logic"),
]


def _detect_property(text: str) -> str:
    low = text.lower()
    for pat, prop in _PROP_MAP:
        if re.search(pat, low, re.I):
            return prop
    return ""


def _section_after(text: str, *headers: str) -> str:
    low_lines = text.splitlines()
    for i, line in enumerate(low_lines):
        l = line.lower().strip("# ").strip()
        if any(h in l for h in headers):
            buf = []
            for j in range(i + 1, len(low_lines)):
                if low_lines[j].startswith("#"):
                    break
                buf.append(low_lines[j])
            return "\n".join(buf).strip()
    return ""


def extract_case_from_text(
    text: str,
    *,
    case_id: str,
    source_id: str = "",
    title: str = "",
) -> StructuredCase:
    """Best-effort extraction; blanks mean unknown — never invent."""
    case = StructuredCase(
        case_id=case_id,
        source_id=source_id,
        title=title or (text.splitlines()[0][:120] if text else ""),
        security_property=_detect_property(text),
        provenance={"extractor": "case_extract_v1", "source_id": source_id},
    )
    case.hypothesis = _section_after(text, "hypothesis") or ""
    case.observation = _section_after(text, "observation") or ""
    case.root_cause = _section_after(text, "root cause") or ""
    case.impact = _section_after(text, "impact") or ""
    case.experiment = _section_after(text, "experiment", "minimum experiment") or ""
    fp = _section_after(text, "false positive", "not the same as", "not same as")
    if fp:
        case.false_positive_guidance = [
            p.strip("- *") for p in fp.splitlines() if p.strip()
        ]
    pre = _section_after(text, "precondition")
    if pre:
        case.preconditions = [p.strip("- *") for p in pre.splitlines() if p.strip()]
    # technology hints
    low = text.lower()
    for tech in ("graphql", "rest", "jwt", "oauth", "websocket"):
        if tech in low:
            case.technology.append(tech)
    # track unknowns
    for field_name in (
        "hypothesis",
        "observation",
        "root_cause",
        "impact",
        "experiment",
        "security_property",
    ):
        if not getattr(case, field_name):
            case.unknowns.append(field_name)
    return case


def extract_case_from_episode(closed: Any, *, case_id: str) -> StructuredCase:
    """Research episode → Case candidate (not trusted knowledge)."""
    align = getattr(closed, "experiment_alignment", None) or {}
    episode = getattr(closed, "episode", None)
    host = ""
    plan = getattr(closed, "plan", None)
    if plan is not None and getattr(plan, "target_context", None):
        host = getattr(plan.target_context, "primary_host", "") or ""
    prop = "authorization"
    outcome = getattr(closed, "final_status", "") or ""
    case = StructuredCase(
        case_id=case_id,
        source_id=f"episode:{getattr(episode, 'episode_id', '')}",
        title=f"Episode case {case_id}",
        target_context=host,
        security_property=prop,
        experiment=str(align.get("experiment_id") or getattr(closed, "selected_experiment_id", "")),
        observation=f"n_obs={len(getattr(closed, 'observations', None) or [])}",
        evidence=list(getattr(closed, "evidence_ids", None) or []),
        confirmed_why=outcome,
        provenance={
            "extractor": "episode_to_case_v1",
            "episode_id": getattr(episode, "episode_id", ""),
            "engagement_id": getattr(closed, "engagement_id", "")
            if hasattr(closed, "engagement_id")
            else "",
            "not_trusted": True,
        },
        unknowns=[],
    )
    if not case.evidence:
        case.unknowns.append("evidence")
    return case
