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
