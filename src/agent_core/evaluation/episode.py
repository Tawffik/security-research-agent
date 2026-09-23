"""
Research Episodes + quality metrics (V2 §46 / evaluation).

North-star orientation:
  Validated Discovery Efficiency ≈
    (Validated Findings × Evidence Quality × Novelty)
    / (Requests + Tool Calls + Tokens + Time + Risk)

We do NOT score "more requests" or "more hypotheses" as success.
Prefer: discriminating experiments, clean stop reasons, evidence-linked findings.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class EpisodeMetrics:
    """Quality-oriented counters — not spray metrics."""

    hypotheses_generated: int = 0
    useful_hypotheses: int = 0  # supported or rejected with evidence
    experiments_designed: int = 0
    observations: int = 0
    evidence_items: int = 0
    confirmed_findings: int = 0
    rejected_claims: int = 0
    false_positive_avoided: int = 0  # skeptic/referee rejected candidate
    requests_simulated: int = 0  # lab only unless live later
    variants_suggested: int = 0
    root_causes: int = 0
    report_blocked: bool = False
    stop_reason: str = ""
    evidence_quality_score: float = 0.0  # 0..1 heuristic
    novelty_score: float = 0.0  # 0..1 heuristic (lab baseline)
    efficiency_proxy: float = 0.0  # quality / cost proxy

    def compute(self) -> None:
        # Evidence quality: prefer multiple evidence + non-blocked report
        eq = 0.0
        if self.evidence_items > 0:
            eq += 0.4
        if self.evidence_items >= 2:
            eq += 0.3
        if self.confirmed_findings and not self.report_blocked:
            eq += 0.3
        if self.rejected_claims and self.evidence_items:
            eq += 0.1  # negative path also evidence-backed
        self.evidence_quality_score = min(1.0, eq)

        # Novelty: structural variants or root cause beyond single finding
        nov = 0.0
        if self.confirmed_findings:
            nov += 0.4
        if self.root_causes:
            nov += 0.3
        if self.variants_suggested:
            nov += min(0.3, 0.1 * self.variants_suggested)
        self.novelty_score = min(1.0, nov)

        # Cost proxy: requests + experiments (tokens not used offline)
        cost = max(1, self.requests_simulated + self.experiments_designed)
        value = (
            self.confirmed_findings * self.evidence_quality_score * max(0.1, self.novelty_score)
            + (0.15 * self.false_positive_avoided * self.evidence_quality_score)
        )
        self.efficiency_proxy = round(value / cost, 4)

    def to_dict(self) -> dict[str, Any]:
        self.compute()
        return asdict(self)


@dataclass
class ResearchEpisode:
    episode_id: str
    engagement_id: str
    created_at: str
    outcome: str  # confirmed | rejected | scope_denied | incomplete
    stop_reason: str
    hypothesis_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    finding_id: Optional[str] = None
    root_cause_id: Optional[str] = None
    variant_ids: list[str] = field(default_factory=list)
    poc_id: Optional[str] = None
    belief_updates: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    metrics: EpisodeMetrics = field(default_factory=EpisodeMetrics)
    lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "engagement_id": self.engagement_id,
            "created_at": self.created_at,
            "outcome": self.outcome,
            "stop_reason": self.stop_reason,
            "hypothesis_ids": list(self.hypothesis_ids),
            "evidence_ids": list(self.evidence_ids),
            "finding_id": self.finding_id,
            "root_cause_id": self.root_cause_id,
            "variant_ids": list(self.variant_ids),
            "poc_id": self.poc_id,
            "belief_updates": list(self.belief_updates),
            "limitations": list(self.limitations),
            "metrics": self.metrics.to_dict(),
            "lessons": list(self.lessons),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class EpisodeRecorder:
    """Build a ResearchEpisode from a closed-loop result (quality-first)."""

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0

    def from_closed_loop(self, result: Any) -> ResearchEpisode:
        self._n += 1
        eid = f"EP-{self._n:03d}-{self.engagement_id}"

        if not result.scope_allowed:
            outcome = "scope_denied"
        elif result.referee_accepted:
            outcome = "confirmed"
        elif result.final_status == "rejected":
            outcome = "rejected"
        else:
            outcome = "incomplete"

        hyp_ids: list[str] = []
        plan = getattr(result, "plan", None)
        if plan is not None:
            hyps = getattr(plan, "hypotheses", None) or []
            hyp_ids = [getattr(h, "hypothesis_id", str(h)) for h in hyps]

        metrics = EpisodeMetrics(
            hypotheses_generated=len(hyp_ids),
            useful_hypotheses=1 if result.evidence_ids else 0,
            experiments_designed=1 if plan and getattr(plan, "experiments", None) else 0,
            observations=len(result.observations or []),
            evidence_items=len(result.evidence_ids or []),
            confirmed_findings=1 if result.referee_accepted else 0,
            rejected_claims=1 if outcome == "rejected" else 0,
            false_positive_avoided=1 if outcome == "rejected" else 0,
            requests_simulated=len(result.observations or []),
            variants_suggested=len(result.variants or []),
            root_causes=1 if result.root_cause else 0,
            report_blocked=bool(result.report and result.report.report_blocked),
            stop_reason=result.stop_reason or "",
        )
        metrics.compute()

        lessons: list[str] = []
        if outcome == "confirmed":
            lessons.append("Discriminating cross-identity experiment produced evidence-backed finding")
            if result.root_cause:
                lessons.append(f"Root cause signature: {result.root_cause.signature}")
            if result.variants:
                lessons.append(
                    f"Structural variants prioritized ({len(result.variants)}) — not full URL spray"
                )
        elif outcome == "rejected":
            lessons.append(
                "Negative evidence preserved; avoided promoting false positive — quality over volume"
            )
        elif outcome == "scope_denied":
            lessons.append("ScopeGuard blocked action — correct stop, zero wasted target interaction")

        if metrics.efficiency_proxy > 0 and metrics.requests_simulated <= 4:
            lessons.append("Low request count with useful outcome — aligned with north-star efficiency")

        return ResearchEpisode(
            episode_id=eid,
            engagement_id=self.engagement_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            outcome=outcome,
            stop_reason=result.stop_reason or "",
            hypothesis_ids=hyp_ids,
            evidence_ids=list(result.evidence_ids or []),
            finding_id=result.finding_id,
            root_cause_id=result.root_cause.root_cause_id if result.root_cause else None,
            variant_ids=[v.variant_id for v in (result.variants or [])],
            poc_id=result.poc.poc_id if result.poc else None,
            belief_updates=list(result.belief_updates or []),
            limitations=list(result.limitations or []),
            metrics=metrics,
            lessons=lessons,
        )

    def write(self, episode: ResearchEpisode, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{episode.episode_id}.json"
        path.write_text(episode.to_json())
        return path
