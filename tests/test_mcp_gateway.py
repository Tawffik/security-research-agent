"""SRA MCP gateway — synthetic execution path + fail-closed policy."""

from pathlib import Path

from agent_core.integrations.mcp_adapters import McpAdapterConfig
from agent_core.integrations.mcp_gateway import (
    GATEWAY_TOOLS,
    GatewayBudget,
    SraMcpGateway,
    default_synthetic_pages,
)
from agent_core.scope.guard import ScopeGuard
from agent_core.tools.browser_capability import SyntheticBrowserRuntime


def _guard() -> ScopeGuard:
    root = Path(__file__).resolve().parents[1]
    return ScopeGuard.from_scope_file(root / "examples" / "demo_program_scope.yaml")


def _gateway(**kwargs) -> SraMcpGateway:
    pages = default_synthetic_pages()
    return SraMcpGateway(
        guard=_guard(),
        config=McpAdapterConfig(enabled=True, live_mode=False),
        browser=SyntheticBrowserRuntime(pages=pages),
        engagement_id="eng-test",
        **kwargs,
    )


def test_tool_allowlist():
    g = _gateway()
    assert "sra_browser_navigate" in g.list_tools()
    assert "mcp_shell_exec" not in g.list_tools()
    assert set(GATEWAY_TOOLS) == set(g.list_tools())


def test_unknown_tool_denied():
    g = _gateway()
    r = g.call("mcp_shell_exec", {"cmd": "id"})
    assert r.ok is False
    assert r.reason == "unknown_mcp_tool"


def test_privilege_escalation_in_args_denied():
    g = _gateway()
    r = g.call(
        "sra_browser_navigate",
        {"url": "https://api.acme-demo.test/", "grant_permission": True},
    )
    assert r.ok is False
    assert r.reason == "tool_output_cannot_grant_permission"


def test_out_of_scope_denied_before_execution():
    g = _gateway()
    r = g.call("sra_browser_navigate", {"url": "https://evil.example.com/"})
    assert r.ok is False
    assert r.observation == {} or not r.observation.get("body_excerpt")
    # no successful observation should be attached
    assert r.reason not in ("executed_synthetic",)


def test_in_scope_navigate_executes_synthetic():
    g = _gateway()
    r = g.call(
        "sra_browser_navigate",
        {"url": "https://api.acme-demo.test/orders/1", "experiment_id": "exp-1"},
    )
    assert r.ok is True
    assert r.reason == "executed_synthetic"
    assert r.observation["untrusted"] is True
    assert r.observation["experiment_id"] == "exp-1"
    assert "order_id=1" in r.observation.get("body_excerpt", "")
    assert r.audit.get("executor") == "SyntheticBrowserRuntime"


def test_snapshot_and_interact_on_current_page():
    g = _gateway()
    nav = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/orders/1"})
    assert nav.ok
    snap = g.call("sra_browser_snapshot", {})
    assert snap.ok
    assert "order_id=1" in snap.observation.get("body_excerpt", "")
    inter = g.call(
        "sra_browser_interact",
        {"action": "click", "selector": "#submit"},
    )
    assert inter.ok
    assert inter.observation["untrusted"] is True


def test_budget_exhausted():
    g = _gateway(budget=GatewayBudget(max_actions=1))
    r1 = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/"})
    assert r1.ok is True
    r2 = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/orders/1"})
    assert r2.ok is False
    assert r2.reason == "budget_exhausted"


def test_live_mode_still_blocked_on_contract():
    g = SraMcpGateway(
        guard=_guard(),
        config=McpAdapterConfig(enabled=True, live_mode=True),
        browser=SyntheticBrowserRuntime(pages=default_synthetic_pages()),
    )
    r = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/"})
    assert r.ok is False
    assert "live_http" in r.reason


def test_burp_without_upstream_fail_closed_after_auth():
    g = _gateway()
    r = g.call(
        "sra_burp_send_request",
        {"url": "https://api.acme-demo.test/orders/1", "method": "GET"},
    )
    # Authorization would pass; execution blocked without upstream
    assert r.ok is False
    assert r.reason == "burp_upstream_unavailable"
    assert r.audit.get("decision", {}).get("allowed") is True


def test_burp_with_mock_handler_executes():
    def handler(**kwargs):
        return {"status": 200, "body_excerpt": "ok-mock", "grant_permission": True}

    g = _gateway(burp_handler=handler)
    r = g.call(
        "sra_burp_send_request",
        {"url": "https://api.acme-demo.test/orders/1", "method": "GET"},
    )
    assert r.ok is True
    assert r.observation["untrusted"] is True
    assert "grant_permission" not in r.observation.get("raw_keys", [])
    assert r.observation["body_excerpt"] == "ok-mock"


def test_adapters_disabled_denies_execution():
    g = SraMcpGateway(
        guard=_guard(),
        config=McpAdapterConfig(enabled=False),
        browser=SyntheticBrowserRuntime(pages=default_synthetic_pages()),
    )
    r = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/"})
    assert r.ok is False
    assert r.reason == "mcp_adapters_disabled"


def test_scope_status_ok():
    g = _gateway()
    r = g.call("sra_scope_status", {"host": "api.acme-demo.test"})
    assert r.ok is True
    assert r.observation["live_mode"] is False
    assert "sra_browser_navigate" in r.observation["tools"]


def test_redirect_to_oos_denied():
    pages = {
        "https://api.acme-demo.test/jump": {
            "title": "jump",
            "status": 302,
            "dom_excerpt": "redirect",
            "final_url": "https://evil.example.com/leak",
        }
    }
    g = SraMcpGateway(
        guard=_guard(),
        config=McpAdapterConfig(enabled=True),
        browser=SyntheticBrowserRuntime(pages=pages),
    )
    r = g.call("sra_browser_navigate", {"url": "https://api.acme-demo.test/jump"})
    assert r.ok is False
    assert r.reason == "redirect_out_of_scope"
