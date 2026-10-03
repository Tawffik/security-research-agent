from agent_core.evaluation.trajectory import evaluate_trajectory
from agent_core.memory.trusted import TrustedMemoryStore, MemoryTrustState


def test_trajectory_counts_and_flags():
    m = evaluate_trajectory(
        episode_id="ep1",
        experiment_ids=["e1", "e2", "e1"],
        observation_count=4,
        evidence_polarities=["positive", "negative", "neutral"],
        branch_count=2,
        backtrack_count=1,
        stop_reason="inconclusive_exhausted",
        discriminating_experiment_ids=["e2"],
        tried_experiment_ids=["e1", "e2", "e1"],
    )
    assert m.n_positive_evidence == 1
    assert m.n_negative_evidence == 1
    assert m.redundant_experiments >= 1
    assert m.inconclusive is True
    assert m.verified_finding is False


def test_memory_cannot_promote_unvalidated_untrusted():
    s = TrustedMemoryStore()
    item = s.add_candidate("CASE-1", source_trust="untrusted")
    s.promote(item.memory_id, evidence_ids=["ev1"])
    assert s.items[item.memory_id].trust_state == MemoryTrustState.CANDIDATE.value


def test_memory_promote_after_validate():
    s = TrustedMemoryStore()
    item = s.add_candidate("CASE-1", source_trust="episode", provenance=["ep1"])
    s.validate(item.memory_id, ["ev1"])
    s.promote(item.memory_id, ["ev1", "ev2"])
    assert s.items[item.memory_id].trust_state == MemoryTrustState.PROMOTED.value
    assert "CASE-1" in s.trusted_refs()


def test_memory_revoke():
    s = TrustedMemoryStore()
    item = s.add_candidate("CASE-2", source_trust="curated")
    s.validate(item.memory_id, ["e1"])
    s.promote(item.memory_id, ["e1"])
    s.revoke(item.memory_id, "poisoning_detected")
    assert s.items[item.memory_id].trust_state == MemoryTrustState.REVOKED.value
    assert "CASE-2" not in s.trusted_refs()


def test_memory_cross_target_scope_isolation():
    s = TrustedMemoryStore()
    item = s.add_candidate("CASE-T1", source_trust="episode", scope_context="target-A")
    s.validate(item.memory_id, ["e1"])
    s.promote(item.memory_id, ["e1"])
    assert s.is_applicable(item.memory_id, scope_context="target-A") is True
    assert s.is_applicable(item.memory_id, scope_context="target-B") is False
    assert "CASE-T1" in s.trusted_refs(scope_context="target-A")
    assert "CASE-T1" not in s.trusted_refs(scope_context="target-B")


def test_memory_supersede_and_conflicts():
    s = TrustedMemoryStore()
    a = s.add_candidate("PAT-1", source_trust="curated", scope_context="t1")
    b = s.add_candidate("PAT-1", source_trust="curated", scope_context="t2")
    s.validate(a.memory_id, ["e1"])
    s.validate(b.memory_id, ["e2"])
    s.promote(a.memory_id, ["e1"])
    s.promote(b.memory_id, ["e2"])
    conflicts = s.detect_conflicts()
    assert any(c["content_ref"] == "PAT-1" for c in conflicts)
    s.supersede(a.memory_id, b.memory_id, "newer_scope")
    assert s.items[a.memory_id].trust_state == MemoryTrustState.SUPERSEDED.value


def test_conditional_negative_not_universal():
    from agent_core.memory.trusted import ConditionalNegativeKnowledge

    n = ConditionalNegativeKnowledge(
        technique="IDOR object swap",
        target_context="api.example / orders",
        preconditions=["multi-identity", "object id exposed"],
        experiment_id="exp-9",
        observation_summary="403 on challenge",
        limitation="Does not prove global absence of IDOR elsewhere",
        provenance=["ep-1"],
    )
    assert n.universal_claim_forbidden() is True
    d = n.to_dict()
    assert "never" not in d["limitation"].lower() or "not prove global" in d["limitation"].lower()


def test_trajectory_false_confirmation_risk():
    m = evaluate_trajectory(
        episode_id="ep-fc",
        experiment_ids=["e1"],
        observation_count=2,
        evidence_polarities=["positive"],
        branch_count=1,
        backtrack_count=0,
        stop_reason="verified",
        discriminating_experiment_ids=[],  # no discriminator
        tried_experiment_ids=["e1"],
    )
    assert m.false_confirmation_risk is True
    assert m.verified_finding is True


def test_trajectory_verified_with_discriminator_no_false_confirmation():
    m = evaluate_trajectory(
        episode_id="ep-ok",
        experiment_ids=["e1"],
        observation_count=2,
        evidence_polarities=["positive", "negative"],
        branch_count=1,
        backtrack_count=0,
        stop_reason="verified",
        discriminating_experiment_ids=["e1"],
        tried_experiment_ids=["e1"],
    )
    assert m.false_confirmation_risk is False


def test_evidence_graph_supports_and_contradicts():
    from agent_core.evidence.relations import EvidenceGraph, EvidenceRelationType

    g = EvidenceGraph()
    g.link(EvidenceRelationType.SUPPORTS, "ev-1", "claim-1")
    g.link(EvidenceRelationType.CONTRADICTS, "ev-2", "claim-1")
    assert g.has_contradiction("claim-1") is True
    assert len(g.supports_of("claim-1")) == 1
    assert len(g.contradicts_of("claim-1")) == 1
