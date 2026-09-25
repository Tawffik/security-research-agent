from pathlib import Path

from agent_core.recon.adapter import adapt_bbci_live_txt
from agent_core.recon.bbci_contract import parse_bbci_live_txt
from agent_core.target.opportunity import OpportunityEngine

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "examples" / "fixtures" / "bbci" / "oneplus.ch.live.txt"


def test_parse_oneplus_live_txt():
    text = LIVE.read_text(encoding="utf-8")
    res = parse_bbci_live_txt(text, program_name="oneplus.ch")
    assert res.ok
    assert res.normalized["primary_host"]
    assert res.normalized["endpoints"]
    assert res.source_shape == "live_txt"


def test_adapt_oneplus_to_target_and_opportunities():
    text = LIVE.read_text(encoding="utf-8")
    (ctx, graph, meta), contract = adapt_bbci_live_txt(
        "eng_oneplus", text, program_name="oneplus.ch"
    )
    assert contract.ok
    assert ctx.primary_host
    assert ctx.endpoints
    opps = OpportunityEngine("eng_oneplus").rank(ctx, graph)
    # may be empty if paths are only '/' — still must not crash
    assert isinstance(opps, list)


def test_live_txt_tab_format():
    sample = "http://api.example.com/v1\t404\t\nhttp://app.example.com\t200\t\n"
    res = parse_bbci_live_txt(sample, primary_host="example.com")
    assert res.ok
    assert len(res.normalized["endpoints"]) >= 1
