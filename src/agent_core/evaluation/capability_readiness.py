"""
Capability readiness inventory — machine-readable map from methodology domain
to knowledge, labs, skills, and measured readiness.

Does not invent readiness: statuses are derived from repository artifacts and
optional offline benchmark rows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


# Canonical methodology domains (aligned with knowledge/*.md Domain frontmatter)
METHODOLOGY_DOMAINS = [
    "authorization",
    "authentication",
    "business_logic",
    "ssrf",
    "injection",
    "xss",
    "csrf",
    "jwt",
    "path_traversal",
    "traversal",
    "oauth",
    "graphql",
    "cors",
    "cache",
    "deserialization",
    "upload",
    "xxe",
    "ssti",
    "websocket",
    "http_desync",
    "redirect",
    "session",
]


@dataclass
class DomainReadiness:
    domain: str
    knowledge_cases: int = 0
    knowledge_patterns: int = 0
    knowledge_procedures: int = 0
    knowledge_negatives: int = 0
    lab_scenarios: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    benchmark_scenarios: list[str] = field(default_factory=list)
    readiness: str = "NOT_INVENTORIED"
    evidence_notes: list[str] = field(default_factory=list)
    next_dependency: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _domain_of_record(rec: Any) -> str:
    d = (getattr(rec, "domain", None) or "unknown").lower().strip()
    if d in ("", "unknown"):
        tags = [str(t).lower() for t in (getattr(rec, "tags", None) or [])]
        for candidate in METHODOLOGY_DOMAINS:
            if candidate in tags or candidate.replace("_", "-") in tags:
                return candidate
        if "sql" in tags or "sqli" in tags:
            return "injection"
        if "idor" in tags or "bola" in tags:
            return "authorization"
    # normalize aliases
    aliases = {
        "authz": "authorization",
        "idor": "authorization",
        "bola": "authorization",
        "sqli": "injection",
        "sql": "injection",
        "server-side-request-forgery": "ssrf",
        "business-logic": "business_logic",
        "path_traversal": "traversal",
        "path-traversal": "traversal",
        "file-upload": "upload",
        "insecure-deserialization": "deserialization",
    }
    return aliases.get(d, d)


# Lab factories registered in closed_loop (name → methodology)
LAB_REGISTRY: dict[str, str] = {
    "default_idor_lab_scenario": "authorization",
    "secure_lab_scenario": "authorization",
    "public_resource_lab_scenario": "authorization",
    "shared_object_lab_scenario": "authorization",
    "hard_authz_lab_scenario": "authorization",
    "action_level_bola_lab_scenario": "authorization",
    "vertical_object_lab_scenario": "authorization",
    "graphql_global_id_lab_scenario": "authorization",
    "ambiguous_incomplete_lab_scenario": "authorization",
    "role_authorized_lab_scenario": "authorization",
    "cache_artifact_lab_scenario": "authorization",
    "business_logic_coupon_lab_scenario": "business_logic",
    "hard_ssrf_lab_scenario": "ssrf",
    "hard_sqli_lab_scenario": "injection",
    "secure_sqli_lab_scenario": "injection",
    "hard_xss_lab_scenario": "xss",
    "secure_xss_lab_scenario": "xss",
    "hard_jwt_lab_scenario": "authentication",
    "secure_jwt_lab_scenario": "authentication",
    "hard_csrf_lab_scenario": "authentication",
    "secure_csrf_lab_scenario": "authentication",
    "hard_path_traversal_lab_scenario": "traversal",
    "secure_path_traversal_lab_scenario": "traversal",
    "hard_upload_lab_scenario": "upload",
    "secure_upload_lab_scenario": "upload",
    "hard_deserialization_lab_scenario": "deserialization",
    "secure_deserialization_lab_scenario": "deserialization",
    "heldout_sqli_lab_scenario": "injection",
    "heldout_xss_lab_scenario": "xss",
    "heldout_secure_xss_lab_scenario": "xss",
}


BENCHMARK_REGISTRY: dict[str, str] = {
    "pos_authz": "authorization",
    "secure_authz": "authorization",
    "public_res": "authorization",
    "shared_res": "authorization",
    "hard_authz": "authorization",
    "action_level_bola": "authorization",
    "vertical_object": "authorization",
    "graphql_global_id": "authorization",
    "business_logic": "business_logic",
    "hard_ssrf": "ssrf",
    "hard_sqli": "injection",
    "hard_xss": "xss",
    "hard_jwt": "authentication",
    "hard_csrf": "authentication",
    "hard_path_traversal": "traversal",
    "hard_upload": "upload",
    "hard_deserialization": "deserialization",
    "heldout_sqli": "injection",
    "heldout_xss": "xss",
}



def build_readiness_matrix(
    knowledge_root: Path,
    skills_root: Optional[Path] = None,
) -> dict[str, DomainReadiness]:
    from agent_core.knowledge.index import KnowledgeIndex

    idx = KnowledgeIndex(knowledge_root).load()
    matrix: dict[str, DomainReadiness] = {
        d: DomainReadiness(domain=d) for d in METHODOLOGY_DOMAINS
    }
    matrix["other"] = DomainReadiness(domain="other")

    for rec in idx.records:
        d = _domain_of_record(rec)
        slot = matrix.get(d) or matrix["other"]
        kind = (getattr(rec, "kind", "") or "").lower()
        if kind == "case":
            slot.knowledge_cases += 1
        elif kind == "pattern":
            slot.knowledge_patterns += 1
        elif kind == "procedure":
            slot.knowledge_procedures += 1
        elif kind == "negative":
            slot.knowledge_negatives += 1

    for lab, meth in LAB_REGISTRY.items():
        if meth in matrix:
            matrix[meth].lab_scenarios.append(lab)

    for sid, meth in BENCHMARK_REGISTRY.items():
        if meth in matrix:
            matrix[meth].benchmark_scenarios.append(sid)

    if skills_root and skills_root.is_dir():
        for p in skills_root.iterdir():
            if not p.is_dir():
                continue
            skill_md = p / "SKILL.md"
            if not skill_md.is_file():
                continue
            text = skill_md.read_text(encoding="utf-8", errors="replace").lower()
            assigned = False
            for d in METHODOLOGY_DOMAINS:
                if d.replace("_", " ") in text or d in text:
                    matrix[d].skills.append(p.name)
                    assigned = True
            if not assigned and "authz" in text or "idor" in text:
                matrix["authorization"].skills.append(p.name)

    for d, slot in matrix.items():
        has_k = (
            slot.knowledge_cases
            + slot.knowledge_patterns
            + slot.knowledge_procedures
        ) > 0
        has_lab = bool(slot.lab_scenarios)
        has_bench = bool(slot.benchmark_scenarios)
        if not has_k and not has_lab:
            slot.readiness = "NOT_IMPLEMENTED"
            slot.next_dependency = "knowledge_or_lab_slice"
        elif has_k and not has_lab:
            slot.readiness = "KNOWLEDGE_ONLY"
            slot.next_dependency = "offline_lab_scenario"
            slot.evidence_notes.append("curated knowledge present; no lab factory")
        elif has_lab and not has_bench:
            slot.readiness = "LAB_TESTED"
            slot.next_dependency = "utility_benchmark_row"
        elif has_lab and has_bench:
            # LAB + benchmark harness wired; not automatically HELD_OUT_VALIDATED
            slot.readiness = "BENCHMARKED"
            slot.next_dependency = "held_out_or_authorized_e2e"
            slot.evidence_notes.append(
                "offline labs + HARD_SCENARIOS/DEFAULT wiring; measure before promoting"
            )
        else:
            slot.readiness = "PARTIAL_IMPLEMENTATION"
            slot.next_dependency = "close_knowledge_lab_gap"

    return matrix


def readiness_to_json(matrix: dict[str, DomainReadiness]) -> str:
    payload = {k: v.to_dict() for k, v in sorted(matrix.items())}
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_readiness_artifact(
    knowledge_root: Path,
    out_path: Path,
    skills_root: Optional[Path] = None,
) -> Path:
    matrix = build_readiness_matrix(knowledge_root, skills_root=skills_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(readiness_to_json(matrix), encoding="utf-8")
    return out_path
