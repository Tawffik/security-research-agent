"""
Deduplication: Cases stay distinct; Patterns may share fingerprints.

Does not destroy independent Cases when they map to the same Pattern.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent_core.knowledge.case_extract import StructuredCase
from agent_core.knowledge.index import KnowledgeRecord


@dataclass
class PatternFingerprint:
    security_property: str
    fingerprint: str
    preconditions_key: str
    member_case_ids: list[str] = field(default_factory=list)
    member_pattern_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def fingerprint_pattern(
    *,
    security_property: str,
    abstraction: str = "",
    preconditions: Optional[list[str]] = None,
) -> str:
    """Stable fingerprint from property + normalized abstraction tokens."""
    pre = "|".join(sorted(_norm(p) for p in (preconditions or []) if p))
    abs_n = _norm(abstraction)
    # Keep boundary words that prevent over-generalization
    tokens = [
        t
        for t in re.findall(r"[a-z0-9_-]{3,}", abs_n)
        if t
        not in {
            "the",
            "and",
            "with",
            "from",
            "that",
            "this",
            "when",
            "using",
        }
    ][:24]
    raw = f"{_norm(security_property)}::{pre}::{' '.join(tokens)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cluster_cases_to_patterns(cases: list[StructuredCase]) -> list[PatternFingerprint]:
    """Multiple cases may share one fingerprint without merging case records."""
    buckets: dict[str, PatternFingerprint] = {}
    for c in cases:
        abs_parts = " ".join(
            filter(
                None,
                [c.hypothesis, c.root_cause, c.observation, c.confirmed_why],
            )
        )
        fp = fingerprint_pattern(
            security_property=c.security_property or "unknown",
            abstraction=abs_parts,
            preconditions=c.preconditions,
        )
        if fp not in buckets:
            buckets[fp] = PatternFingerprint(
                security_property=c.security_property or "unknown",
                fingerprint=fp,
                preconditions_key="|".join(sorted(c.preconditions)),
            )
        buckets[fp].member_case_ids.append(c.case_id)
    return list(buckets.values())


def find_duplicate_patterns(
    records: list[KnowledgeRecord],
) -> list[tuple[str, str, str]]:
    """Return pairs (id_a, id_b, fingerprint) for same-property near-duplicates."""
    by_fp: dict[str, list[str]] = {}
    for r in records:
        if r.kind != "pattern":
            continue
        fp = fingerprint_pattern(
            security_property=r.security_property or r.domain,
            abstraction=r.abstraction or r.title,
        )
        by_fp.setdefault(fp, []).append(r.record_id)
    pairs: list[tuple[str, str, str]] = []
    for fp, ids in by_fp.items():
        if len(ids) < 2:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pairs.append((ids[i], ids[j], fp))
    return pairs


def novelty_vs_existing(
    case: StructuredCase, existing_patterns: list[KnowledgeRecord]
) -> str:
    """
    new_case | strengthens_pattern | duplicate_information | contradiction_unknown
    """
    if not case.security_property:
        return "new_case"
    fp = fingerprint_pattern(
        security_property=case.security_property,
        abstraction=" ".join([case.hypothesis, case.root_cause, case.observation]),
        preconditions=case.preconditions,
    )
    for p in existing_patterns:
        if p.kind != "pattern":
            continue
        pfp = fingerprint_pattern(
            security_property=p.security_property or p.domain,
            abstraction=p.abstraction or p.title,
        )
        if pfp == fp:
            return "strengthens_pattern"
        # same property different fp → new evidence under property
        if (p.security_property or p.domain) == case.security_property:
            return "new_case"
    return "new_case"
