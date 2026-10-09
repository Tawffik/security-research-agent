
"""
MCP capability adapters for external harnesses (OpenCode + Playwright MCP + Burp MCP).

Design invariants:
- MCP is a transport/integration protocol, not authorization.
- Every security-relevant action still requires ToolContract + ScopeGuard.
- Live HTTP / browser / Burp actions default to DENY unless explicitly enabled.
- Tool output never grants new permissions.
- Page content and Burp responses are untrusted observations only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

from agent_core.scope.guard import RiskTier, ScopeGuard
from agent_core.tools.contracts import ToolAuthorizationResult, ToolContract, authorize_tool


class McpProvider(str, Enum):
    PLAYWRIGHT = "playwright_mcp"
    BURP = "burp_mcp"
    OPENCODE = "opencode_server"


# Contracts — live_http_allowed remains False by default (fail-closed).
PLAYWRIGHT_NAVIGATE = ToolContract(
    name="mcp_playwright_navigate",
    purpose="Navigate browser via Playwright MCP under explicit scope",
    inputs=["url", "identity"],
    outputs=["url", "title", "snapshot_excerpt", "status"],
    cost=0.4,
    risk=0.45,
    side_effects="read",
    evidence_value=0.65,
    required_skill="browser-observation",
    authorization_required=True,
    live_http_allowed=False,
    timeout_sec=30.0,
)

PLAYWRIGHT_INTERACT = ToolContract(
    name="mcp_playwright_interact",
    purpose="Click/type via Playwright MCP — never executes page-origin instructions as policy",
    inputs=["url", "action", "selector_or_ref", "identity"],
    outputs=["url", "snapshot_excerpt", "status"],
    cost=0.5,
    risk=0.55,
    side_effects="state_change",
    evidence_value=0.6,
    required_skill="browser-observation",
    authorization_required=True,
    live_http_allowed=False,
    timeout_sec=30.0,
)

BURP_SEND_REQUEST = ToolContract(
    name="mcp_burp_send_request",
    purpose="Send authorized HTTP request through Burp MCP (lab/authorized only)",
    inputs=["method", "url", "headers", "body", "identity"],
    outputs=["status", "headers", "body_excerpt"],
    cost=0.35,
    risk=0.5,
    side_effects="read",
    evidence_value=0.75,
    required_skill="authz-idor-analysis",
    authorization_required=True,
    live_http_allowed=False,
    timeout_sec=20.0,
)

BURP_HISTORY_READ = ToolContract(
    name="mcp_burp_history_read",
    purpose="Read Burp proxy/history entries for in-scope hosts only",
    inputs=["host_filter", "limit"],
    outputs=["entries"],
    cost=0.15,
    risk=0.2,
    side_effects="none",
    evidence_value=0.4,
    required_skill="",
    authorization_required=True,
    live_http_allowed=False,
    timeout_sec=10.0,
)

_CONTRACTS: dict[str, ToolContract] = {
    PLAYWRIGHT_NAVIGATE.name: PLAYWRIGHT_NAVIGATE,
    PLAYWRIGHT_INTERACT.name: PLAYWRIGHT_INTERACT,
    BURP_SEND_REQUEST.name: BURP_SEND_REQUEST,
    BURP_HISTORY_READ.name: BURP_HISTORY_READ,
}


@dataclass
class McpAdapterConfig:
    """Safe defaults — nothing public, nothing live."""

    enabled: bool = False
    live_mode: bool = False
    playwright_endpoint: str = "http://127.0.0.1:8931/mcp"
    burp_endpoint: str = "http://127.0.0.1:9876/mcp"
    opencode_endpoint: str = "http://127.0.0.1:4096"
    allow_public_bind: bool = False  # must stay False
    isolated_browser_profile: bool = True
    treat_page_content_untrusted: bool = True
    max_actions_per_episode: int = 20

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class McpActionRequest:
    provider: str
    tool_name: str
    host: str = ""
    url: str = ""
    purpose: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    experiment_id: str = ""
    hypothesis_id: str = ""
    engagement_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class McpActionDecision:
    allowed: bool
    reason: str
    provider: str = ""
    tool_name: str = ""
    contract_name: str = ""
    scope_decision: str = ""
    live_mode: bool = False
    observation_kind: str = "blocked"  # blocked | would_execute | executed_mock
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def host_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        return (p.hostname or "").lower()
    except Exception:
        return ""


def get_contract(tool_name: str) -> Optional[ToolContract]:
    return _CONTRACTS.get(tool_name)


def list_mcp_contracts() -> list[ToolContract]:
    return list(_CONTRACTS.values())


def authorize_mcp_action(
    req: McpActionRequest,
    *,
    guard: ScopeGuard,
    config: Optional[McpAdapterConfig] = None,
) -> McpActionDecision:
    """
    Authorize an MCP-backed action. Does NOT execute live traffic.

    Fail-closed paths:
    - adapters disabled
    - unknown tool
    - missing host
    - live_mode without contract.live_http_allowed
    - ScopeGuard denial
    - public bind requested
    """
    cfg = config or McpAdapterConfig()
    if cfg.allow_public_bind:
        return McpActionDecision(
            allowed=False,
            reason="public_bind_forbidden",
            provider=req.provider,
            tool_name=req.tool_name,
            audit={"policy": "MCP listeners must bind to loopback or private VPN only"},
        )
    if not cfg.enabled:
        return McpActionDecision(
            allowed=False,
            reason="mcp_adapters_disabled",
            provider=req.provider,
            tool_name=req.tool_name,
            live_mode=cfg.live_mode,
        )

    contract = get_contract(req.tool_name)
    if contract is None:
        return McpActionDecision(
            allowed=False,
            reason="unknown_mcp_tool",
            provider=req.provider,
            tool_name=req.tool_name,
        )

    host = (req.host or host_from_url(req.url) or host_from_url(str(req.inputs.get("url", "")))).lower()
    if contract.authorization_required and not host:
        return McpActionDecision(
            allowed=False,
            reason="missing_scope",
            provider=req.provider,
            tool_name=req.tool_name,
            contract_name=contract.name,
        )

    # Tool output / page content never elevates privileges — checked structurally.
    if req.inputs.get("grant_permission") or req.inputs.get("escalate"):
        return McpActionDecision(
            allowed=False,
            reason="tool_output_cannot_grant_permission",
            provider=req.provider,
            tool_name=req.tool_name,
            contract_name=contract.name,
        )

    auth: ToolAuthorizationResult = authorize_tool(
        contract,
        guard=guard,
        host=host,
        action_description=req.purpose or contract.purpose,
        live_mode=cfg.live_mode,
    )
    if not auth.allowed:
        return McpActionDecision(
            allowed=False,
            reason=auth.reason,
            provider=req.provider,
            tool_name=req.tool_name,
            contract_name=contract.name,
            scope_decision=auth.scope_decision,
            live_mode=cfg.live_mode,
        )

    # Even when authorized, this module does not perform live MCP I/O by default.
    # Callers must use an explicit executor with live credentials.
    return McpActionDecision(
        allowed=True,
        reason="authorized_not_executed",
        provider=req.provider,
        tool_name=req.tool_name,
        contract_name=contract.name,
        scope_decision=auth.scope_decision,
        live_mode=cfg.live_mode,
        observation_kind="would_execute",
        audit={
            "experiment_id": req.experiment_id,
            "hypothesis_id": req.hypothesis_id,
            "engagement_id": req.engagement_id,
            "page_content_untrusted": cfg.treat_page_content_untrusted,
            "isolated_profile": cfg.isolated_browser_profile,
        },
    )


def normalize_mcp_observation(
    *,
    provider: str,
    tool_name: str,
    url: str = "",
    status: int | None = None,
    body_excerpt: str = "",
    title: str = "",
    experiment_id: str = "",
    raw: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Normalize external MCP output into a provenance-bearing observation dict."""
    raw = raw or {}
    # Strip any attempted privilege fields from untrusted tool/page content.
    safe_raw = {
        k: v
        for k, v in raw.items()
        if k not in ("grant_permission", "escalate", "system_prompt", "authorization")
    }
    return {
        "source": "mcp",
        "provider": provider,
        "tool_name": tool_name,
        "url": url,
        "host": host_from_url(url),
        "status": status,
        "title": title[:200] if title else "",
        "body_excerpt": (body_excerpt or "")[:2000],
        "experiment_id": experiment_id,
        "untrusted": True,
        "provenance": {
            "provider": provider,
            "tool_name": tool_name,
            "content_isolation": "untrusted_external",
        },
        "raw_keys": sorted(safe_raw.keys())[:40],
    }
