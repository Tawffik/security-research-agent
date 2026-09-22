"""Contract tests for canonical V2 schemas (Sprint 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_core.schemas import (
    Actor,
    Belief,
    Decision,
    DecisionAction,
    Engagement,
    EngagementMode,
    Experiment,
    Finding,
    FindingStatus,
    Hypothesis,
    Opportunity,
    Priority,
    Resource,
    TargetContext,
    Unknown,
)
from agent_core.schemas.engagement import Authorization, Budget, RiskPolicy, RiskTierName


def test_engagement_roundtrip():
    eng = Engagement(
        engagement_id="eng_2026_001",
        program="acme-demo",
        mode=EngagementMode.AUTHORIZED,
        scope=Authorization(
            program_name="acme-demo-2026",
            in_scope_patterns=["api.acme-demo.test"],
            max_risk_tier=RiskTierName.ACTIVE_RISKY,
        ),
        identities=["user_a", "user_b"],
        budget=Budget(token_budget=10_000, tool_call_budget=50),
        risk_policy=RiskPolicy(allow_destructive=False),
    )
    data = eng.model_dump()
    restored = Engagement.model_validate(data)
    assert restored.engagement_id == "eng_2026_001"
    assert restored.scope.max_risk_tier == RiskTierName.ACTIVE_RISKY
    assert restored.budget.token_budget == 10_000


def test_engagement_rejects_empty_id():
    with pytest.raises(ValidationError):
        Engagement(
            engagement_id="  ",
            program="x",
            scope=Authorization(program_name="x"),
        )


def test_opportunity_bounds():
    opp = Opportunity(
        opportunity_id="opp_12",
        type="authorization",
        target="/api/orders/{id}",
        identity_surface=True,
        object_surface=True,
        stateful=True,
        mutation=True,
        priority=Priority.HIGH,
        novelty=0.8,
    )
    assert opp.priority == Priority.HIGH
    with pytest.raises(ValidationError):
        Opportunity(
            opportunity_id="bad",
            type="x",
            target="y",
            novelty=1.5,  # out of range
        )


def test_unknown_and_belief():
    u = Unknown(
        unknown_id="U1",
        question="Does user B own object 123?",
        why_it_matters="Affects ownership-bypass hypothesis",
        confidence=0.2,
    )
    b = Belief(
        belief_id="B-017",
        claim="Object authorization appears ownership-bound.",
        confidence=0.71,
        supporting_evidence_ids=["E12", "E17"],
        contradicting_evidence_ids=["E22"],
    )
    assert u.unknown_id == "U1"
    assert b.confidence == 0.71


def test_hypothesis_with_alternatives():
    h = Hypothesis(
        hypothesis_id="H1",
        statement="Ownership bypass possible on /api/orders/{id}",
        primary_explanation="Authorization missing",
        confidence=0.62,
        alternatives=[
            {"explanation_id": "A1", "description": "resource shared"},
            {"explanation_id": "A2", "description": "role grants access"},
        ],
    )
    assert len(h.alternatives) == 2
    assert h.status.value == "open"


def test_experiment_and_decision():
    exp = Experiment(
        experiment_id="experiment_17",
        hypothesis_id="H1",
        description="Cross-identity access to order 123",
        expected_observation="403 for user B",
        discriminator="status + body ownership marker",
        information_gain=0.85,
        risk=0.2,
        cost=0.15,
    )
    dec = Decision(
        decision_id="d1",
        decision=DecisionAction.EXECUTE,
        candidate="experiment_17",
        confidence=0.84,
        reason_codes=["HIGH_INFORMATION_GAIN", "LOW_COST", "LOW_RISK"],
        experiment_id="experiment_17",
        hypothesis_id="H1",
    )
    assert dec.decision == DecisionAction.EXECUTE
    assert exp.information_gain == 0.85


def test_finding_lifecycle_fields():
    f = Finding(
        finding_id="F1",
        title="IDOR on order resource",
        claim="User B accessed User A order",
        status=FindingStatus.CANDIDATE,
        scope_valid=True,
        skeptic_disproof_attempted=False,
        reproducible=False,
    )
    assert f.status == FindingStatus.CANDIDATE
    # CONFIRMED requires more than status alone — callers must set flags
    f2 = f.model_copy(
        update={
            "status": FindingStatus.CONFIRMED,
            "skeptic_disproof_attempted": True,
            "reproducible": True,
        }
    )
    assert f2.skeptic_disproof_attempted is True


def test_target_context():
    ctx = TargetContext(
        engagement_id="eng_2026_001",
        primary_host="api.acme-demo.test",
        technologies=["rest", "jwt"],
        actors=[Actor(actor_id="a1", name="user_a")],
        resources=[Resource(resource_id="r1", name="order-123")],
    )
    assert len(ctx.actors) == 1
    assert ctx.resources[0].resource_id == "r1"


def test_json_schema_exportable():
    """Schemas must be JSON-serializable for artifact validation."""
    eng = Engagement(
        engagement_id="eng_x",
        program="p",
        scope=Authorization(program_name="p"),
    )
    payload = eng.model_dump_json()
    assert "eng_x" in payload
    Engagement.model_validate_json(payload)
