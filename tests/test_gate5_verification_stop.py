"""Gate 5.3 executable verification + Gate 5.4 structured stop semantics."""

import tempfile
from pathlib import Path

from agent_core.evidence.store import EvidencePolarity, EvidenceStore, FindingStatus
from agent_core.research.stop_semantics import NON_SECURE_STOPS, StopReason, evaluate_stop
from agent_core.verification.executable import ExecutableVerifier, VerificationOutcome


def _store() -> EvidenceStore:
    d = tempfile.mkdtemp()
    return EvidenceStore.open(Path(d) / "ev.db")


def test_insufficient_evidence_cannot_confirm():
    store = _store()
    v = ExecutableVerifier(store)
    contract = v.build_contract("ownership bypass", hypothesis_id="h1", min_positive=1)
    result = v.verify(contract)
    assert result.outcome == VerificationOutcome.INCONCLUSIVE.value
    assert result.cannot_become_confirmed is True
    assert result.finding_status != FindingStatus.CONFIRMED.value


def test_positive_evidence_can_confirm():
    store = _store()
    store.record(
        target="api/x",
        action="GET",
        input_data="id=1",
        expected="deny",
        observed="200 secret",
        polarity=EvidencePolarity.POSITIVE,
        confidence=0.9,
        source="lab",
        related_hypothesis="h1",
    )
    v = ExecutableVerifier(store)
    contract = v.build_contract("ownership bypass", hypothesis_id="h1")
    result = v.verify(contract)
    assert result.outcome == VerificationOutcome.CONFIRMED.value
    assert result.finding_status == FindingStatus.CONFIRMED.value


def test_negative_only_disproves_not_secure():
    store = _store()
    store.record(
        target="api/x",
        action="GET",
        input_data="id=1",
        expected="deny",
        observed="403",
        polarity=EvidencePolarity.NEGATIVE,
        confidence=0.9,
        source="lab",
        related_hypothesis="h1",
    )
    v = ExecutableVerifier(store)
    contract = v.build_contract("ownership bypass", hypothesis_id="h1")
    result = v.verify(contract)
    assert result.outcome == VerificationOutcome.DISPROVED.value
    assert result.cannot_become_confirmed is True


def test_stop_no_evidence_never_secure():
    t = evaluate_stop(StopReason.INCONCLUSIVE_EXHAUSTED)
    assert t.secure_claim_allowed is False
    t2 = evaluate_stop(StopReason.SCOPE_BLOCKED)
    assert t2.secure_claim_allowed is False
    t3 = evaluate_stop(StopReason.BUDGET_EXHAUSTED)
    assert t3.secure_claim_allowed is False
    for s in NON_SECURE_STOPS:
        assert evaluate_stop(s).secure_claim_allowed is False


def test_stop_verified_without_positive_becomes_inconclusive():
    t = evaluate_stop(StopReason.VERIFIED, has_positive_evidence=False)
    assert t.stop_reason == StopReason.INCONCLUSIVE_EXHAUSTED.value
    assert t.secure_claim_allowed is False


def test_stop_verified_with_positive_not_global_secure():
    t = evaluate_stop(StopReason.VERIFIED, has_positive_evidence=True, finding_id="f1")
    assert t.finding_id == "f1"
    assert t.secure_claim_allowed is False  # claim verified ≠ target secure
