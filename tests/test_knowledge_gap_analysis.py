from pathlib import Path
from agent_core.knowledge.gap_analysis import analyze_knowledge_gaps

ROOT = Path(__file__).resolve().parents[1]


def test_gap_analysis_prioritizes_missing_procedures():
    gaps = analyze_knowledge_gaps(ROOT / "knowledge")
    assert gaps
    # xss/injection likely higher gap than authorization
    by = {g.security_property: g for g in gaps}
    assert by["authorization"].n_procedures >= 1
    assert by["xss"].priority >= by["authorization"].priority
