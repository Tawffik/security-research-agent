"""
Engagement orchestrator — Phase A control loop above agent_core.

Wires ScopeGuard, Ledger, EvidenceStore, SkillRegistry, Content Isolation,
and VerificationLoop into a single engagement run.

Default transport is MockTransport (no network). Opt into live HTTP with
EngagementConfig.use_live_http=True — every request still passes
ScopeGuard.authorize() inside the orchestrator before the wire.
"""

from agent_core.orchestrator.engagement import (
    EngagementConfig,
    EngagementOrchestrator,
    EngagementResult,
)
from agent_core.orchestrator.transport import (
    HttpTransport,
    MockTransport,
    TransportResponse,
)

__all__ = [
    "EngagementConfig",
    "EngagementOrchestrator",
    "EngagementResult",
    "HttpTransport",
    "MockTransport",
    "TransportResponse",
]
