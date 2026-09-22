"""Tests for ReconResultAdapter — deterministic normalization."""

from __future__ import annotations

from pathlib import Path

from agent_core.recon.adapter import RawRecon, ReconResultAdapter

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "sample_recon.json"


def test_adapt_fixture_produces_context_and_graph():
    adapter = ReconResultAdapter("eng_test")
    ctx, graph, norm = adapter.adapt(RawRecon.from_file(FIXTURE))
    assert ctx.engagement_id == "eng_test"
    assert ctx.primary_host == "api.acme-demo.test"
    assert len(ctx.actors) >= 2
    assert len(ctx.endpoints) >= 5
    assert len(ctx.resources) >= 2
    assert graph.engagement_id == "eng_test"
    assert len(graph.nodes) > 0
    assert any(e.kind.value == "owns" for e in graph.edges)
    assert norm["endpoint_count"] == len(ctx.endpoints)


def test_deterministic_same_recon():
    adapter = ReconResultAdapter("eng_det")
    r = RawRecon.from_file(FIXTURE)
    ctx1, graph1, n1 = adapter.adapt(r)
    ctx2, graph2, n2 = adapter.adapt(r)
    assert [a.actor_id for a in ctx1.actors] == [a.actor_id for a in ctx2.actors]
    assert [e.endpoint_id for e in ctx1.endpoints] == [e.endpoint_id for e in ctx2.endpoints]
    assert n1["endpoint_count"] == n2["endpoint_count"]


def test_dedup_actors_and_endpoints():
    data = {
        "primary_host": "api.test",
        "actors": [
            {"name": "u1", "roles": ["customer"]},
            {"name": "u1", "roles": ["customer"]},
        ],
        "endpoints": [
            {"method": "GET", "path": "/x", "host": "api.test"},
            {"method": "GET", "path": "/x", "host": "api.test"},
        ],
        "resources": [],
    }
    ctx, _, _ = ReconResultAdapter("e").adapt(RawRecon.from_dict(data))
    assert len(ctx.actors) == 1
    assert len(ctx.endpoints) == 1
