import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.evidence.store import EvidenceStore, EvidencePolarity, FindingStatus


def make_store(tmp_path) -> EvidenceStore:
    return EvidenceStore.open(tmp_path / "test_evidence.db")


def test_record_and_verify_chain(tmp_path):
    store = make_store(tmp_path)
    store.record(
        target="acme.com", action="probe", input_data="x", expected="y", observed="z",
        polarity=EvidencePolarity.NEUTRAL, confidence=0.5, source="test",
    )
    store.record(
        target="acme.com", action="probe2", input_data="x2", expected="y2", observed="z2",
        polarity=EvidencePolarity.POSITIVE, confidence=0.9, source="test",
    )
    assert store.verify_chain() is True


def test_tampering_breaks_chain(tmp_path):
    store = make_store(tmp_path)
    store.record(
        target="acme.com", action="probe", input_data="x", expected="y", observed="z",
        polarity=EvidencePolarity.NEUTRAL, confidence=0.5, source="test",
    )
    # Simulate tampering: directly mutate a row after the fact.
    store.conn.execute("UPDATE evidence SET observed = 'tampered!'")
    store.conn.commit()
    assert store.verify_chain() is False


def test_negative_evidence_prevents_retry(tmp_path):
    store = make_store(tmp_path)
    store.record(
        target="acme.com", action="idor_probe", input_data="obj=1042", expected="403", observed="403",
        polarity=EvidencePolarity.NEGATIVE, confidence=0.9, source="authz-idor-analysis",
        related_hypothesis="H002",
    )
    negatives = store.negative_evidence_for("H002")
    assert len(negatives) == 1
    assert negatives[0].observed == "403"


def test_finding_lifecycle(tmp_path):
    store = make_store(tmp_path)
    ev = store.record(
        target="acme.com", action="idor_probe", input_data="obj=1042", expected="403", observed="200",
        polarity=EvidencePolarity.POSITIVE, confidence=0.9, source="authz-idor-analysis",
        related_hypothesis="H001",
    )
    finding_id = store.create_finding(title="IDOR on invoices", evidence_ids=[ev.evidence_id], severity="high")
    store.set_finding_status(finding_id, FindingStatus.CONFIRMED)
    row = store.conn.execute("SELECT status FROM findings WHERE finding_id=?", (finding_id,)).fetchone()
    assert row[0] == FindingStatus.CONFIRMED.value
