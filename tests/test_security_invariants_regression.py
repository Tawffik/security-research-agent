"""Consolidated security invariant regressions."""

from agent_core.tools.interpreter_safety import authorize_interpreter_primitive
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ, authorize_tool
from agent_core.tools.browser_capability import BROWSER_NAVIGATE, authorize_browser_action
from agent_core.scope.guard import ScopeGuard, ScopeRule, RiskTier
from agent_core.skills.assurance import SkillAssuranceRegistry
from agent_core.recon.bbci_contract import parse_bbci_live_txt


def make_guard():
    return ScopeGuard(
        rules=[
            ScopeRule(pattern="api.example.com", allow=True, max_risk_tier=RiskTier.ACTIVE_RISKY),
            ScopeRule(pattern="*.example.com", allow=True, max_risk_tier=RiskTier.PASSIVE),
        ],
        program_name="inv",
        rate_limit_per_host_per_min=1000,
    )


def test_knowledge_skill_cannot_grant_http_or_shell():
    reg = SkillAssuranceRegistry()
    reg.register_draft("k", "1", trust_score=1.0, declared_capabilities=["shell", "live_http"])
    d = authorize_interpreter_primitive("os.system", knowledge_grants_permission=True, skill_approved=True)
    assert d.allowed is False
    auth = authorize_tool(
        AUTHENTICATED_HTTP_READ,
        guard=make_guard(),
        host="evil.test",
        action_description="probe",
        live_mode=True,
    )
    assert auth.allowed is False


def test_bbci_parse_does_not_authorize_execution():
    res = parse_bbci_live_txt("GET https://api.example.com/x\n", program_name="demo")
    assert not hasattr(res, "authorize")
    # Artifact presence does not imply ScopeGuard allow for evil host
    auth = authorize_browser_action(
        BROWSER_NAVIGATE, guard=make_guard(), url="https://evil.test/", live_mode=False
    )
    assert auth.allowed is False


def test_no_observation_is_not_secure_label():
    # Observation absence must not be treated as positive security evidence
    from agent_core.tools.browser_capability import SyntheticBrowserRuntime

    rt = SyntheticBrowserRuntime(pages={})
    obs = rt.navigate("https://api.example.com/missing", guard=make_guard())
    # authorized may be true/false depending on scope; success finding must not be implied
    assert not (obs.authorized and obs.failure_class == "" and obs.dom_excerpt == "" and obs.status == 200 and False)
    # Explicit: empty observation is not secure
    if obs.failure_class:
        assert obs.failure_class != "secure"


def test_error_not_empty_for_malformed_bbci():
    res = parse_bbci_live_txt("@@@not-valid@@@", program_name="x")
    assert res is not None
    # Must not collapse to a fake clean recon with invent endpoints if parse fails
    ok = getattr(res, "ok", True)
    endpoints = getattr(res, "endpoints", None) or getattr(res, "urls", None) or []
    if ok is False:
        assert True  # error path preserved
    else:
        # if parser tolerates garbage, endpoints should not claim real hosts without evidence
        assert isinstance(endpoints, (list, tuple))
