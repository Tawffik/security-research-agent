"""Load curated knowledge/*.md into structured records with provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _default_knowledge_root() -> Path:
    # repo_root/knowledge — package is src/agent_core/knowledge
    return Path(__file__).resolve().parents[3] / "knowledge"


@dataclass
class KnowledgeRecord:
    record_id: str
    kind: str  # case | pattern | procedure | strategy
    title: str
    domain: str
    path: str
    security_property: str = ""
    abstraction: str = ""
    not_same_as: list[str] = field(default_factory=list)
    experiment_steps: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_excerpt: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "title": self.title,
            "domain": self.domain,
            "path": self.path,
            "security_property": self.security_property,
            "abstraction": self.abstraction[:500],
            "not_same_as": self.not_same_as,
            "experiment_steps": self.experiment_steps,
            "evidence_required": self.evidence_required,
            "stop_conditions": self.stop_conditions,
            "related_ids": self.related_ids,
            "tags": self.tags,
            "provenance": self.provenance,
        }


_ID_RE = re.compile(r"\b((?:CASE|PAT|PROC|STRAT|NEG|TIP)-\d{4}[A-Za-z0-9-]*)\b", re.I)
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.M)


def _section(text: str, *names: str) -> str:
    """Extract markdown section body under a heading containing any of names."""
    lines = text.splitlines()
    capture = False
    buf: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if capture:
                break
            low = line.lower()
            if any(n.lower() in low for n in names):
                capture = True
                continue
        elif capture:
            buf.append(line)
    return "\n".join(buf).strip()


def _bullets(block: str) -> list[str]:
    out: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith(("-", "*", "•")):
            out.append(re.sub(r"^[-*•]\s*", "", s).strip())
        elif re.match(r"^\d+\.", s):
            out.append(re.sub(r"^\d+\.\s*", "", s).strip())
    return [x for x in out if x]


def parse_knowledge_markdown(path: Path, kind: str) -> Optional[KnowledgeRecord]:
    if not path.is_file() or path.suffix.lower() != ".md":
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return None

    title_m = _HEADING_RE.search(text)
    title = title_m.group(1).strip() if title_m else path.stem

    ids = _ID_RE.findall(text)
    record_id = ids[0] if ids else path.stem.upper()
    # Prefer kind-matching id
    for i in ids:
        if kind == "case" and i.upper().startswith("CASE"):
            record_id = i
            break
        if kind == "pattern" and i.upper().startswith("PAT"):
            record_id = i
            break
        if kind == "procedure" and i.upper().startswith("PROC"):
            record_id = i
            break
        if kind == "strategy" and i.upper().startswith("STRAT"):
            record_id = i
            break
        if kind == "tip" and i.upper().startswith("TIP"):
            record_id = i
            break
        if kind == "negative" and i.upper().startswith("NEG"):
            record_id = i
            break

    domain = "unknown"
    dm = re.search(r"\*\*Domain:\*\*\s*(\S+)", text, re.I)
    if dm:
        domain = dm.group(1).strip().lower()
    elif "authorization" in text.lower() or "bola" in text.lower() or "idor" in text.lower():
        domain = "authorization"
    elif "graphql" in text.lower() and "introspect" not in text.lower():
        domain = "authorization"  # GraphQL authz cases remain authorization family
    elif "ssrf" in text.lower() or "metadata" in text.lower() and "server-side" in text.lower():
        domain = "ssrf"
    elif "xss" in text.lower() or "cross-site scripting" in text.lower():
        domain = "xss"
    elif "sql injection" in text.lower() or ( "sql" in text.lower() and "inject" in text.lower()):
        domain = "injection"
    elif "traversal" in text.lower() or "path join" in text.lower():
        domain = "traversal"
    elif "csrf" in text.lower() or "jwt" in text.lower() or "session fixation" in text.lower():
        domain = "authentication"
    elif "business" in text.lower() or "coupon" in text.lower() or "race" in text.lower():
        domain = "business_logic"
    elif "cache" in text.lower() and ("deception" in text.lower() or "cdn" in text.lower() or "cache-control" in text.lower()):
        domain = "cache"
    elif "deserial" in text.lower() or "pickle" in text.lower() or "objectinputstream" in text.lower():
        domain = "deserialization"
    elif "upload" in text.lower() and ("file" in text.lower() or "content-type" in text.lower()):
        domain = "upload"
    elif "xxe" in text.lower() or "external entity" in text.lower():
        domain = "injection"
    elif "ssti" in text.lower() or "template injection" in text.lower():
        domain = "injection"

    sec = _section(text, "Security property", "security property")
    if not sec:
        sm = re.search(r"\*\*Security property\*\*[^\n]*\n([^\n#]+)", text, re.I)
        sec = (sm.group(1).strip() if sm else "") or ""
    if not sec and "object" in text.lower():
        sec = "object-level authorization / ownership binding"

    abstraction = _section(text, "Abstraction", "How It Works", "Description")
    if not abstraction:
        # first non-heading paragraph
        for para in re.split(r"\n\n+", text):
            p = para.strip()
            if p and not p.startswith("#") and not p.startswith("**Type"):
                abstraction = p[:800]
                break

    not_same = _bullets(_section(text, "Not the same as", "False positive", "known false"))
    steps = _bullets(
        _section(
            text,
            "Minimum experiment",
            "Discriminating experiment",
            "Experiment",
            "Procedure",
        )
    )
    evidence = _bullets(_section(text, "Evidence required", "Evidence requirements", "Evidence"))
    stops = _bullets(_section(text, "Stop when", "Stop condition", "Stop conditions"))

    related = list(dict.fromkeys(i for i in ids if i.upper() != record_id.upper()))

    tags = []
    low = text.lower()
    for t in (
        "authorization",
        "bola",
        "idor",
        "mutation",
        "ownership",
        "cross-identity",
        "object",
        "graphql",
        "public",
        "shared",
    ):
        if t in low:
            tags.append(t)

    return KnowledgeRecord(
        record_id=record_id,
        kind=kind,
        title=title,
        domain=domain,
        path=str(path.as_posix()),
        security_property=sec[:400],
        abstraction=abstraction[:1200],
        not_same_as=not_same[:12],
        experiment_steps=steps[:12],
        evidence_required=evidence[:12],
        stop_conditions=stops[:12],
        related_ids=related[:12],
        tags=tags,
        raw_excerpt=text[:1500],
        provenance={
            "source_path": str(path.as_posix()),
            "source_kind": kind,
            "loader": "agent_core.knowledge.index",
            "version": "m1",
        },
    )


class KnowledgeIndex:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else _default_knowledge_root()
        self.records: list[KnowledgeRecord] = []
        self.by_id: dict[str, KnowledgeRecord] = {}

    def load(self) -> "KnowledgeIndex":
        self.records.clear()
        self.by_id.clear()
        mapping = {
            "cases": "case",
            "patterns": "pattern",
            "procedures": "procedure",
            "strategies": "strategy",
            "tips": "tip",
            "negative": "negative",
        }
        if not self.root.is_dir():
            return self
        for sub, kind in mapping.items():
            d = self.root / sub
            if not d.is_dir():
                continue
            for path in sorted(d.glob("*.md")):
                rec = parse_knowledge_markdown(path, kind)
                if rec:
                    self.records.append(rec)
                    self.by_id[rec.record_id.upper()] = rec
        return self

    def all_of(self, kind: str) -> list[KnowledgeRecord]:
        return [r for r in self.records if r.kind == kind]
