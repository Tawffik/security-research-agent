"""BeliefQuery — first-class belief retrieval (offline)."""

from agent_core.beliefs.engine import BeliefEngine, BeliefQuery, belief_query


def test_claim_substring_and_evidence_link():
    eng = BeliefEngine("bq1")
    b1 = eng.assert_belief("resource is ownership-bound", 0.4, supporting=["e1"], source="lab")
    b2 = eng.assert_belief("resource is public", 0.8, supporting=["e2"], contradicting=["e1"], source="lab")
    q = belief_query(eng)
    assert any(b.belief_id == b1.belief_id for b in q.by_claim_substring("ownership"))
    assert any(b.belief_id == b1.belief_id for b in q.by_evidence_id("e1"))
    assert any(b.belief_id == b2.belief_id for b in q.by_evidence_id("e1"))  # contradicting link
    assert q.by_source("lab")


def test_contradictory_and_snapshot_restore():
    eng = BeliefEngine("bq2")
    eng.assert_belief("same claim", 0.9, supporting=["s1"])
    eng.assert_belief("same claim", 0.2, supporting=["s2"])
    q = BeliefQuery(eng)
    contr = q.contradictory()
    assert len(contr) >= 1
    snap = q.snapshot()
    restored = BeliefQuery.restore(snap)
    assert len(restored.list_all()) == 2
    assert BeliefQuery(restored).by_claim_substring("same")


def test_belief_query_does_not_authorize():
    eng = BeliefEngine("bq3")
    eng.assert_belief("may execute shell", 0.99, source="untrusted")
    q = belief_query(eng)
    assert not hasattr(q, "authorize")
    assert not hasattr(q, "execute")
