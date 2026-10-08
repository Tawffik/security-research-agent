#!/usr/bin/env python3
"""Offline: BBCI meta/sra_handoff.json → contract → ReconResultAdapter."""
from __future__ import annotations

import json
from pathlib import Path

from agent_core.recon.adapter import adapt_bbci_artifact
from agent_core.recon.bbci_contract import normalize_bbci_artifact

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "bbci" / "capital_sra_handoff.json"


def test_sra_handoff_contract_and_adapt():
    raw = json.loads(FIXTURE.read_text())
    assert raw.get("schema") == "bugbountyci.sra_handoff.v1"
    contract = normalize_bbci_artifact(raw)
    assert contract.ok, contract.error_messages()
    assert contract.source_shape == "sra_handoff_v1"
    assert contract.normalized.get("primary_host") == "capital.com"
    assert len(contract.normalized.get("endpoints") or []) >= 5
    # host preserved on at least one absolute-origin API
    hosts = {e.get("host") for e in contract.normalized["endpoints"] if e.get("host")}
    assert hosts, "expected endpoint host fields from sra_handoff"

    adapted, contract2 = adapt_bbci_artifact("eng_bbci_handoff_test", raw)
    ctx, graph, meta = adapted
    assert ctx.primary_host == "capital.com"
    assert len(ctx.endpoints) >= 5
    assert contract2.ok


def test_offline_sra_handoff_adapt_report():
    from agent_core.orchestrator.offline_bbci_episode import run_offline_sra_handoff_adapt
    report = run_offline_sra_handoff_adapt(FIXTURE)
    assert report.ok
    assert report.contract_ok
    assert report.primary_host == "capital.com"
    assert report.n_endpoints >= 5
    assert report.stages.get("adaptation") is True


def test_offline_sra_handoff_closed_loop_episode():
    from agent_core.orchestrator.offline_bbci_episode import run_offline_sra_handoff_episode
    scope = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "bbci" / "capital_offline_scope.yaml"
    report = run_offline_sra_handoff_episode(FIXTURE, scope_path=scope)
    assert report.contract_ok
    assert report.primary_host == "capital.com"
    assert report.n_endpoints >= 5
    assert report.stages.get("ingestion") is True
    assert report.stages.get("adaptation") is True
    # ClosedLoop may omit some stages depending on plan emptiness — record honestly
    assert report.execution_mode == "offline_lab"
    assert "no_live_http" in report.notes
