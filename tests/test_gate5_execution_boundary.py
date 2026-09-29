"""Gate 5.1 — Tool Contract + Authorized Execution Boundary (fail-closed)."""

from pathlib import Path

from agent_core.scope.guard import ScopeGuard
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ, ToolContract, authorize_tool
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def _boundary() -> ExecutionBoundary:
    guard = ScopeGuard.from_scope_file(SCOPE)
    b = ExecutionBoundary(guard=guard)
    b.register(AUTHENTICATED_HTTP_READ)
    return b


def test_authorized_action_accepted():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="api.acme-demo.test",
            purpose="lab read",
            experiment_id="exp-1",
            live_mode=False,
        )
    )
    assert d.allowed is True
    assert d.reason == "authorized"
    assert d.authorization_decision == "allow"
    assert d.request_id


def test_missing_authorization_host_denied():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(tool_name="authenticated_http_request", host="", experiment_id="exp-1")
    )
    assert d.allowed is False
    assert d.reason == "missing_scope"


def test_missing_scope_out_of_program_denied():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="not-in-program.example",
            experiment_id="exp-1",
        )
    )
    assert d.allowed is False
    assert "scope" in d.reason or d.reason == "scope_deny"


def test_ambiguous_authorization_requires_approval_denied():
    """High risk without approval token → DENY (not implicit allow)."""
    b = _boundary()
    risky = ToolContract(
        name="risky_write",
        purpose="write",
        side_effects="write",
        authorization_required=True,
        live_http_allowed=False,
    )
    b.register(risky)
    d = b.request_execution(
        ActionRequest(
            tool_name="risky_write",
            host="api.acme-demo.test",
            risk_tier="destructive",
            experiment_id="exp-1",
        )
    )
    assert d.allowed is False
    assert d.reason in ("ambiguous_authorization", "scope_deny", "scope_requires_approval")


def test_unknown_action_denied():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(tool_name="nonexistent_tool_xyz", host="api.acme-demo.test")
    )
    assert d.allowed is False
    assert d.reason == "unknown_action"


def test_invalid_empty_tool_denied():
    b = _boundary()
    d = b.request_execution(ActionRequest(tool_name="", host="api.acme-demo.test"))
    assert d.allowed is False
    assert d.reason == "unknown_action"


def test_denial_is_auditable():
    b = _boundary()
    b.request_execution(
        ActionRequest(tool_name="unknown", host="api.acme-demo.test", experiment_id="e9")
    )
    assert len(b.audit_log) >= 1
    last = b.audit_log[-1]
    assert last.allowed is False
    assert last.audit.get("decision") == "DENY"
    assert last.audit.get("request", {}).get("experiment_id") == "e9"


def test_authorization_preserves_provenance():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="api.acme-demo.test",
            experiment_id="exp-42",
            hypothesis_id="hyp-7",
            engagement_id="eng-1",
        )
    )
    assert d.allowed is True
    assert d.experiment_id == "exp-42"
    assert d.hypothesis_id == "hyp-7"
    assert d.audit["request"]["experiment_id"] == "exp-42"


def test_experiment_exists_does_not_bypass_boundary():
    """Research logic cannot execute by only setting experiment_id."""
    b = _boundary()
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="",  # missing scope
            experiment_id="I-exist-therefore-execute",
            hypothesis_id="also-exists",
        )
    )
    assert d.allowed is False
    assert d.reason == "missing_scope"


def test_live_mode_denied_without_contract_flag():
    b = _boundary()
    d = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="api.acme-demo.test",
            live_mode=True,
        )
    )
    assert d.allowed is False
    assert "live_http" in d.reason


def test_authorize_tool_missing_host_denied():
    guard = ScopeGuard.from_scope_file(SCOPE)
    r = authorize_tool(
        AUTHENTICATED_HTTP_READ,
        guard=guard,
        host="",
        action_description="x",
        live_mode=False,
    )
    assert r.allowed is False
    assert r.reason == "missing_scope"
