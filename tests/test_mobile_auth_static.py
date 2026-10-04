"""Mobile control-plane auth: session cookie + bearer; no secret leakage."""

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "static" / "mobile" / "index.html"


def _client(tmp_path, monkeypatch, token="correct-token-16chars-xx", auto="1"):
    monkeypatch.setenv("AGENT_API_TOKEN", token)
    monkeypatch.setenv("AGENT_SESSION_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("AGENT_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("AGENT_CONTROL_PLANE_AUTO_SESSION", auto)
    from agent_core.control_plane.app import build_app
    from agent_core.runtime.engine import ResearchRuntime
    from agent_core.runtime.store import SessionStore

    rt = ResearchRuntime(
        SessionStore(tmp_path / "s.db"),
        default_recon=ROOT / "examples/fixtures/sample_recon.json",
        default_scope=ROOT / "examples/demo_program_scope.yaml",
    )
    return TestClient(build_app(runtime=rt)), token


def test_mobile_index_has_v3_session_auth_not_token_paste():
    src = INDEX.read_text(encoding="utf-8")
    assert "mobile-auth-v3" in src
    assert "Save token" not in src
    assert "localStorage.getItem" not in src and "localStorage.setItem" not in src
    assert "Save token" not in src  # no manual secret UX
    assert "credentials: 'same-origin'" in src or 'credentials: "same-origin"' in src


def test_bearer_auth_matrix(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch, auto="0")
    assert client.get("/health").status_code == 200
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": "Bearer wrong-token-16chars"}).status_code == 401
    ok = client.get("/api/sessions", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200


def test_get_slash_bootstraps_session_cookie(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch, auto="1")
    r = client.get("/")
    assert r.status_code == 200
    assert "mobile-auth-v3" in r.text
    assert token not in r.text
    assert "sra_cp_session" in r.cookies
    # Cookie alone authenticates API
    r2 = client.get("/api/sessions")
    assert r2.status_code == 200
    assert "sessions" in r2.json()


def test_session_cookie_does_not_contain_api_token(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch)
    r = client.get("/")
    cookie = r.cookies.get("sra_cp_session")
    assert cookie
    assert token not in cookie
    assert token not in r.text


def test_forged_cookie_rejected(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    client.cookies.set("sra_cp_session", "forged.notvalid")
    assert client.get("/api/sessions").status_code == 401


def test_bootstrap_endpoint(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, auto="1")
    r = client.post("/api/auth/bootstrap")
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    assert client.get("/api/sessions").status_code == 200


def test_auto_session_off_requires_bearer_for_bootstrap(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch, auto="0")
    assert client.post("/api/auth/bootstrap").status_code == 401
    assert client.post("/api/auth/bootstrap", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_api_token_never_in_responses(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch)
    for path in ("/", "/health", "/api/auth/session"):
        body = client.get(path).text
        assert token not in body


def test_dangerous_routes_still_absent(tmp_path, monkeypatch):
    client, token = _client(tmp_path, monkeypatch)
    client.get("/")  # bootstrap
    for path in ("/exec", "/shell", "/python", "/run-anything", "/browser-any-url"):
        assert client.post(path).status_code == 404
