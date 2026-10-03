"""Gate 5.2 — Capability exposure + failure taxonomy."""

from pathlib import Path

from agent_core.scope.guard import ScopeGuard
from agent_core.tools.capability import CapabilityTracker, FailureClass
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_capability_lifecycle_required_available_exposed_used():
    t = CapabilityTracker(engagement_id="e1")
    t.require("authenticated_http_request", experiment_id="exp-1")
    t.mark_available("authenticated_http_request")
    exp = t.mark_exposed("authenticated_http_request")
    assert exp.exposed is True
    used = t.mark_used("authenticated_http_request", outcome="success", request_id="r1")
    assert used.used is True
    assert used.outcome == "success"
    s = t.summary()
    assert "authenticated_http_request" in s["exposed"]


def test_cannot_expose_unavailable_capability():
    t = CapabilityTracker()
    rec = t.mark_exposed("missing_tool")
    assert rec.exposed is False
    assert rec.failure_class == FailureClass.CAPABILITY_NOT_EXPOSED.value
    assert any(f.failure_class == FailureClass.CAPABILITY_NOT_EXPOSED.value for f in t.failures)


def test_boundary_records_capability_on_allow_and_deny():
    guard = ScopeGuard.from_scope_file(SCOPE)
    b = ExecutionBoundary(guard=guard)
    b.register(AUTHENTICATED_HTTP_READ)
    assert "authenticated_http_request" in b.capabilities._available

    ok = b.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host="api.acme-demo.test",
            experiment_id="exp-ok",
        )
    )
    assert ok.allowed is True
    assert any(r.outcome == "success" for r in b.capabilities.records)

    deny = b.request_execution(
        ActionRequest(tool_name="authenticated_http_request", host="", experiment_id="exp-deny")
    )
    assert deny.allowed is False
    assert any(f.failure_class for f in b.capabilities.failures)
    assert FailureClass.SCOPE_BLOCK.value in {f.failure_class for f in b.capabilities.failures} or any(
        f.failure_class == FailureClass.SCOPE_BLOCK.value for f in b.capabilities.failures
    )


def test_unknown_tool_classified_capability_not_exposed():
    guard = ScopeGuard.from_scope_file(SCOPE)
    b = ExecutionBoundary(guard=guard)
    b.register(AUTHENTICATED_HTTP_READ)
    d = b.request_execution(
        ActionRequest(tool_name="no_such_tool", host="api.acme-demo.test")
    )
    assert d.allowed is False
    assert any(
        f.failure_class == FailureClass.CAPABILITY_NOT_EXPOSED.value for f in b.capabilities.failures
    )


def test_failure_taxonomy_values_stable():
    names = {f.value for f in FailureClass}
    assert "scope_block" in names
    assert "capability_not_exposed" in names
    assert "verification_failure" in names
    assert "budget_exhaustion" in names
