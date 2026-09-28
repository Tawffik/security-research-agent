"""
Controlled import of promoted candidates into curated knowledge (offline).

Never imports rejected/unreviewed/benchmark-failing candidates.
Never grants execution permission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_core.knowledge.candidates import (
    CandidateStatus,
    KnowledgeCandidate,
    SkillCandidate,
)
from agent_core.knowledge.compiler import GeneratedArtifact


@dataclass
class ImportResult:
    ok: bool
    path: Optional[str] = None
    reason: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "reason": self.reason,
            "provenance": dict(self.provenance),
        }


class CuratedKnowledgeImporter:
    """
    Writes markdown only under an explicit import directory when gates pass.
    Default root: knowledge/imported/ (not cases/patterns/procedures trusted paths
    unless force_trusted_subdir is set carefully).
    """

    def __init__(self, knowledge_root: Path, *, import_subdir: str = "imported"):
        self.root = knowledge_root
        self.import_dir = knowledge_root / import_subdir

    def can_import_candidate(self, c: KnowledgeCandidate) -> tuple[bool, str]:
        if c.universal_claim:
            return False, "universal_claim_forbidden"
        if c.status != CandidateStatus.PROMOTED:
            return False, f"status_not_promoted:{c.status.value}"
        if c.kind.value in ("positive", "negative"):
            snap = c.benchmark_snapshot or {}
            if not snap:
                return False, "benchmark_snapshot_required"
            if snap.get("false_positive"):
                return False, "benchmark_false_positive"
        if not c.episode_id and not c.engagement_id:
            return False, "provenance_required"
        return True, "ok"

    def can_import_skill_candidate(self, sk: SkillCandidate, c: KnowledgeCandidate) -> tuple[bool, str]:
        if sk.status != "approved_for_review":
            return False, f"skill_status:{sk.status}"
        ok, reason = self.can_import_candidate(c)
        if not ok:
            return False, reason
        # Human review still required — import only to review staging
        return True, "ok_staging_only"

    def import_candidate(
        self,
        c: KnowledgeCandidate,
        *,
        human_review_token: str = "",
    ) -> ImportResult:
        ok, reason = self.can_import_candidate(c)
        if not ok:
            return ImportResult(ok=False, reason=reason)
        if not human_review_token:
            return ImportResult(ok=False, reason="human_review_token_required")

        self.import_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", c.candidate_id)
        path = self.import_dir / f"{safe_id}.md"
        if path.exists():
            return ImportResult(
                ok=True,
                path=str(path),
                reason="already_imported",
                provenance={"candidate_id": c.candidate_id, "dedup": True},
            )

        body = self._render_md(c, human_review_token)
        path.write_text(body, encoding="utf-8")
        return ImportResult(
            ok=True,
            path=str(path),
            reason="imported",
            provenance={
                "candidate_id": c.candidate_id,
                "episode_id": c.episode_id,
                "experiment_id": c.experiment_id,
                "evidence_ids": list(c.evidence_ids),
                "benchmark_snapshot": dict(c.benchmark_snapshot or {}),
                "human_review_token": human_review_token,
                "status": "imported_untrusted_staging",
            },
        )

    def import_generated_artifact(
        self,
        art: GeneratedArtifact,
        *,
        human_review_token: str = "",
    ) -> ImportResult:
        if art.status != "validated":
            return ImportResult(ok=False, reason=f"artifact_status:{art.status}")
        if not human_review_token:
            return ImportResult(ok=False, reason="human_review_token_required")
        self.import_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", art.artifact_id)
        path = self.import_dir / f"{safe_id}.md"
        if path.exists():
            return ImportResult(ok=True, path=str(path), reason="already_imported")
        body = (
            f"# {art.artifact_id} — {art.title}\n\n"
            f"**Type:** {art.kind.upper()} (IMPORTED CANDIDATE — NOT AUTO-TRUSTED)\n"
            f"**Status:** STAGING\n"
            f"**Domain:** {art.domain}\n"
            f"**Security property:** {art.security_property}\n\n"
            f"## Abstraction\n{art.abstraction}\n\n"
            f"## Provenance\n"
            f"- source_unit_ids: {', '.join(art.source_unit_ids)}\n"
            f"- source_ids: {', '.join(art.source_ids)}\n"
            f"- confidence: {art.confidence}\n"
            f"- review: {human_review_token}\n"
            f"- origin: knowledge_compiler_generate\n"
        )
        if art.experiment_steps:
            body += "\n## Minimum experiment\n"
            for i, s in enumerate(art.experiment_steps, 1):
                body += f"{i}. {s}\n"
        path.write_text(body, encoding="utf-8")
        return ImportResult(ok=True, path=str(path), reason="imported")

    def _render_md(self, c: KnowledgeCandidate, token: str) -> str:
        return (
            f"# {c.candidate_id}\n\n"
            f"**Type:** KNOWLEDGE_CANDIDATE_IMPORT\n"
            f"**Status:** STAGING (not trusted corpus)\n"
            f"**Kind:** {c.kind.value}\n"
            f"**Security property:** {c.security_property}\n\n"
            f"## Summary\n{c.summary}\n\n"
            f"## Provenance\n"
            f"- episode_id: {c.episode_id}\n"
            f"- engagement_id: {c.engagement_id}\n"
            f"- experiment_id: {c.experiment_id}\n"
            f"- evidence_ids: {', '.join(c.evidence_ids)}\n"
            f"- host: {c.target_host}\n"
            f"- benchmark: {c.benchmark_snapshot}\n"
            f"- human_review: {token}\n"
            f"- universal_claim: {c.universal_claim}\n"
        )
