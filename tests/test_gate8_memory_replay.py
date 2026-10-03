"""Gate 8 memory replay validation."""

from agent_core.memory.replay_validate import simulate_checkpoint_resume, validate_memory_replay
from agent_core.memory.trusted import TrustedMemoryStore, MemoryTrustState


def test_replay_preserves_promoted_and_blocks_untrusted():
    s = TrustedMemoryStore()
    good = s.add_candidate("CASE-OK", source_trust="episode", scope_context="target-A", provenance=["ep1"])
    s.validate(good.memory_id, ["e1"])
    s.promote(good.memory_id, ["e1", "e2"])
    bad = s.add_candidate("CASE-POISON", source_trust="untrusted", scope_context="target-A")
    s.promote(bad.memory_id, ["e1"])  # should stay candidate
    assert s.items[bad.memory_id].trust_state == MemoryTrustState.CANDIDATE.value

    restored = simulate_checkpoint_resume(s)
    report = validate_memory_replay(restored, scope_context="target-A")
    assert report.ok is True
    assert "CASE-OK" in restored.trusted_refs(scope_context="target-A")
    assert "CASE-POISON" not in restored.trusted_refs()


def test_replay_cross_target_and_revoked():
    s = TrustedMemoryStore()
    a = s.add_candidate("PAT-X", source_trust="curated", scope_context="target-A", provenance=["p"])
    s.validate(a.memory_id, ["e1"])
    s.promote(a.memory_id, ["e1"])
    s.revoke(a.memory_id, "stale")
    restored = simulate_checkpoint_resume(s)
    report = validate_memory_replay(restored, scope_context="target-B")
    assert report.ok is True
    assert restored.is_applicable(a.memory_id, scope_context="target-A") is False
    assert restored.is_applicable(a.memory_id, scope_context="target-B") is False


def test_memory_cannot_encode_execution_permission():
    s = TrustedMemoryStore()
    item = s.add_candidate("execution_permission_grant", source_trust="episode", provenance=["x"])
    s.validate(item.memory_id, ["e1"])
    s.promote(item.memory_id, ["e1"])
    report = validate_memory_replay(s, scope_context="")
    assert report.ok is False
    assert any("execution" in f for f in report.failures)
