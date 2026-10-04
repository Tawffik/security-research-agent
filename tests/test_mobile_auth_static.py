"""Static mobile auth contract — no token leakage, correct Bearer format."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "static" / "mobile" / "index.html"


def test_mobile_index_has_correct_bearer_header_construction():
    src = INDEX.read_text(encoding="utf-8")
    assert "mobile-auth-v2" in src
    # Correct concat form (not the broken 'Bearer token()' string)
    assert "'Authorization': 'Bearer ' + t" in src or '"Authorization": "Bearer " + t' in src or "'Authorization': 'Bearer ' + t" in src
    assert "Bearer ' + t" in src or 'Bearer " + t' in src
    # Must not contain the historical broken pattern
    assert "'Authorization': 'Bearer token()" not in src
    assert '"Authorization": "Bearer token()' not in src
    # No query-param token
    assert "token=" not in src.lower() or "placeholder" in src  # placeholder ok
    assert "?token" not in src
    assert "localStorage.getItem(TOKEN_KEY)" in src or "localStorage.getItem('sra_token')" in src


def test_health_open_sessions_auth_matrix(tmp_path, monkeypatch):
    token = "correct-token-16chars-xx"
    monkeypatch.setenv("AGENT_API_TOKEN", token)
    monkeypatch.setenv("AGENT_SESSION_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("AGENT_REPO_ROOT", str(ROOT))
    from agent_core.control_plane.app import build_app
    from agent_core.runtime.engine import ResearchRuntime
    from agent_core.runtime.store import SessionStore

    rt = ResearchRuntime(
        SessionStore(tmp_path / "s.db"),
        default_recon=ROOT / "examples/fixtures/sample_recon.json",
        default_scope=ROOT / "examples/demo_program_scope.yaml",
    )
    client = TestClient(build_app(runtime=rt))

    assert client.get("/health").status_code == 200
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": "Bearer wrong-token-16chars"}).status_code == 401
    ok = client.get("/api/sessions", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert "sessions" in ok.json()

    # Served UI contains fixed auth marker
    html = client.get("/")
    assert html.status_code == 200
    assert "mobile-auth-v2" in html.text
    assert "Bearer ' + t" in html.text or 'Bearer " + t' in html.text
    assert html.headers.get("cache-control", "").startswith("no-store") or "no-store" in html.headers.get("cache-control", "")
