"""
Canonical data models for Security Research Agent V2.

These schemas are the contract between modules. Free-form dicts are not
allowed in core state paths; everything important is validated here.

Phase: Sprint 1 / Phase 2 (Canonical Data Model).
"""

from agent_core.schemas.engagement import (
    Engagement,
    EngagementMode,
    Authorization,
    Budget,
    RiskPolicy,
    RiskTierName,
)
from agent_core.schemas.target import (
    Actor,
    ActorType,
    Role,
    Resource,
    ResourceType,
    Endpoint,
    Relationship,
    RelationshipKind,
    TargetContext,
    TargetGraph,
)
from agent_core.schemas.research import (
    Opportunity,
    Priority,
    Unknown,
    Belief,
    Hypothesis,
    HypothesisStatus,
    AlternativeExplanation,
    Experiment,
    ExperimentStatus,
    Decision,
    DecisionAction,
    Observation,
    Claim,
    Finding,
    FindingStatus,
)

__all__ = [
    "Engagement",
    "EngagementMode",
    "Authorization",
    "Budget",
    "RiskPolicy",
    "RiskTierName",
    "Actor",
    "ActorType",
    "Role",
    "Resource",
    "ResourceType",
    "Endpoint",
    "Relationship",
    "RelationshipKind",
    "TargetContext",
    "TargetGraph",
    "Opportunity",
    "Priority",
    "Unknown",
    "Belief",
    "Hypothesis",
    "HypothesisStatus",
    "AlternativeExplanation",
    "Experiment",
    "ExperimentStatus",
    "Decision",
    "DecisionAction",
    "Observation",
    "Claim",
    "Finding",
    "FindingStatus",
]
