"""OpenRouter is optional assist; research works without it."""

import os
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path, monkeypatch, with_key=False):
    monkeypatch.setenv("AGENT_API_TOKEN", "llm-test-token-16chars")
    monkeypatch.setenv("AGENT_SESSION_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("AGENT_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("AGENT_CONTROL_PLANE_AUTO_SESSION", "1")
    if with_key:
        monkeypatch.setenv("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", "sk-or-test-not-real-0000"))
    else:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_KEY", raising=False)
    from agent_core.control_plane.app import build_app
    from agent_core.runtime.engine import ResearchRuntime
    from agent_core.runtime.store import SessionStore

    rt = ResearchRuntime(
        SessionStore(tmp_path / "s.db"),
        default_recon=ROOT / "examples/fixtures/sample_recon.json",
        default_scope=ROOT / "examples/demo_program_scope.yaml",
    )
    return TestClient(build_app(runtime=rt))


def test_llm_status_without_key(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_key=False)
    client.get("/")
    r = client.get("/api/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert body["findings_source"] == "never_llm"
    assert body["llm"]["configured"] is False
    assert "OPENROUTER" in body["llm"]["error"]


def test_health_reports_llm_flag(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_key=False)
    h = client.get("/health").json()
    assert h.get("llm_role") == "assist_only"
    assert h.get("llm_configured") is False


def test_assist_fails_closed_without_key(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, with_key=False)
    client.get("/")
    r = client.post("/api/llm/assist", json={"prompt": "suggest hypotheses for BOLA"})
    assert r.status_code == 503


def test_probe_module_no_key():
    from agent_core.llm.openrouter import probe_openrouter
    st = probe_openrouter(live_call=False)
    # may or may not be configured in env; just ensure shape
    assert hasattr(st, "configured")
    d = st.to_dict()
    assert "configured" in d
