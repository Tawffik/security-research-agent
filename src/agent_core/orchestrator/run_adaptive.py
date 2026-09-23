"""Compose closed-loop + adaptive + checkpoint (lab)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from agent_core.ledger.checkpoint import Checkpoint, CheckpointStore
from agent_core.orchestrator.adaptive import AdaptiveLoop, AdaptiveStepResult
from agent_core.orchestrator.closed_loop import ClosedLoopResult, ClosedLoopRunner, LabScenario


def run_closed_then_adaptive(
    *,
    recon_path: Union[str, Path],
    scope_path: Union[str, Path],
    engagement_id: str,
    scenario: Optional[LabScenario] = None,
) -> tuple[ClosedLoopResult, AdaptiveStepResult, Checkpoint]:
    closed = ClosedLoopRunner(scope_path=scope_path, engagement_id=engagement_id).run(
        recon_path, scenario=scenario
    )
    adaptive = AdaptiveLoop(engagement_id).step(closed)
    store = CheckpointStore(engagement_id)
    cp = store.from_closed_and_adaptive(closed, adaptive)
    return closed, adaptive, cp
