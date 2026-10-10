"""
Knowledge candidates from research episodes (M8).

Invariant: episode ≠ trusted knowledge.
Candidates remain untrusted until an explicit promotion gate passes.
This module never writes into knowledge/cases|patterns|procedures as approved.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class CandidateKind(str, Enum):
    POSITIVE = "positive"  # issue-supporting lesson under specific context
    NEGATIVE = "negative"  # benign / enforcement-supporting under specific context
    PROCEDURE_IMPROVEMENT = "procedure_improvement"
    STRATEGY = "strategy"


class CandidateStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"  # passed local checks, still not global trusted knowledge
    REJECTED = "rejected"
    PROMOTED = "promoted"  # only after explicit promote() — still writes candidate ledger, not MD corpus


@dataclass
class KnowledgeCandidate:
    candidate_id: str
    kind: CandidateKind
    status: CandidateStatus
    summary: str
    episode_id: str = ""
    engagement_id: str = ""
    experiment_id: str = ""
    hypothesis_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    security_property: str = "unknown"
    target_host: str = ""
    context_notes: str = ""
    confidence: float = 0.4
    universal_claim: bool = False  # must stay False for safety
    created_at: str = ""
    rejection_reason: str = ""
    promotion_reason: str = ""
    benchmark_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandidateStore:
    """JSONL ledger of candidates — not the curated knowledge/ corpus."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self._items: list[KnowledgeCandidate] = []
        self._n = 0

    def add(self, c: KnowledgeCandidate) -> KnowledgeCandidate:
        self._items.append(c)
        return c

    def list_all(self) -> list[KnowledgeCandidate]:
        return list(self._items)

    def by_status(self, status: CandidateStatus) -> list[KnowledgeCandidate]:
        return [c for c in self._items if c.status == status]

    def write_jsonl(self, path: Optional[Path] = None) -> Path:
        path = path or self.path
        if path is None:
            raise ValueError("path required")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for c in self._items:
                f.write(json.dumps(c.to_dict()) + "\n")
        return path


class KnowledgeCandidateFactory:
    """Build candidates from closed-loop + episode — never auto-promotes."""

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0

    def from_closed_loop(
        self,
        closed: Any,
        *,
        episode_id: str = "",
    ) -> list[KnowledgeCandidate]:
        out: list[KnowledgeCandidate] = []
        align = getattr(closed, "experiment_alignment", None) or {}
        if not isinstance(align, dict):
            align = {}
        episode = getattr(closed, "episode", None)
        ep_id = episode_id or (getattr(episode, "episode_id", "") if episode else "")
        host = ""
        plan = getattr(closed, "plan", None)
        if plan is not None and getattr(plan, "target_context", None):
            host = getattr(plan.target_context, "primary_host", "") or ""

        exp_id = getattr(closed, "selected_experiment_id", None) or align.get("experiment_id") or ""
        hyp_id = align.get("hypothesis_id") or ""
        evidence = list(getattr(closed, "evidence_ids", None) or [])
        # Propagate methodology from scenario/result — never invent authorization.
        prop = (
            getattr(closed, "methodology", None)
            or align.get("methodology")
            or ""
        )
        prop = str(prop).strip().lower() or "unknown"

        # Positive candidate only as context-bound, non-universal
        if getattr(closed, "referee_accepted", False):
            self._n += 1
            out.append(
                KnowledgeCandidate(
                    candidate_id=f"KC-{self.engagement_id}-{self._n:03d}",
                    kind=CandidateKind.POSITIVE,
                    status=CandidateStatus.PROPOSED,
                    summary=(
                        f"Context-bound {prop} finding candidate from lab episode; "
                        "not a global vulnerability pattern"
                    ),
                    episode_id=ep_id,
                    engagement_id=self.engagement_id,
                    experiment_id=str(exp_id),
                    hypothesis_id=str(hyp_id),
                    evidence_ids=evidence,
                    security_property=prop,
                    target_host=host,
                    context_notes="lab fixture; requires independent validation before promotion",
                    confidence=0.55,
                    universal_claim=False,
                    created_at=_now(),
                )
            )

        # Negative candidate: enforcement observed — still not universal "secure"
        final = getattr(closed, "final_status", "") or ""
        if final == "rejected" or (
            not getattr(closed, "referee_accepted", False)
            and getattr(closed, "scope_allowed", True)
            and evidence
            and not getattr(closed, "referee_accepted", False)
            and final in ("rejected", "incomplete")
            and any(
                getattr(o, "status", 0) in (401, 403, 404)
                for o in (getattr(closed, "observations", None) or [])
            )
        ):
            # Prefer explicit rejected
            if final == "rejected" or (
                not getattr(closed, "referee_accepted", False)
                and final == "rejected"
            ):
                pass
            if final == "rejected":
                self._n += 1
                out.append(
                    KnowledgeCandidate(
                        candidate_id=f"KC-{self.engagement_id}-{self._n:03d}",
                        kind=CandidateKind.NEGATIVE,
                        status=CandidateStatus.PROPOSED,
                        summary=(
                            "Context-bound enforcement observation (negative path); "
                            "must not be read as universal non-vulnerability"
                        ),
                        episode_id=ep_id,
                        engagement_id=self.engagement_id,
                        experiment_id=str(exp_id),
                        hypothesis_id=str(hyp_id),
                        evidence_ids=evidence,
                        security_property=prop,
                        target_host=host,
                        context_notes="negative result is scoped to this engagement/fixture only",
                        confidence=0.5,
                        universal_claim=False,
                        created_at=_now(),
                    )
                )

        # Procedure improvement when coverage was insufficient/ambiguous
        suf = align.get("experiment_sufficiency")
        gap = align.get("coverage_gap") or {}
        if suf in ("insufficient", "ambiguous"):
            self._n += 1
            roles = (gap.get("missing_roles") or []) + (gap.get("ambiguous_roles") or [])
            out.append(
                KnowledgeCandidate(
                    candidate_id=f"KC-{self.engagement_id}-{self._n:03d}",
                    kind=CandidateKind.PROCEDURE_IMPROVEMENT,
                    status=CandidateStatus.PROPOSED,
                    summary=f"Procedure coverage {suf}; roles={roles} — candidate for procedure refinement",
                    episode_id=ep_id,
                    engagement_id=self.engagement_id,
                    experiment_id=str(exp_id),
                    hypothesis_id=str(hyp_id),
                    evidence_ids=evidence,
                    security_property="authorization",
                    target_host=host,
                    context_notes="coverage gap lesson; not a finding",
                    confidence=0.45,
                    universal_claim=False,
                    created_at=_now(),
                )
            )

        return out


class PromotionGate:
    """
    Explicit promotion boundary.

    Validated ≠ globally trusted knowledge MD.
    promote() only marks PROMOTED on the candidate ledger after checks.
    """

    def validate(self, candidate: KnowledgeCandidate) -> tuple[bool, str]:
        if candidate.universal_claim:
            return False, "universal_claim_forbidden"
        if not candidate.evidence_ids and candidate.kind in (
            CandidateKind.POSITIVE,
            CandidateKind.NEGATIVE,
        ):
            return False, "evidence_required"
        if not candidate.episode_id and not candidate.engagement_id:
            return False, "provenance_required"
        if candidate.kind == CandidateKind.NEGATIVE and "universal" in candidate.summary.lower():
            return False, "negative_must_not_claim_universal"
        if candidate.status == CandidateStatus.REJECTED:
            return False, "already_rejected"
        return True, "ok"

    def mark_validated(self, candidate: KnowledgeCandidate) -> KnowledgeCandidate:
        ok, reason = self.validate(candidate)
        if not ok:
            candidate.status = CandidateStatus.REJECTED
            candidate.rejection_reason = reason
            return candidate
        candidate.status = CandidateStatus.VALIDATED
        return candidate

    def promote(self, candidate: KnowledgeCandidate, *, reason: str) -> KnowledgeCandidate:
        """
        Mark promoted only if validated. Does NOT write knowledge/*.md.
        """
        if candidate.status != CandidateStatus.VALIDATED:
            ok, r = self.validate(candidate)
            if not ok:
                candidate.status = CandidateStatus.REJECTED
                candidate.rejection_reason = r
                return candidate
            candidate.status = CandidateStatus.VALIDATED
        candidate.status = CandidateStatus.PROMOTED
        candidate.promotion_reason = reason
        return candidate


@dataclass
class SkillCandidate:
    """Benchmark-gated skill candidate — still not a runtime skill file."""

    skill_candidate_id: str
    from_candidate_id: str
    status: str = "pending_benchmark"  # pending_benchmark | rejected | approved_for_review
    benchmark_case_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def promote_to_skill_candidate(
    candidate: KnowledgeCandidate,
    *,
    benchmark_false_positive: bool,
    benchmark_true_positive: bool = False,
) -> SkillCandidate:
    """
    Benchmark gate: never approve skill candidate on FP.
    Positive knowledge needs TP signal; negative/procedure can go to review without TP.
    """
    sid = f"SKC-{candidate.candidate_id}"
    if candidate.universal_claim:
        return SkillCandidate(
            skill_candidate_id=sid,
            from_candidate_id=candidate.candidate_id,
            status="rejected",
            reason="universal_claim_forbidden",
        )
    if benchmark_false_positive:
        return SkillCandidate(
            skill_candidate_id=sid,
            from_candidate_id=candidate.candidate_id,
            status="rejected",
            reason="benchmark_false_positive",
        )
    if candidate.kind == CandidateKind.POSITIVE and not candidate.benchmark_snapshot and not benchmark_true_positive:
        return SkillCandidate(
            skill_candidate_id=sid,
            from_candidate_id=candidate.candidate_id,
            status="pending_benchmark",
            reason="benchmark_snapshot_required",
        )
    if candidate.kind == CandidateKind.POSITIVE and not benchmark_true_positive:
        return SkillCandidate(
            skill_candidate_id=sid,
            from_candidate_id=candidate.candidate_id,
            status="pending_benchmark",
            reason="positive_requires_true_positive_benchmark",
        )
    if candidate.status not in (CandidateStatus.VALIDATED, CandidateStatus.PROMOTED):
        return SkillCandidate(
            skill_candidate_id=sid,
            from_candidate_id=candidate.candidate_id,
            status="pending_benchmark",
            reason="candidate_not_validated",
        )
    return SkillCandidate(
        skill_candidate_id=sid,
        from_candidate_id=candidate.candidate_id,
        status="approved_for_review",
        reason="benchmark_gate_passed_human_review_still_required",
    )
