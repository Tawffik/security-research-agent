"""Control plane + ResearchRuntime — offline, authenticated, no shell endpoints."""

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    token = "test-token-16chars-min"
    monkeypatch.setenv("AGENT_API_TOKEN", token)
    monkeypatch.setenv("AGENT_SESSION_DB", str(tmp_path / "sessions.db"))
    # rebuild app with new env
    from agent_core.control_plane.app import build_app
    from agent_core.runtime.engine import ResearchRuntime
    from agent_core.runtime.store import SessionStore

    store = SessionStore(tmp_path / "sessions.db")
    rt = ResearchRuntime(
        store,
        default_recon=ROOT / "examples" / "fixtures" / "sample_recon.json",
        default_scope=ROOT / "examples" / "demo_program_scope.yaml",
    )
    app = build_app(runtime=rt)
    return TestClient(app), token


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_no_auth_required(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["live_http_default"] is False


def test_unauthenticated_rejected(client):
    c, _ = client
    assert c.get("/api/sessions").status_code == 401
    assert c.post("/api/sessions", json={}).status_code == 401


def test_dangerous_endpoints_absent(client):
    c, token = client
    for path in ("/exec", "/shell", "/python", "/run-anything", "/browser-any-url"):
        assert c.post(path, headers=auth(token)).status_code == 404


def test_session_lifecycle_e2e(client):
    c, token = client
    h = auth(token)
    r = c.post("/api/sessions", headers=h, json={"label": "e2e"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert r.json()["live_http"] is False

    r = c.post(f"/api/sessions/{sid}/start", headers=h)
    assert r.status_code == 200
    # wait for offline closed loop
    terminal = {"COMPLETED", "FAILED", "BLOCKED", "INCONCLUSIVE", "CANCELLED"}
    status = "RUNNING"
    for _ in range(60):
        time.sleep(0.25)
        s = c.get(f"/api/sessions/{sid}", headers=h).json()
        status = s["status"]
        if status in terminal:
            break
    assert status in terminal, status
    ev = c.get(f"/api/sessions/{sid}/events", headers=h).json()["events"]
    assert any(e["event_type"] == "SESSION_STARTED" for e in ev)
    assert any(e["event_type"] in ("SESSION_COMPLETED", "SESSION_FAILED", "SESSION_INCONCLUSIVE", "BLOCKED") for e in ev)
    rep = c.get(f"/api/sessions/{sid}/report", headers=h).json()
    assert rep["live_http"] is False
    assert "report" in rep


def test_duplicate_start_idempotent(client):
    c, token = client
    h = auth(token)
    sid = c.post("/api/sessions", headers=h, json={}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/start", headers=h)
    r2 = c.post(f"/api/sessions/{sid}/start", headers=h)
    assert r2.status_code == 200


def test_persistence_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token-16chars-min")
    from agent_core.runtime.store import SessionStore
    from agent_core.runtime.engine import ResearchRuntime

    db = tmp_path / "p.db"
    store = SessionStore(db)
    rt = ResearchRuntime(store, default_recon=ROOT / "examples/fixtures/sample_recon.json", default_scope=ROOT / "examples/demo_program_scope.yaml")
    s = rt.create_session(label="persist")
    sid = s.session_id
    store2 = SessionStore(db)
    loaded = store2.get_session(sid)
    assert loaded is not None
    assert loaded.label == "persist"


def test_ui_index_served(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "Security Research Agent" in r.text
