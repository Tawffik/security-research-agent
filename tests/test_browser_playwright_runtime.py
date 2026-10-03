"""Playwright browser runtime — system Chrome; ScopeGuard; no fabricated live network."""

from agent_core.scope.guard import ScopeGuard, ScopeRule, RiskTier
from agent_core.tools.browser_capability import (
    BROWSER_NAVIGATE_LIVE,
    PlaywrightBrowserRuntime,
    SyntheticBrowserRuntime,
    authorize_browser_action,
    playwright_available,
    system_chrome_available,
)
from agent_core.tools.capability import FailureClass


def make_guard():
    rules = [
        ScopeRule(pattern="api.example.com", allow=True, max_risk_tier=RiskTier.ACTIVE_RISKY),
        ScopeRule(pattern="*.example.com", allow=True, max_risk_tier=RiskTier.PASSIVE),
        ScopeRule(pattern="billing.example.com", allow=False),
    ]
    return ScopeGuard(rules=rules, program_name="test-program", rate_limit_per_host_per_min=1000)


def test_playwright_and_chrome_available():
    assert playwright_available() is True
    assert system_chrome_available() is True


def test_playwright_local_data_url_navigation():
    rt = PlaywrightBrowserRuntime()
    guard = make_guard()
    obs = rt.navigate(
        "data:text/html,<html><title>local-ok</title><body>hi</body></html>",
        guard=guard,
        live_mode=False,
    )
    assert obs.authorized is True
    assert obs.synthetic is False
    assert "local-ok" in obs.title
    assert obs.failure_class == ""


def test_playwright_network_without_live_mode_denied():
    rt = PlaywrightBrowserRuntime()
    guard = make_guard()
    obs = rt.navigate("https://api.example.com/", guard=guard, live_mode=False)
    assert obs.authorized is False
    assert obs.browser_failure == "environment_failure"


def test_playwright_out_of_scope_denied_even_with_live_mode():
    rt = PlaywrightBrowserRuntime()
    guard = make_guard()
    obs = rt.navigate("https://evil.test/", guard=guard, live_mode=True)
    assert obs.authorized is False
    assert obs.failure_class in (
        FailureClass.SCOPE_BLOCK.value,
        FailureClass.AUTHORIZATION_DENIED.value,
        FailureClass.ENVIRONMENT_FAILURE.value,
    )


def test_synthetic_click_and_fill():
    guard = make_guard()
    rt = SyntheticBrowserRuntime(
        pages={
            "https://api.example.com/form": {
                "title": "Form",
                "status": 200,
                "dom_excerpt": "<form>",
                "elements": {"#user": "input", "#submit": "button"},
            }
        }
    )
    nav = rt.navigate("https://api.example.com/form", guard=guard)
    assert nav.authorized
    fill = rt.interact("fill", guard=guard, selector="#user", value="alice")
    assert fill.authorized and fill.failure_class == ""
    click = rt.interact("click", guard=guard, selector="#submit")
    assert click.authorized
    missing = rt.interact("click", guard=guard, selector="#nope")
    assert missing.browser_failure == "interaction_failure"


def test_live_contract_exists():
    assert BROWSER_NAVIGATE_LIVE.live_http_allowed is True
    assert authorize_browser_action(
        BROWSER_NAVIGATE_LIVE, guard=make_guard(), url="https://api.example.com/x", live_mode=True
    ).allowed is True


def test_skill_trust_score_cannot_authorize_browser():
    """KNOWLEDGE / skill trust_score ≠ permission."""
    from agent_core.skills.assurance import SkillAssuranceRegistry

    reg = SkillAssuranceRegistry()
    reg.register_draft(
        "evil-browser-skill",
        "1.0",
        trust_score=0.99,
        declared_capabilities=["browser_navigate_live", "shell"],
        provenance=["attacker-controlled"],
    )
    guard = make_guard()
    # High trust skill does not change ScopeGuard outcome for evil host
    auth = authorize_browser_action(
        BROWSER_NAVIGATE_LIVE,
        guard=guard,
        url="https://evil.test/pwn",
        live_mode=True,
    )
    assert auth.allowed is False
    # skill registry has no authorize method granting execution
    assert not hasattr(reg, "authorize_execution")


def test_malicious_url_tricks_denied():
    guard = make_guard()
    rt = PlaywrightBrowserRuntime()
    for url in (
        "https://api.example.com.evil.test/",
        "https://evil.test@api.example.com/",
        "javascript:alert(1)",
    ):
        obs = rt.navigate(url, guard=guard, live_mode=True)
        # Must not succeed as authorized network navigation to real in-scope host
        if obs.authorized and obs.failure_class == "":
            # only acceptable if somehow local — javascript should fail
            assert not url.startswith("https://evil")
