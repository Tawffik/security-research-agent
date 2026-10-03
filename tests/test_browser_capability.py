"""Browser capability — ScopeGuard + Tool Contract; synthetic offline runtime."""

from agent_core.scope.guard import ScopeGuard, ScopeRule, RiskTier, Decision
from agent_core.tools.browser_capability import (
    BROWSER_NAVIGATE,
    SyntheticBrowserRuntime,
    authorize_browser_action,
    host_from_url,
    playwright_available,
)
from agent_core.tools.capability import FailureClass
from agent_core.tools.failure_policy import next_action_for_failure


def make_guard():
    rules = [
        ScopeRule(pattern="api.example.com", allow=True, max_risk_tier=RiskTier.ACTIVE_RISKY),
        ScopeRule(pattern="*.example.com", allow=True, max_risk_tier=RiskTier.PASSIVE),
        ScopeRule(pattern="billing.example.com", allow=False),
    ]
    return ScopeGuard(rules=rules, program_name="test-program", rate_limit_per_host_per_min=1000)


def test_playwright_availability_is_reported_not_assumed():
    assert isinstance(playwright_available(), bool)


def test_out_of_scope_navigation_denied():
    guard = make_guard()
    auth = authorize_browser_action(
        BROWSER_NAVIGATE, guard=guard, url="https://evil.example/admin"
    )
    assert auth.allowed is False


def test_live_mode_blocked_when_contract_disallows_live():
    guard = make_guard()
    auth = authorize_browser_action(
        BROWSER_NAVIGATE,
        guard=guard,
        url="https://api.example.com/x",
        live_mode=True,
    )
    assert auth.allowed is False
    assert "live_http" in auth.reason


def test_synthetic_navigate_in_scope_fixture():
    guard = make_guard()
    runtime = SyntheticBrowserRuntime(
        pages={
            "https://api.example.com/app": {
                "title": "App",
                "status": 200,
                "dom_excerpt": "<div id=user>me</div>",
            }
        }
    )
    obs = runtime.navigate("https://api.example.com/app", guard=guard, live_mode=False)
    assert obs.authorized is True
    assert obs.synthetic is True
    assert obs.title == "App"
    assert obs.failure_class == ""


def test_synthetic_out_of_scope_does_not_produce_finding_like_success():
    guard = make_guard()
    runtime = SyntheticBrowserRuntime(pages={"https://evil.test/": {"title": "x", "status": 200}})
    obs = runtime.navigate("https://evil.test/", guard=guard)
    assert obs.authorized is False
    assert obs.error
    assert obs.failure_class
    assert next_action_for_failure(obs.failure_class) in (
        "block", "defer", "try_alternative", "stop", "backtrack", "fix_precondition"
    )


def test_host_from_url():
    assert host_from_url("https://A.Example.COM/path") == "a.example.com"
    assert host_from_url("not-a-url") == ""


def test_browser_cannot_bypass_with_empty_url():
    guard = make_guard()
    auth = authorize_browser_action(BROWSER_NAVIGATE, guard=guard, url="")
    assert auth.allowed is False


def test_billing_exclusion_beats_wildcard():
    guard = make_guard()
    auth = authorize_browser_action(
        BROWSER_NAVIGATE, guard=guard, url="https://billing.example.com/pay"
    )
    assert auth.allowed is False
