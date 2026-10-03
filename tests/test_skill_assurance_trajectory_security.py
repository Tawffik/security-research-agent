from agent_core.skills.assurance import SkillAssuranceRegistry, SkillAssuranceState
from agent_core.evaluation.trajectory_security import analyze_trajectory_security
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ
from agent_core.scope.guard import ScopeGuard
from pathlib import Path

SCOPE = Path(__file__).resolve().parents[1] / "examples" / "demo_program_scope.yaml"


def test_skill_cannot_approve_without_benchmark():
    r = SkillAssuranceRegistry()
    r.register_draft("authz-idor", "1.0.0")
    rec = r.advance("authz-idor", "1.0.0", SkillAssuranceState.APPROVED)
    assert rec.assurance_state == SkillAssuranceState.DRAFT.value


def test_material_update_forces_revalidation():
    r = SkillAssuranceRegistry()
    r.register_draft("authz-idor", "1.0.0")
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.BENCHMARKED, ["bm1"])
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.SECURITY_EVALUATED, ["sec1"])
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.REVIEW)
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.APPROVED, ["bm1"])
    assert r.is_execution_eligible("authz-idor", "1.0.0") is True
    new = r.material_update("authz-idor", "1.0.0", "1.1.0", ["new_cap"])
    assert new.assurance_state == SkillAssuranceState.REVALIDATION.value
    assert r.is_execution_eligible("authz-idor", "1.1.0") is False
    assert r.trust_score_grants_execution("authz-idor", "1.0.0") is False


def test_approved_skill_still_needs_scopeguard():
    r = SkillAssuranceRegistry()
    r.register_draft("authz-idor", "1.0.0")
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.BENCHMARKED, ["bm1"])
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.SECURITY_EVALUATED, ["s1"])
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.REVIEW)
    r.advance("authz-idor", "1.0.0", SkillAssuranceState.APPROVED, ["bm1"])
    assert r.is_execution_eligible("authz-idor", "1.0.0")
    b = ExecutionBoundary(guard=ScopeGuard.from_scope_file(SCOPE))
    b.register(AUTHENTICATED_HTTP_READ)
    d = b.request_execution(ActionRequest(tool_name="authenticated_http_request", host="evil.example"))
    assert d.allowed is False


def test_trajectory_flags_memory_contamination_and_denied_attempts():
    rep = analyze_trajectory_security(
        untrusted_source_ids=["src1"],
        memory_refs_used=["mem1"],
        memory_trust_states={"mem1": "candidate"},
        execution_audit=[{"allowed": False, "decision": "DENY"}, {"allowed": False}],
        capability_differentials=[{"capability_name": "x", "differential": "declared_only"}],
    )
    assert rep.memory_contamination_flags >= 1
    assert rep.denied_action_attempts >= 2
    assert rep.capability_escalation_flags >= 1
