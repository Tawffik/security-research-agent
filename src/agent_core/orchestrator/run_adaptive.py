"""Compose closed-loop + adaptive + checkpoint + action regret (lab)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from agent_core.evaluation.action_regret import ActionRegretRecord, ActionRegretTracker
from agent_core.research.surprise import SurpriseEngine, SurpriseEvent
from agent_core.memory.episodic import EpisodicMemory, EpisodeMemoryEntry
from agent_core.evidence.claim_matrix import ClaimEvidenceBuilder, ClaimEvidenceMatrix
from agent_core.security.invariants import InvariantRegistry, InvariantCheck
from agent_core.decisions.stop_conditions import StopPolicy, StopDecision
from agent_core.findings.severity import assess_authz_finding, SeverityAssessment
from agent_core.evaluation.replay import replay_from_objects, ReplaySummary
from agent_core.findings.lifecycle import lifecycle_from_closed_loop, FindingLifecycle
from agent_core.experiments.differential import compare_lab_observations, DifferentialResult
from agent_core.experiments.dedup import ExperimentDeduper
from agent_core.ledger.checkpoint import Checkpoint, CheckpointStore
from agent_core.orchestrator.adaptive import AdaptiveLoop, AdaptiveStepResult
from agent_core.orchestrator.closed_loop import ClosedLoopResult, ClosedLoopRunner, LabScenario


def run_closed_then_adaptive(
    *,
    recon_path: Union[str, Path],
    scope_path: Union[str, Path],
    engagement_id: str,
    scenario: Optional[LabScenario] = None,
) -> tuple:
    closed = ClosedLoopRunner(scope_path=scope_path, engagement_id=engagement_id).run(
        recon_path, scenario=scenario
    )
    adaptive = AdaptiveLoop(engagement_id).step(closed)
    store = CheckpointStore(engagement_id)
    cp = store.from_closed_and_adaptive(closed, adaptive)
    tracker = ActionRegretTracker(engagement_id)
    r1 = tracker.record_closed_loop(closed)
    r2 = tracker.record_adaptive(adaptive)
    surprises = SurpriseEngine(engagement_id).from_lab_observations(
        closed.observations,
        suggests_authz_issue=bool(
            closed.referee_accepted or (closed.final_status == "confirmed")
        ),
    )
    # If rejected secure path, still evaluate (should yield no high surprise on 403)
    if not surprises and closed.observations:
        surprises = SurpriseEngine(engagement_id).from_lab_observations(
            closed.observations,
            suggests_authz_issue=False,
        )
    lessons = []
    if closed.episode and getattr(closed.episode, "lessons", None):
        lessons = list(closed.episode.lessons)
    mem = EpisodicMemory(engagement_id)
    entries = mem.ingest_from_pipeline(
        closed=closed,
        adaptive=adaptive,
        surprises=surprises,
        episode_lessons=lessons,
    )
    claim_text = ""
    if closed.report is not None:
        claim_text = closed.report.claim
    matrix = ClaimEvidenceBuilder(engagement_id).build(
        claim=claim_text or f"status={closed.final_status}",
        evidence_ids=list(closed.evidence_ids or []),
        observation_refs=[f"{o.identity}:{o.status}" for o in (closed.observations or [])],
        action_summary="lab cross-identity object access",
    )
    inv_checks: list[InvariantCheck] = []
    non_owner = [o for o in (closed.observations or []) if not (o.identity.endswith("_a") or "owner" in o.identity)]
    if non_owner:
        inv_checks.append(
            InvariantRegistry(engagement_id).check_ownership_from_lab(
                non_owner_status=non_owner[0].status,
                evidence_ids=list(closed.evidence_ids or []),
            )
        )
    mean_reg = None
    if [r1, r2]:
        mean_reg = round((r1.regret + r2.regret) / 2, 4)
    stop_decision = StopPolicy().evaluate(
        scope_allowed=closed.scope_allowed,
        referee_accepted=closed.referee_accepted,
        final_status=closed.final_status or "",
        evidence_count=len(closed.evidence_ids or []),
        has_variants=bool(closed.variants),
        adaptive_stop=adaptive.stop,
        adaptive_reason=adaptive.stop_reason or "",
        mean_action_regret=mean_reg,
    )
    inv_violated = None
    if inv_checks:
        inv_violated = inv_checks[0].holds is False
    severity = assess_authz_finding(
        confirmed=bool(closed.referee_accepted),
        invariant_violated=inv_violated,
        cross_identity=True,
    )
    replay = replay_from_objects(engagement_id=engagement_id, closed=closed, checkpoint=cp)
    lifecycle = lifecycle_from_closed_loop(closed)
    differential = compare_lab_observations(closed.observations or [])
    deduper = ExperimentDeduper()
    for o in closed.observations or []:
        deduper.check_and_register(
            method=o.method,
            path=o.path,
            identity=o.identity,
            hypothesis_id=closed.finding_id or "",
            action=f"{o.method} {o.path}",
        )
    return (
        closed,
        adaptive,
        cp,
        [r1, r2],
        surprises,
        entries,
        matrix,
        inv_checks,
        stop_decision,
        severity,
        replay,
        lifecycle,
        differential,
        deduper,
    )
