"""
SRA-controlled MCP gateway — the only target-testing path exposed to harnesses.

Path:
  OpenCode / MCP client
    → SRA gateway tools (allowlist)
    → authorize_mcp_action / ScopeGuard
    → SyntheticBrowserRuntime (default) or optional real runtime
    → normalize_mcp_observation + audit

Invariants:
- MCP transport ≠ authorization
- Model prompts cannot grant scope, live_mode, or budgets
- Tool/page/Burp output is untrusted and cannot escalate privileges
- live_mode defaults False; live HTTP stays contract-gated
- Unknown tools and OOS hosts fail closed before any network I/O
- Upstream MCP unavailable → fail closed (no silent success)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from agent_core.integrations.mcp_adapters import (
    BURP_HISTORY_READ,
    BURP_SEND_REQUEST,
    PLAYWRIGHT_INTERACT,
    PLAYWRIGHT_NAVIGATE,
    McpActionDecision,
    McpActionRequest,
    McpAdapterConfig,
    authorize_mcp_action,
    host_from_url,
    normalize_mcp_observation,
)
from agent_core.scope.guard import ScopeGuard
from agent_core.tools.browser_capability import (
    SyntheticBrowserRuntime,
    is_local_only_url,
)


# Tools the LLM may see in the target-testing profile.
GATEWAY_TOOLS = (
    "sra_scope_status",
    "sra_browser_navigate",
    "sra_browser_snapshot",
    "sra_browser_interact",
    "sra_burp_send_request",
    "sra_burp_history_read",
)

_PRIVILEGE_KEYS = frozenset(
    {
        "grant_permission",
        "escalate",
        "system_prompt",
        "authorization",
        "live_mode",
        "approval_token",
        "raise_budget",
        "bypass_scope",
    }
)


@dataclass
class GatewayBudget:
    max_actions: int = 20
    used: int = 0

    def consume(self) -> bool:
        if self.used >= self.max_actions:
            return False
        self.used += 1
        return True


@dataclass
class GatewayResult:
    ok: bool
    tool: str
    reason: str = ""
    observation: dict[str, Any] = field(default_factory=dict)
    decision: Optional[dict[str, Any]] = None
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _strip_privilege(inputs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    bad = [k for k in inputs if k in _PRIVILEGE_KEYS]
    clean = {k: v for k, v in inputs.items() if k not in _PRIVILEGE_KEYS}
    return clean, bad


def _redirect_host(url: str, final_url: str) -> Optional[str]:
    if not final_url or final_url == url:
        return None
    h = host_from_url(final_url)
    return h or None


class SraMcpGateway:
    """
    Bounded executor used by tests and by the optional stdio MCP server entrypoint.

    Default executor is SyntheticBrowserRuntime (no network).
    Real upstream Playwright/Burp processes are optional and never implied by auth alone.
    """

    def __init__(
        self,
        *,
        guard: ScopeGuard,
        config: Optional[McpAdapterConfig] = None,
        browser: Optional[SyntheticBrowserRuntime] = None,
        budget: Optional[GatewayBudget] = None,
        burp_handler: Optional[Callable[..., dict[str, Any]]] = None,
        engagement_id: str = "",
        operator_approval: bool = False,
    ):
        self.guard = guard
        self.config = config or McpAdapterConfig(enabled=True)
        self.browser = browser or SyntheticBrowserRuntime()
        self.budget = budget or GatewayBudget(max_actions=self.config.max_actions_per_episode)
        self.burp_handler = burp_handler
        self.engagement_id = engagement_id
        self.operator_approval = operator_approval
        self.audit_log: list[dict[str, Any]] = []
        self._last_url = ""

    def list_tools(self) -> list[str]:
        return list(GATEWAY_TOOLS)

    def call(self, tool: str, arguments: Optional[dict[str, Any]] = None) -> GatewayResult:
        args = dict(arguments or {})
        clean, bad = _strip_privilege(args)
        if bad:
            return self._deny(tool, "tool_output_cannot_grant_permission", {"stripped_keys": bad})

        if tool not in GATEWAY_TOOLS:
            return self._deny(tool, "unknown_mcp_tool")

        if tool == "sra_scope_status":
            return self._scope_status(clean)

        if not self.budget.consume():
            return self._deny(tool, "budget_exhausted", {"used": self.budget.used})

        if tool == "sra_browser_navigate":
            return self._browser_navigate(clean)
        if tool == "sra_browser_snapshot":
            return self._browser_snapshot(clean)
        if tool == "sra_browser_interact":
            return self._browser_interact(clean)
        if tool == "sra_burp_send_request":
            return self._burp_send(clean)
        if tool == "sra_burp_history_read":
            return self._burp_history(clean)
        return self._deny(tool, "unknown_mcp_tool")

    def _record(self, result: GatewayResult) -> GatewayResult:
        self.audit_log.append(result.to_dict())
        return result

    def _deny(self, tool: str, reason: str, extra: Optional[dict[str, Any]] = None) -> GatewayResult:
        audit = {"engagement_id": self.engagement_id, **(extra or {})}
        return self._record(
            GatewayResult(ok=False, tool=tool, reason=reason, audit=audit)
        )

    def _scope_status(self, args: dict[str, Any]) -> GatewayResult:
        host = str(args.get("host") or host_from_url(str(args.get("url") or "")) or "")
        info = {
            "enabled": self.config.enabled,
            "live_mode": self.config.live_mode,
            "operator_approval": self.operator_approval,
            "budget_used": self.budget.used,
            "budget_max": self.budget.max_actions,
            "host": host,
            "tools": list(GATEWAY_TOOLS),
        }
        if host:
            # Read-only probe of ScopeGuard without claiming execution permission.
            from agent_core.scope.guard import RiskTier

            try:
                d = self.guard.authorize(
                    host=host,
                    risk_tier=RiskTier.PASSIVE,
                    action_description="sra_scope_status",
                )
                info["scope_decision"] = getattr(d, "value", str(d))
            except Exception as exc:  # pragma: no cover — defensive
                info["scope_decision"] = "error"
                info["scope_error"] = type(exc).__name__
        return self._record(
            GatewayResult(ok=True, tool="sra_scope_status", reason="status", observation=info, audit=info)
        )

    def _authorize(
        self,
        *,
        provider: str,
        tool_name: str,
        url: str = "",
        host: str = "",
        purpose: str = "",
        inputs: Optional[dict[str, Any]] = None,
        experiment_id: str = "",
        hypothesis_id: str = "",
    ) -> McpActionDecision:
        return authorize_mcp_action(
            McpActionRequest(
                provider=provider,
                tool_name=tool_name,
                url=url,
                host=host or host_from_url(url),
                purpose=purpose,
                inputs=dict(inputs or {}),
                experiment_id=experiment_id,
                hypothesis_id=hypothesis_id,
                engagement_id=self.engagement_id,
            ),
            guard=self.guard,
            config=self.config,
        )

    def _browser_navigate(self, args: dict[str, Any]) -> GatewayResult:
        url = str(args.get("url") or "")
        experiment_id = str(args.get("experiment_id") or "")
        identity = str(args.get("identity") or "")
        decision = self._authorize(
            provider="playwright_mcp",
            tool_name=PLAYWRIGHT_NAVIGATE.name,
            url=url,
            purpose="sra_browser_navigate",
            inputs=args,
            experiment_id=experiment_id,
        )
        if not decision.allowed:
            return self._deny(
                "sra_browser_navigate",
                decision.reason,
                {"decision": decision.to_dict()},
            )

        # Synthetic local execution — no upstream MCP required.
        obs = self.browser.navigate(
            url,
            guard=self.guard,
            live_mode=False,
            identity=identity,
        )
        final_url = getattr(obs, "final_url", None) or url
        # Redirect / final host re-check
        rh = _redirect_host(url, final_url)
        if rh and not is_local_only_url(final_url):
            recheck = self._authorize(
                provider="playwright_mcp",
                tool_name=PLAYWRIGHT_NAVIGATE.name,
                url=final_url,
                host=rh,
                purpose="redirect_recheck",
                experiment_id=experiment_id,
            )
            if not recheck.allowed:
                return self._deny(
                    "sra_browser_navigate",
                    "redirect_out_of_scope",
                    {"final_url": final_url, "host": rh, "decision": recheck.to_dict()},
                )

        if getattr(obs, "error", None) and not getattr(obs, "authorized", True):
            return self._deny(
                "sra_browser_navigate",
                str(obs.error),
                {"observation_id": getattr(obs, "observation_id", "")},
            )

        self._last_url = final_url
        normalized = normalize_mcp_observation(
            provider="playwright_mcp",
            tool_name=PLAYWRIGHT_NAVIGATE.name,
            url=final_url,
            status=getattr(obs, "status", None),
            body_excerpt=getattr(obs, "dom_excerpt", "") or "",
            title=getattr(obs, "title", "") or "",
            experiment_id=experiment_id,
            raw={
                "observation_id": getattr(obs, "observation_id", ""),
                "synthetic": getattr(obs, "synthetic", True),
                "authorized": getattr(obs, "authorized", True),
            },
        )
        return self._record(
            GatewayResult(
                ok=True,
                tool="sra_browser_navigate",
                reason="executed_synthetic",
                observation=normalized,
                decision=decision.to_dict(),
                audit={
                    "engagement_id": self.engagement_id,
                    "experiment_id": experiment_id,
                    "executor": "SyntheticBrowserRuntime",
                    "observation_id": getattr(obs, "observation_id", ""),
                },
            )
        )

    def _browser_snapshot(self, args: dict[str, Any]) -> GatewayResult:
        url = str(args.get("url") or self._last_url or "")
        if not url:
            return self._deny("sra_browser_snapshot", "no_current_page")
        # Snapshot is read-only on current page — still authorize host.
        decision = self._authorize(
            provider="playwright_mcp",
            tool_name=PLAYWRIGHT_NAVIGATE.name,
            url=url,
            purpose="sra_browser_snapshot",
            experiment_id=str(args.get("experiment_id") or ""),
        )
        if not decision.allowed and not is_local_only_url(url):
            return self._deny("sra_browser_snapshot", decision.reason)

        page = (self.browser.pages or {}).get(url) or {}
        excerpt = str(page.get("dom_excerpt") or "")[:2000]
        normalized = normalize_mcp_observation(
            provider="playwright_mcp",
            tool_name="sra_browser_snapshot",
            url=url,
            status=int(page.get("status") or 200),
            body_excerpt=excerpt,
            title=str(page.get("title") or ""),
            experiment_id=str(args.get("experiment_id") or ""),
        )
        return self._record(
            GatewayResult(
                ok=True,
                tool="sra_browser_snapshot",
                reason="executed_synthetic",
                observation=normalized,
                decision=decision.to_dict() if decision.allowed else None,
                audit={"engagement_id": self.engagement_id},
            )
        )

    def _browser_interact(self, args: dict[str, Any]) -> GatewayResult:
        action = str(args.get("action") or "click")
        selector = str(args.get("selector") or args.get("selector_or_ref") or "")
        value = str(args.get("value") or "")
        page_url = str(args.get("url") or self._last_url or "")
        decision = self._authorize(
            provider="playwright_mcp",
            tool_name=PLAYWRIGHT_INTERACT.name,
            url=page_url,
            purpose="sra_browser_interact",
            inputs=args,
            experiment_id=str(args.get("experiment_id") or ""),
        )
        if not decision.allowed and not is_local_only_url(page_url):
            return self._deny("sra_browser_interact", decision.reason, {"decision": decision.to_dict()})

        obs = self.browser.interact(
            action,
            guard=self.guard,
            selector=selector,
            value=value,
            page_url=page_url,
            identity=str(args.get("identity") or ""),
        )
        if getattr(obs, "error", None) and not getattr(obs, "authorized", True):
            return self._deny("sra_browser_interact", str(obs.error))

        normalized = normalize_mcp_observation(
            provider="playwright_mcp",
            tool_name=PLAYWRIGHT_INTERACT.name,
            url=getattr(obs, "url", "") or page_url,
            status=getattr(obs, "status", None),
            body_excerpt=getattr(obs, "dom_excerpt", "") or "",
            title=getattr(obs, "title", "") or "",
            experiment_id=str(args.get("experiment_id") or ""),
            raw={"observation_id": getattr(obs, "observation_id", ""), "selector": selector},
        )
        return self._record(
            GatewayResult(
                ok=True,
                tool="sra_browser_interact",
                reason="executed_synthetic",
                observation=normalized,
                decision=decision.to_dict() if decision.allowed else None,
                audit={"engagement_id": self.engagement_id, "selector": selector},
            )
        )

    def _burp_send(self, args: dict[str, Any]) -> GatewayResult:
        url = str(args.get("url") or "")
        method = str(args.get("method") or "GET").upper()
        decision = self._authorize(
            provider="burp_mcp",
            tool_name=BURP_SEND_REQUEST.name,
            url=url,
            purpose="sra_burp_send_request",
            inputs=args,
            experiment_id=str(args.get("experiment_id") or ""),
        )
        if not decision.allowed:
            return self._deny("sra_burp_send_request", decision.reason, {"decision": decision.to_dict()})

        if self.burp_handler is None:
            # No live Burp — fail closed for execution, but authorization was proven.
            return self._deny(
                "sra_burp_send_request",
                "burp_upstream_unavailable",
                {
                    "decision": decision.to_dict(),
                    "note": "authorization_passed_execution_blocked_no_upstream",
                },
            )

        try:
            raw = self.burp_handler(method=method, url=url, inputs=args)
        except Exception as exc:
            return self._deny("sra_burp_send_request", f"burp_handler_error:{type(exc).__name__}")

        normalized = normalize_mcp_observation(
            provider="burp_mcp",
            tool_name=BURP_SEND_REQUEST.name,
            url=url,
            status=raw.get("status"),
            body_excerpt=str(raw.get("body_excerpt") or "")[:2000],
            experiment_id=str(args.get("experiment_id") or ""),
            raw=raw if isinstance(raw, dict) else {},
        )
        return self._record(
            GatewayResult(
                ok=True,
                tool="sra_burp_send_request",
                reason="executed_handler",
                observation=normalized,
                decision=decision.to_dict(),
                audit={"engagement_id": self.engagement_id, "method": method},
            )
        )

    def _burp_history(self, args: dict[str, Any]) -> GatewayResult:
        host = str(args.get("host_filter") or args.get("host") or "")
        decision = self._authorize(
            provider="burp_mcp",
            tool_name=BURP_HISTORY_READ.name,
            host=host,
            url=f"https://{host}/" if host else "",
            purpose="sra_burp_history_read",
            inputs=args,
        )
        if not decision.allowed:
            return self._deny("sra_burp_history_read", decision.reason)

        if self.burp_handler is None:
            return self._deny(
                "sra_burp_history_read",
                "burp_upstream_unavailable",
                {"decision": decision.to_dict()},
            )
        return self._deny("sra_burp_history_read", "burp_history_not_implemented_in_gateway")


def default_synthetic_pages() -> dict[str, dict[str, Any]]:
    """Local synthetic app pages for gateway E2E (no network)."""
    return {
        "https://api.acme-demo.test/orders/1": {
            "title": "Order 1",
            "status": 200,
            "dom_excerpt": "<html><body>order_id=1 owner=user_a</body></html>",
            "final_url": "https://api.acme-demo.test/orders/1",
            "elements": {"#submit": "submit-btn"},
        },
        "https://api.acme-demo.test/": {
            "title": "API Home",
            "status": 200,
            "dom_excerpt": "<html><body>api home</body></html>",
            "final_url": "https://api.acme-demo.test/",
        },
        "data:text/html,hello": {
            "title": "local",
            "status": 200,
            "dom_excerpt": "hello",
            "final_url": "data:text/html,hello",
        },
    }
