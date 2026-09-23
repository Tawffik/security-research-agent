from pathlib import Path

from agent_core.orchestrator.closed_loop import default_idor_lab_scenario, secure_lab_scenario
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_confirmed_has_low_regret_relative_to_reject_path_quality():
    _, _, _, regrets, _sur, _mem = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_ar_c",
        scenario=default_idor_lab_scenario(),
    )
    assert len(regrets) == 2
    closed_r = regrets[0]
    assert closed_r.evidence_created >= 1
    assert closed_r.actual_information_gain >= 0.5
    assert closed_r.regret < closed_r.expected_information_gain


def test_rejected_still_useful_negative_evidence():
    _, adaptive, _, regrets, _sur, _mem = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_ar_r",
        scenario=secure_lab_scenario(),
    )
    assert adaptive.stop
    closed_r = regrets[0]
    assert closed_r.actual_information_gain >= 0.4  # negative evidence counts
    assert any("negative" in n.lower() or "rejected" in n.lower() for n in closed_r.notes)
