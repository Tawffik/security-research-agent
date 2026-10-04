"""Control plane sessions can consume BBCI live.txt offline without modifying BBCI."""

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "examples" / "fixtures" / "bbci" / "oneplus.ch.live.txt"
SCOPE = ROOT / "examples" / "fixtures" / "bbci" / "oneplus_offline_scope.yaml"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "bbci-test-token-16chars")
    monkeypatch.setenv("AGENT_SESSION_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("AGENT_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("AGENT_CONTROL_PLANE_AUTO_SESSION", "1")
    from agent_core.control_plane.app import build_app
    from agent_core.runtime.engine import ResearchRuntime
    from agent_core.runtime.store import SessionStore

    rt = ResearchRuntime(
        SessionStore(tmp_path / "s.db"),
        default_recon=ROOT / "examples/fixtures/sample_recon.json",
        default_scope=ROOT / "examples/demo_program_scope.yaml",
    )
    return TestClient(build_app(runtime=rt)), rt


def test_list_artifacts_includes_bbci_live_txt(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    client.get("/")
    r = client.get("/api/artifacts")
    assert r.status_code == 200
    arts = r.json()["artifacts"]
    paths = [a["path"] for a in arts]
    assert any(p.endswith("oneplus.ch.live.txt") for p in paths)
    bbci = [a for a in arts if a["kind"] == "bbci_live_txt"]
    assert bbci
    assert bbci[0].get("scope_hint")


def test_session_runs_bbci_live_txt_offline(tmp_path, monkeypatch):
    import time

    assert LIVE.is_file() and SCOPE.is_file()
    client, _ = _client(tmp_path, monkeypatch)
    client.get("/")
    r = client.post(
        "/api/sessions",
        json={
            "label": "bbci-oneplus",
            "recon_path": str(LIVE),
            "scope_path": str(SCOPE),
        },
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert r.json()["recon_path"] == str(LIVE)
    client.post(f"/api/sessions/{sid}/start")
    terminal = {"COMPLETED", "FAILED", "BLOCKED", "INCONCLUSIVE", "CANCELLED"}
    status = "RUNNING"
    for _ in range(80):
        time.sleep(0.25)
        status = client.get(f"/api/sessions/{sid}").json()["status"]
        if status in terminal:
            break
    assert status in terminal, status
    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["live_http"] is False
    assert rep["report"].get("artifact_kind") == "bbci_live_txt"
    assert rep["report"].get("execution_mode") == "offline_lab"
    events = client.get(f"/api/sessions/{sid}/events").json()["events"]
    assert any(e["event_type"] == "SESSION_STARTED" for e in events)


def test_artifacts_endpoint_requires_auth(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    # no cookie yet
    assert client.get("/api/artifacts").status_code == 401
