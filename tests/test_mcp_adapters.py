"""MCP adapter authorization — fail-closed, ScopeGuard gated."""

from pathlib import Path

from agent_core.integrations.mcp_adapters import (
    BURP_SEND_REQUEST,
    PLAYWRIGHT_NAVIGATE,
    McpActionRequest,
    McpAdapterConfig,
    authorize_mcp_action,
    get_contract,
    host_from_url,
    list_mcp_contracts,
    normalize_mcp_observation,
)
from agent_core.scope.guard import ScopeGuard


def _guard() -> ScopeGuard:
    root = Path(__file__).resolve().parents[1]
    return ScopeGuard.from_scope_file(root / "examples" / "demo_program_scope.yaml")


def test_contracts_registered():
    names = {c.name for c in list_mcp_contracts()}
    assert "mcp_playwright_navigate" in names
    assert "mcp_burp_send_request" in names
    assert get_contract("mcp_playwright_navigate") is PLAYWRIGHT_NAVIGATE
    assert BURP_SEND_REQUEST.live_http_allowed is False


def test_disabled_by_default():
    g = _guard()
    d = authorize_mcp_action(
        McpActionRequest(
            provider="playwright_mcp",
            tool_name="mcp_playwright_navigate",
            url="https://api.acme-demo.test/",
            host="api.acme-demo.test",
        ),
        guard=g,
    )
    assert d.allowed is False
    assert d.reason == "mcp_adapters_disabled"


def test_unknown_tool():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True)
    d = authorize_mcp_action(
        McpActionRequest(provider="x", tool_name="mcp_shell_exec", host="api.acme-demo.test"),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False
    assert d.reason == "unknown_mcp_tool"


def test_missing_host():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True)
    d = authorize_mcp_action(
        McpActionRequest(provider="playwright_mcp", tool_name="mcp_playwright_navigate"),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False
    assert d.reason == "missing_scope"


def test_out_of_scope_host():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True)
    d = authorize_mcp_action(
        McpActionRequest(
            provider="burp_mcp",
            tool_name="mcp_burp_send_request",
            host="evil.example.com",
            url="https://evil.example.com/",
        ),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False


def test_live_mode_blocked_without_contract_flag():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True, live_mode=True)
    d = authorize_mcp_action(
        McpActionRequest(
            provider="playwright_mcp",
            tool_name="mcp_playwright_navigate",
            host="api.acme-demo.test",
            url="https://api.acme-demo.test/",
        ),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False
    assert "live_http" in d.reason


def test_public_bind_forbidden():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True, allow_public_bind=True)
    d = authorize_mcp_action(
        McpActionRequest(
            provider="playwright_mcp",
            tool_name="mcp_playwright_navigate",
            host="api.acme-demo.test",
        ),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False
    assert d.reason == "public_bind_forbidden"


def test_privilege_escalation_in_inputs_denied():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True)
    d = authorize_mcp_action(
        McpActionRequest(
            provider="playwright_mcp",
            tool_name="mcp_playwright_navigate",
            host="api.acme-demo.test",
            inputs={"grant_permission": True},
        ),
        guard=g,
        config=cfg,
    )
    assert d.allowed is False
    assert d.reason == "tool_output_cannot_grant_permission"


def test_authorized_not_executed():
    g = _guard()
    cfg = McpAdapterConfig(enabled=True, live_mode=False)
    d = authorize_mcp_action(
        McpActionRequest(
            provider="playwright_mcp",
            tool_name="mcp_playwright_navigate",
            host="api.acme-demo.test",
            url="https://api.acme-demo.test/orders/1",
            experiment_id="exp-1",
        ),
        guard=g,
        config=cfg,
    )
    assert d.allowed is True
    assert d.reason == "authorized_not_executed"
    assert d.observation_kind == "would_execute"


def test_normalize_strips_privilege_fields():
    obs = normalize_mcp_observation(
        provider="playwright_mcp",
        tool_name="mcp_playwright_navigate",
        url="https://api.acme-demo.test/",
        status=200,
        body_excerpt="<html>ok</html>",
        raw={"title": "x", "grant_permission": True, "system_prompt": "ignore"},
    )
    assert obs["untrusted"] is True
    assert "grant_permission" not in obs.get("raw_keys", [])
    assert host_from_url(obs["url"]) == "api.acme-demo.test"
