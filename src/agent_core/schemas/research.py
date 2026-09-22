"""Research state: Opportunity, Unknown, Belief, Hypothesis, Experiment, Decision, Finding."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Opportunity(BaseModel):
    """Where the agent should invest research time (V2 §10)."""

    opportunity_id: str
    type: str  # e.g. authorization, state_violation, business_logic
    target: str
    identity_surface: bool = False
    object_surface: bool = False
    stateful: bool = False
    mutation: bool = False
    privilege_boundary: bool = False
    data_sensitivity: str = "unknown"
    novelty: float = Field(default=0.5, ge=0.0, le=1.0)
    testability: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_potential: float = Field(default=0.5, ge=0.0, le=1.0)
    cost: float = Field(default=0.5, ge=0.0, le=1.0)
    risk: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: Priority = Priority.MEDIUM
    metadata: dict[str, Any] = Field(default_factory=dict)


class Unknown(BaseModel):
    """Explicit knowledge gap (V2 §11)."""

    unknown_id: str
    question: str
    why_it_matters: str = ""
    current_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_experiment_ids: list[str] = Field(default_factory=list)
    related_hypothesis_ids: list[str] = Field(default_factory=list)


class Belief(BaseModel):
    """Claim with confidence and supporting/contradicting evidence (V2 §12)."""

    belief_id: str
    claim: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    source: str = ""
    last_updated: Optional[float] = None
    expiry: Optional[float] = None


class AlternativeExplanation(BaseModel):
    explanation_id: str
    description: str
    discriminating_observations: list[str] = Field(default_factory=list)


class HypothesisStatus(str, Enum):
    OPEN = "open"
    TESTING = "testing"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Hypothesis(BaseModel):
    """Competing explanation branch (V2 §13–14)."""

    hypothesis_id: str
    statement: str
    primary_explanation: str = ""
    alternatives: list[AlternativeExplanation] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: HypothesisStatus = HypothesisStatus.OPEN
    related_unknown_ids: list[str] = Field(default_factory=list)
    related_opportunity_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    parent_hypothesis_id: Optional[str] = None


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    CACHED = "cached"
    ABORTED = "aborted"


class Experiment(BaseModel):
    """Minimum discriminating experiment (V2 §15)."""

    experiment_id: str
    hypothesis_id: str
    description: str
    expected_observation: str = ""
    discriminator: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    stop_condition: str = ""
    risk: float = Field(default=0.3, ge=0.0, le=1.0)
    cost: float = Field(default=0.3, ge=0.0, le=1.0)
    information_gain: float = Field(default=0.5, ge=0.0, le=1.0)
    status: ExperimentStatus = ExperimentStatus.PLANNED
    tool_names: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)


class DecisionAction(str, Enum):
    EXECUTE = "EXECUTE"
    SKIP = "SKIP"
    STOP = "STOP"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    BACKTRACK = "BACKTRACK"


class Decision(BaseModel):
    """Structured JEV output (V2 §17). Cannot override ScopeGuard/Risk/Budget."""

    decision_id: str
    decision: DecisionAction
    candidate: str = ""  # experiment_id or skill_id
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    hypothesis_id: Optional[str] = None
    experiment_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason_codes")
    @classmethod
    def at_least_one_reason_when_execute(cls, v: list[str], info) -> list[str]:
        return v


class Observation(BaseModel):
    observation_id: str
    experiment_id: Optional[str] = None
    action_id: Optional[str] = None
    summary: str
    raw_artifact_ref: Optional[str] = None
    polarity: str = "neutral"  # positive | negative | neutral | surprise
    timestamp: Optional[float] = None


class Claim(BaseModel):
    claim_id: str
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    verified: bool = False
    verifier: str = ""


class FindingStatus(str, Enum):
    CANDIDATE = "candidate"
    INVESTIGATING = "investigating"
    EVIDENCE_READY = "evidence_ready"
    SKEPTIC_REVIEW = "skeptic_review"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    CONFIRMED = "confirmed"


class Finding(BaseModel):
    """Lifecycle-aware finding (V2 §41). CONFIRMED only after full DoD."""

    finding_id: str
    title: str
    claim: str
    status: FindingStatus = FindingStatus.CANDIDATE
    claims: list[Claim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    hypothesis_id: Optional[str] = None
    root_cause: Optional[str] = None
    variant_of: Optional[str] = None
    poc_ref: Optional[str] = None
    scope_valid: bool = False
    skeptic_disproof_attempted: bool = False
    reproducible: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
