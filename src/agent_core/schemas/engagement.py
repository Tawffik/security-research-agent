"""Engagement, Authorization, Budget, RiskPolicy — immutable start-of-run contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class EngagementMode(str, Enum):
    AUTHORIZED = "authorized"
    LAB = "lab"
    CTF = "ctf"
    OWNED = "owned"


class RiskTierName(str, Enum):
    PASSIVE = "passive"
    ACTIVE_SAFE = "active_safe"
    ACTIVE_RISKY = "active_risky"
    DESTRUCTIVE = "destructive"


class Authorization(BaseModel):
    """What the operator has explicitly authorized for this engagement."""

    program_name: str
    in_scope_patterns: list[str] = Field(default_factory=list)
    excluded_patterns: list[str] = Field(default_factory=list)
    max_risk_tier: RiskTierName = RiskTierName.ACTIVE_SAFE
    rate_limit_per_host_per_min: int = 30
    concurrency_limit_per_host: int = 2
    notes: str = ""


class Budget(BaseModel):
    token_budget: int = 50_000
    tool_call_budget: int = 200
    request_budget: int = 500
    time_budget_sec: Optional[int] = None


class RiskPolicy(BaseModel):
    default_max_tier: RiskTierName = RiskTierName.ACTIVE_SAFE
    require_approval_for: list[RiskTierName] = Field(
        default_factory=lambda: [RiskTierName.ACTIVE_RISKY, RiskTierName.DESTRUCTIVE]
    )
    allow_destructive: bool = False


class Engagement(BaseModel):
    """
    Immutable engagement root object after start (updates only via explicit versioned patch).

    Matches V2 §6 Engagement Object.
    """

    engagement_id: str
    program: str
    mode: EngagementMode = EngagementMode.AUTHORIZED
    scope: Authorization
    authorization: dict[str, Any] = Field(default_factory=dict)
    identities: list[str] = Field(default_factory=list)
    recon_artifact_ref: Optional[str] = None
    risk_policy: RiskPolicy = Field(default_factory=RiskPolicy)
    budget: Budget = Field(default_factory=Budget)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("engagement_id")
    @classmethod
    def engagement_id_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("engagement_id must be non-empty")
        return v.strip()
