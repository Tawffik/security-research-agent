from agent_core.memory.origin import MemoryOriginChain, SourceTrustClass, detect_laundering
from agent_core.memory.trusted import TrustedMemoryStore


def test_summary_laundering_detected():
    o = MemoryOriginChain(
        source_identity="target-body",
        source_trust_class=SourceTrustClass.TARGET_ORIGIN,
        derivation_channel="summary",
        content_hash="abc",
    )
    assert o.is_laundering_risk() is True
    assert o.may_auto_promote() is False
    v = detect_laundering(o, claimed_trust="trusted")
    assert "summary_or_echo_laundering" in v


def test_tool_echo_laundering():
    o = MemoryOriginChain(
        source_identity="http_tool",
        source_trust_class=SourceTrustClass.TOOL_ECHO,
        derivation_channel="tool_echo",
    )
    v = detect_laundering(o, claimed_trust="promoted")
    assert "trusted_tool_echo_laundering" in v or "summary_or_echo_laundering" in v


def test_curated_with_evidence_not_laundering():
    o = MemoryOriginChain(
        source_identity="knowledge/CASE-1",
        source_trust_class=SourceTrustClass.CURATED,
        derivation_channel="direct",
        parent_evidence_refs=["ev1"],
    )
    assert o.may_auto_promote() is True
    assert detect_laundering(o, claimed_trust="trusted") == []


def test_store_rejects_promote_without_validation_still():
    s = TrustedMemoryStore()
    item = s.add_candidate("x", source_trust="untrusted")
    s.promote(item.memory_id, ["e1"])
    assert s.items[item.memory_id].trust_state == "candidate"
