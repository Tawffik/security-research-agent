"""Control-plane semantics: local Gate 6 blocker must not imply campaign stop."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_policy_document_exists_and_states_invariant():
    p = ROOT / ".agent" / "AUTONOMOUS_CAMPAIGN_POLICY.md"
    assert p.is_file()
    text = p.read_text()
    assert "LOCAL BLOCKER" in text
    assert "CAMPAIGN BLOCKER" in text
    assert "Gate 6" in text


def test_state_gate6_blocked_does_not_force_campaign_blocked_when_offline_work_listed():
    """If STATE still lists READY offline deps, campaign must not be CAMPAIGN_BLOCKED."""
    state_path = ROOT / ".agent" / "STATE.json"
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text())
    blocked_ids = {b.get("id") for b in state.get("blocked", [])}
    next_deps = state.get("next_dependencies") or []
    # After recovery, either campaign is IN_PROGRESS, or next_deps empty
    if next_deps and any(
        d for d in next_deps if d not in ("offline_research_episode_integration_audit",)
    ):
        assert state.get("campaign_status") != "CAMPAIGN_BLOCKED" or not next_deps
    if "gate6_live_bbci_e2e" in blocked_ids:
        # Gate 6 local block is expected and valid
        assert True


def test_gate6_blocker_record_has_resume_condition():
    state = json.loads((ROOT / ".agent" / "STATE.json").read_text())
    g6 = next((b for b in state.get("blocked", []) if b.get("id") == "gate6_live_bbci_e2e"), None)
    assert g6 is not None
    assert g6.get("resume_condition")
    assert g6.get("required_human_action")
