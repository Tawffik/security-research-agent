"""Compose closed-loop + adaptive + checkpoint + action regret (lab)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from agent_core.evaluation.action_regret import ActionRegretRecord, ActionRegretTracker
from agent_core.research.surprise import SurpriseEngine, SurpriseEvent
from agent_core.memory.episodic import EpisodicMemory, EpisodeMemoryEntry
from agent_core.ledger.checkpoint import Checkpoint, CheckpointStore
from agent_core.orchestrator.adaptive import AdaptiveLoop, AdaptiveStepResult
from agent_core.orchestrator.closed_loop import ClosedLoopResult, ClosedLoopRunner, LabScenario


def run_closed_then_adaptive(
    *,
    recon_path: Union[str, Path],
    scope_path: Union[str, Path],
    engagement_id: str,
    scenario: Optional[LabScenario] = None,
) -> tuple[ClosedLoopResult, AdaptiveStepResult, Checkpoint, list[ActionRegretRecord], list[SurpriseEvent], list[EpisodeMemoryEntry]]:
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
    return closed, adaptive, cp, [r1, r2], surprises, entries
