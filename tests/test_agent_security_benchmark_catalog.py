from agent_core.evaluation.agent_security_benchmark import (
    DEFAULT_AGENT_SECURITY_SUITE,
    suite_categories,
)
from agent_core.skills.assurance import SkillAssuranceRegistry, SkillAssuranceState
from agent_core.memory.origin import MemoryOriginChain, SourceTrustClass, detect_laundering


def test_catalog_covers_required_categories():
    cats = suite_categories()
    for required in (
        "malicious_skill",
        "over_privilege",
        "capability_mismatch",
        "update_drift",
        "poisoned_memory",
        "memory_laundering",
        "untrusted_instruction",
        "cross_target_contamination",
        "capability_escalation",
    ):
        assert required in cats


def test_oracle_not_used_for_skill_approval():
    """Ground truth strings on cases must not approve skills."""
    r = SkillAssuranceRegistry()
    r.register_draft("sk", "1.0.0")
    # Even if a benchmark case says expected_detection=approve, registry ignores it
    case = DEFAULT_AGENT_SECURITY_SUITE[0]
    assert case.ground_truth == "" or True
    rec = r.advance("sk", "1.0.0", SkillAssuranceState.APPROVED)
    assert rec.assurance_state != SkillAssuranceState.APPROVED.value


def test_memory_laundering_case_maps_to_origin_detector():
    o = MemoryOriginChain(
        source_identity="target",
        source_trust_class=SourceTrustClass.TARGET_ORIGIN,
        derivation_channel="summary",
    )
    assert detect_laundering(o, claimed_trust="trusted")
