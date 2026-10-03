"""BBCI host preservation + sparse host_surface opportunities."""

from pathlib import Path

from agent_core.recon.adapter import adapt_bbci_live_txt
from agent_core.recon.bbci_contract import parse_bbci_live_txt
from agent_core.target.opportunity import OpportunityEngine
from agent_core.recon.adapter import ReconResultAdapter, RawRecon

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "examples" / "fixtures" / "bbci" / "oneplus.ch.live.txt"
SAMPLE = ROOT / "examples" / "fixtures" / "sample_recon.json"


def test_oneplus_hosts_remain_distinct():
    text = LIVE.read_text(encoding="utf-8")
    res = parse_bbci_live_txt(text, program_name="oneplus.ch")
    assert res.ok
    hosts = {e.get("host") for e in res.normalized["endpoints"] if e.get("host")}
    for expected in ("files.oneplus.ch", "api.oneplus.ch", "help.oneplus.ch"):
        assert expected in hosts, expected
    # Same path / on different hosts must not collapse
    paths_by_host = {}
    for e in res.normalized["endpoints"]:
        paths_by_host.setdefault(e["host"], set()).add(e["path"])
    assert len(paths_by_host) >= 3


def test_adapter_preserves_hosts_and_endpoint_hosts():
    text = LIVE.read_text(encoding="utf-8")
    (ctx, graph, meta), contract = adapt_bbci_live_txt("eng", text, program_name="oneplus.ch")
    assert contract.ok
    assert "api.oneplus.ch" in ctx.hosts or any(e.host == "api.oneplus.ch" for e in ctx.endpoints)
    ep_hosts = {e.host for e in ctx.endpoints if e.host}
    assert "files.oneplus.ch" in ep_hosts
    assert "api.oneplus.ch" in ep_hosts


def test_host_surface_opportunities_nonzero_no_fake_authz():
    text = LIVE.read_text(encoding="utf-8")
    (ctx, graph, _), _ = adapt_bbci_live_txt("eng", text, program_name="oneplus.ch")
    opps = OpportunityEngine("eng").rank(ctx, graph)
    assert len(opps) >= 1
    host_ops = [o for o in opps if o.type == "host_surface"]
    assert host_ops
    # Must not invent authorization from host-only recon
    assert not any(o.type in ("authorization", "authorization_mutation") for o in opps)
    assert all(o.identity_surface is False for o in host_ops)


def test_deterministic_double_run():
    text = LIVE.read_text(encoding="utf-8")
    a1, _ = adapt_bbci_live_txt("eng", text, program_name="oneplus.ch")
    a2, _ = adapt_bbci_live_txt("eng", text, program_name="oneplus.ch")
    ctx1, g1, _ = a1
    ctx2, g2, _ = a2
    assert [e.endpoint_id for e in ctx1.endpoints] == [e.endpoint_id for e in ctx2.endpoints]
    o1 = OpportunityEngine("eng").rank(ctx1, g1)
    o2 = OpportunityEngine("eng").rank(ctx2, g2)
    assert [o.opportunity_id for o in o1] == [o.opportunity_id for o in o2]


def test_rich_sample_recon_still_has_authz_opportunities():
    data = __import__("json").loads(SAMPLE.read_text(encoding="utf-8"))
    ctx, graph, _ = ReconResultAdapter("eng_rich").adapt(RawRecon.from_dict(data))
    opps = OpportunityEngine("eng_rich").rank(ctx, graph)
    assert any(o.type in ("authorization", "authorization_mutation", "api_surface") for o in opps)
