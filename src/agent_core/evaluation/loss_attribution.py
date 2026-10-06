"""Loss-point attribution — diagnostic only (not a runtime decision engine).

When a candidate disappears, attribute the loss stage for evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class LossStage(str, Enum):
    RECON_LOSS = "RECON_LOSS"
    ADAPTER_LOSS = "ADAPTER_LOSS"
    MODELING_LOSS = "MODELING_LOSS"
    HYPOTHESIS_LOSS = "HYPOTHESIS_LOSS"
    EXPERIMENT_SELECTION_LOSS = "EXPERIMENT_SELECTION_LOSS"
    EXECUTION_LOSS = "EXECUTION_LOSS"
    OBSERVATION_LOSS = "OBSERVATION_LOSS"
    INTERPRETATION_LOSS = "INTERPRETATION_LOSS"
    FALSIFICATION_LOSS = "FALSIFICATION_LOSS"
    VERIFICATION_LOSS = "VERIFICATION_LOSS"
    PROMOTION_LOSS = "PROMOTION_LOSS"
    NONE = "NONE"


@dataclass
class StagePresence:
    recon: bool = False
    adapter: bool = False
    modeling: bool = False
    hypothesis: bool = False
    experiment_selected: bool = False
    executed: bool = False
    observation: bool = False
    interpretation: bool = False
    falsification_evaluated: bool = False
    verification: bool = False
    promoted: bool = False


@dataclass
class LossPointReport:
    candidate_id: str
    loss_stage: str
    present: StagePresence
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def attribute_loss(candidate_id: str, present: StagePresence) -> LossPointReport:
    """First missing stage after the last present stage in the pipeline order."""
    order = [
        ("recon", LossStage.RECON_LOSS),
        ("adapter", LossStage.ADAPTER_LOSS),
        ("modeling", LossStage.MODELING_LOSS),
        ("hypothesis", LossStage.HYPOTHESIS_LOSS),
        ("experiment_selected", LossStage.EXPERIMENT_SELECTION_LOSS),
        ("executed", LossStage.EXECUTION_LOSS),
        ("observation", LossStage.OBSERVATION_LOSS),
        ("interpretation", LossStage.INTERPRETATION_LOSS),
        ("falsification_evaluated", LossStage.FALSIFICATION_LOSS),
        ("verification", LossStage.VERIFICATION_LOSS),
        ("promoted", LossStage.PROMOTION_LOSS),
    ]
    notes: list[str] = []
    for attr, stage in order:
        if not getattr(present, attr):
            notes.append(f"first_absent={attr}")
            return LossPointReport(
                candidate_id=candidate_id,
                loss_stage=stage.value,
                present=present,
                notes=notes,
            )
    return LossPointReport(
        candidate_id=candidate_id,
        loss_stage=LossStage.NONE.value,
        present=present,
        notes=["full_pipeline_present"],
    )
