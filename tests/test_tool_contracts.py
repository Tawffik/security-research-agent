"""M12: Tool contracts fail-closed for live HTTP; ScopeGuard required."""

from pathlib import Path

from agent_core.scope.guard import ScopeGuard
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ, authorize_tool

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_live_mode_blocked_by_default_contract():
    guard = ScopeGuard.from_scope_file(SCOPE)
    r = authorize_tool(
        AUTHENTICATED_HTTP_READ,
        guard=guard,
        host="api.acme-demo.test",
        action_description="GET /api/orders/1",
        live_mode=True,
    )
    assert r.allowed is False
    assert "live_http" in r.reason


def test_lab_mode_scope_allows_in_scope_host():
    guard = ScopeGuard.from_scope_file(SCOPE)
    r = authorize_tool(
        AUTHENTICATED_HTTP_READ,
        guard=guard,
        host="api.acme-demo.test",
        action_description="lab GET",
        live_mode=False,
    )
    assert r.allowed is True


def test_out_of_scope_host_denied():
    guard = ScopeGuard.from_scope_file(SCOPE)
    r = authorize_tool(
        AUTHENTICATED_HTTP_READ,
        guard=guard,
        host="evil.example.com",
        action_description="GET /",
        live_mode=False,
    )
    assert r.allowed is False
