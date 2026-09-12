"""
Engagement orchestrator — Phase A control loop above agent_core.

Wires ScopeGuard, Ledger, EvidenceStore, SkillRegistry, Content Isolation,
and VerificationLoop into a single engagement run. No live network: the
default transport is mock-only so the loop can be exercised safely before
real HTTP/browser tooling is attached.
"""

from agent_core.orchestrator.engagement import (
    EngagementConfig,
    EngagementOrchestrator,
    EngagementResult,
    MockTransport,
)

__all__ = [
    "EngagementConfig",
    "EngagementOrchestrator",
    "EngagementResult",
    "MockTransport",
]
