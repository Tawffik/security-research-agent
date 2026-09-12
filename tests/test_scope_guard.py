import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.scope.guard import ScopeGuard, ScopeRule, RiskTier, Decision


def make_guard():
    rules = [
        ScopeRule(pattern="api.example.com", allow=True, max_risk_tier=RiskTier.ACTIVE_RISKY),
        ScopeRule(pattern="*.example.com", allow=True, max_risk_tier=RiskTier.PASSIVE),
        ScopeRule(pattern="billing.example.com", allow=False),
    ]
    return ScopeGuard(rules=rules, program_name="test-program", rate_limit_per_host_per_min=1000)


def test_out_of_scope_host_denied():
    guard = make_guard()
    assert guard.authorize(host="totally-unrelated.com") == Decision.DENY


def test_explicit_exclusion_beats_wildcard_allow():
    guard = make_guard()
    # billing.example.com matches both the wildcard *.example.com (allow)
    # and the explicit exclusion — exclusion must win.
    assert guard.authorize(host="billing.example.com", risk_tier=RiskTier.PASSIVE) == Decision.DENY


def test_risk_tier_within_scope_allowed():
    guard = make_guard()
    assert guard.authorize(host="api.example.com", risk_tier=RiskTier.ACTIVE_RISKY) == Decision.ALLOW


def test_risk_tier_exceeding_scope_requires_approval():
    guard = make_guard()
    # www.example.com only matches the PASSIVE-only wildcard rule
    decision = guard.authorize(host="www.example.com", risk_tier=RiskTier.DESTRUCTIVE)
    assert decision == Decision.REQUIRES_APPROVAL


def test_approval_token_unlocks_higher_risk():
    guard = make_guard()
    token = guard.grant_approval(
        granted_by="human-lead",
        reason="program explicitly approved a rate-limit stress test",
        action_pattern="destructive:www.example.com:*",
    )
    decision = guard.authorize(
        host="www.example.com",
        risk_tier=RiskTier.DESTRUCTIVE,
        action_description="destructive:www.example.com:rate-limit-probe",
        approval_token=token.token_id,
    )
    assert decision == Decision.ALLOW


def test_rate_limit_enforced():
    rules = [ScopeRule(pattern="api.example.com", allow=True, max_risk_tier=RiskTier.ACTIVE_SAFE)]
    guard = ScopeGuard(rules=rules, program_name="rl-test", rate_limit_per_host_per_min=2)
    assert guard.authorize(host="api.example.com") == Decision.ALLOW
    assert guard.authorize(host="api.example.com") == Decision.ALLOW
    assert guard.authorize(host="api.example.com") == Decision.DENY  # 3rd hit within the minute
