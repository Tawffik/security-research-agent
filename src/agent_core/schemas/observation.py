"""
Normalized Observation model (M11).

Raw Response ≠ Observation ≠ Interpretation ≠ Finding
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """First-class research observation with provenance."""

    observation_id: str
    engagement_id: str = ""
    experiment_id: str = ""
    step_id: str = ""
    hypothesis_id: str = ""
    identity: str = ""
    role: str = ""  # baseline | challenge | ""
    method: str = ""
    path: str = ""
    host: str = ""
    status: int = 0
    body: str = ""
    body_excerpt: str = ""
    notes: str = ""
    # Deltas vs baseline (optional; filled when pair available)
    status_delta: Optional[int] = None
    body_changed: Optional[bool] = None
    length_delta: Optional[int] = None
    # Provenance
    tool_name: str = "lab_fixture"
    source: str = "lab"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reproducible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def from_lab_observation(
    lab_obs: Any,
    *,
    engagement_id: str = "",
    experiment_id: str = "",
    step_id: str = "",
    hypothesis_id: str = "",
    index: int = 0,
    baseline: Any = None,
) -> Observation:
    status = int(getattr(lab_obs, "status", 0) or 0)
    body = str(getattr(lab_obs, "body", "") or "")
    status_delta = None
    body_changed = None
    length_delta = None
    if baseline is not None:
        b_status = int(getattr(baseline, "status", 0) or 0)
        b_body = str(getattr(baseline, "body", "") or "")
        status_delta = status - b_status
        body_changed = body != b_body
        length_delta = len(body) - len(b_body)
    return Observation(
        observation_id=f"obs-{index}-{getattr(lab_obs, 'identity', 'x')}-{status}",
        engagement_id=engagement_id,
        experiment_id=experiment_id,
        step_id=step_id,
        hypothesis_id=hypothesis_id,
        identity=str(getattr(lab_obs, "identity", "") or ""),
        role=str(getattr(lab_obs, "role", "") or ""),
        method=str(getattr(lab_obs, "method", "") or ""),
        path=str(getattr(lab_obs, "path", "") or ""),
        host=str(getattr(lab_obs, "host", "") or ""),
        status=status,
        body=body,
        body_excerpt=body[:200],
        notes=str(getattr(lab_obs, "notes", "") or ""),
        status_delta=status_delta,
        body_changed=body_changed,
        length_delta=length_delta,
        tool_name="lab_fixture",
        source="lab",
    )
