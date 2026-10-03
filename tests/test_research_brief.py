from pathlib import Path

from agent_core.orchestrator.closed_loop import ClosedLoopRunner, default_idor_lab_scenario
from agent_core.research.brief import compile_brief_from_closed_loop

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_compile_brief_from_closed_loop():
    r = ClosedLoopRunner(scope_path=SCOPE, engagement_id="brief1").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    brief = compile_brief_from_closed_loop(r, engagement_id="brief1")
    assert brief.scope_state in ("allowed", "denied")
    assert brief.next_decision
    assert brief.engagement_id == "brief1"
    d = brief.to_dict()
    assert "evidence_debt" in d
