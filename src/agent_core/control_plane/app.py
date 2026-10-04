"""
FastAPI control plane for mobile-controlled remote research agent.

Auth:
  - Bearer AGENT_API_TOKEN for programmatic clients
  - Signed HttpOnly session cookie for browser/mobile UI (bootstrapped on GET /)

No /exec, /shell, /python, /browser-any-url endpoints.
All research goes through ResearchRuntime → existing ClosedLoopRunner (offline).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_core.control_plane.auth import (
    COOKIE_NAME,
    is_authenticated,
    mint_session_cookie_value,
    token_configured,
    verify_bearer,
    verify_session_cookie_value,
)
from agent_core.runtime.engine import ResearchRuntime
from agent_core.runtime.store import SessionStore


def _repo_root() -> Path:
    env = os.environ.get("AGENT_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


ROOT = _repo_root()


class CreateBody(BaseModel):
    label: str = "research"
    recon_path: str = ""
    scope_path: str = ""


DEFAULT_DB = Path(os.environ.get("AGENT_SESSION_DB", str(ROOT / "data" / "sessions.db")))


def _auto_session_enabled() -> bool:
    # Default ON for single-user Codespaces/mobile control plane.
    return os.environ.get("AGENT_CONTROL_PLANE_AUTO_SESSION", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _cookie_secure(request: Request | None = None) -> bool:
    raw = os.environ.get("AGENT_COOKIE_SECURE", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    if request is not None:
        xf = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
        if xf == "https":
            return True
        if str(request.url.scheme).lower() == "https":
            return True
    return False


def build_app(runtime: ResearchRuntime | None = None) -> FastAPI:
    store = SessionStore(DEFAULT_DB)
    rt = runtime or ResearchRuntime(store)
    app = FastAPI(title="Security Research Agent Control Plane", version="0.2.0")
    app.state.runtime = rt

    static_dir = ROOT / "static" / "mobile"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def require_auth(request: Request, authorization: Optional[str] = Header(default=None)) -> None:
        if not token_configured():
            raise HTTPException(status_code=503, detail="AGENT_API_TOKEN not configured (min 16 chars)")
        cookie = request.cookies.get(COOKIE_NAME)
        if not is_authenticated(authorization_header=authorization, session_cookie=cookie):
            raise HTTPException(status_code=401, detail="unauthorized")

    def _set_session_cookie(
        response: HTMLResponse | JSONResponse,
        request: Request | None = None,
    ) -> None:
        if not token_configured():
            return
        response.set_cookie(
            key=COOKIE_NAME,
            value=mint_session_cookie_value(),
            httponly=True,
            samesite="lax",
            secure=_cookie_secure(request),
            max_age=12 * 3600,
            path="/",
        )

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        h = rt.health()
        h["auth_configured"] = token_configured()
        h["browser_session"] = verify_session_cookie_value(request.cookies.get(COOKIE_NAME))
        h["auth_modes"] = ["bearer", "session_cookie"]
        return h

    @app.get("/api/auth/session")
    def auth_session_status(request: Request) -> dict[str, Any]:
        ok = token_configured() and verify_session_cookie_value(request.cookies.get(COOKIE_NAME))
        return {"authenticated": ok, "mode": "session_cookie" if ok else None}

    @app.post("/api/auth/bootstrap")
    def auth_bootstrap(request: Request, authorization: Optional[str] = Header(default=None)) -> JSONResponse:
        if not token_configured():
            raise HTTPException(status_code=503, detail="AGENT_API_TOKEN not configured (min 16 chars)")
        if not _auto_session_enabled() and not verify_bearer(authorization):
            raise HTTPException(status_code=401, detail="unauthorized")
        resp = JSONResponse({"authenticated": True, "mode": "session_cookie"})
        _set_session_cookie(resp, request)
        return resp

    @app.get("/api/artifacts")
    def list_artifacts(request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        """List readable recon artifacts (BBCI exports + fixtures). Read-only; does not call BBCI."""
        return {"artifacts": rt.list_artifacts(), "live_http": False}

    @app.get("/api/status")

    def status(request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        sessions = rt.list_sessions()
        active = [s.session_id for s in sessions if s.status == "RUNNING"]
        return {
            "health": rt.health(),
            "session_count": len(sessions),
            "active": active,
            "live_http_default": False,
        }

    @app.post("/api/sessions")
    async def create_session(request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        sess = rt.create_session(
            label=str(data.get("label") or "research"),
            recon_path=str(data.get("recon_path") or ""),
            scope_path=str(data.get("scope_path") or ""),
        )
        return sess.to_dict()

    @app.get("/api/sessions")
    def list_sessions(request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        return {"sessions": [s.to_dict() for s in rt.list_sessions()]}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        sess = rt.get(session_id)
        if not sess:
            raise HTTPException(404, "session_not_found")
        return sess.to_dict()

    def _mut(session_id: str, op: str) -> dict[str, Any]:
        try:
            if op == "start":
                return rt.start(session_id).to_dict()
            if op == "stop":
                return rt.stop(session_id).to_dict()
            if op == "pause":
                return rt.pause(session_id).to_dict()
            if op == "resume":
                return rt.resume(session_id).to_dict()
        except KeyError:
            raise HTTPException(404, "session_not_found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        raise HTTPException(400, "unknown_op")

    @app.post("/api/sessions/{session_id}/start")
    def start(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "start")

    @app.post("/api/sessions/{session_id}/stop")
    def stop(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "stop")

    @app.post("/api/sessions/{session_id}/pause")
    def pause(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "pause")

    @app.post("/api/sessions/{session_id}/resume")
    def resume(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "resume")

    @app.get("/api/sessions/{session_id}/events")
    def events(session_id: str, request: Request, after: int = 0, _: None = Depends(require_auth)) -> dict[str, Any]:
        if not rt.get(session_id):
            raise HTTPException(404, "session_not_found")
        evs = rt.store.list_events(session_id, after_sequence=after)
        return {"events": [e.to_dict() for e in evs]}

    @app.get("/api/sessions/{session_id}/events/stream")
    async def events_stream(
        session_id: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        require_auth(request, authorization)
        if not rt.get(session_id):
            raise HTTPException(404, "session_not_found")

        import asyncio
        import json

        async def gen():
            last = 0
            idle = 0
            while idle < 60:
                evs = rt.store.list_events(session_id, after_sequence=last)
                if not evs:
                    idle += 1
                    yield "event: ping\ndata: {}\n\n"
                    await asyncio.sleep(0.5)
                    continue
                idle = 0
                for e in evs:
                    last = e.sequence
                    yield f"data: {json.dumps(e.to_dict())}\n\n"
                sess = rt.get(session_id)
                if sess and sess.is_terminal():
                    break
                await asyncio.sleep(0.3)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/sessions/{session_id}/report")
    def report(session_id: str, request: Request, _: None = Depends(require_auth)) -> dict[str, Any]:
        sess = rt.get(session_id)
        if not sess:
            raise HTTPException(404, "session_not_found")
        return {
            "session_id": session_id,
            "status": sess.status,
            "outcome": sess.outcome,
            "stop_reason": sess.stop_reason,
            "finding_id": sess.latest_finding or None,
            "evidence_count": sess.evidence_count,
            "report": sess.report,
            "live_http": False,
        }

    @app.get("/", response_class=HTMLResponse)
    def ui_index(request: Request) -> HTMLResponse:
        index = static_dir / "index.html"
        if not index.exists():
            return HTMLResponse("<h1>Mobile UI missing</h1>", status_code=500)
        body = index.read_text(encoding="utf-8")
        resp = HTMLResponse(
            body,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )
        if token_configured() and _auto_session_enabled():
            existing = request.cookies.get(COOKIE_NAME)
            if not verify_session_cookie_value(existing):
                _set_session_cookie(resp, request)
        return resp

    @app.api_route("/exec", methods=["GET", "POST"])
    @app.api_route("/shell", methods=["GET", "POST"])
    @app.api_route("/python", methods=["GET", "POST"])
    @app.api_route("/run-anything", methods=["GET", "POST"])
    @app.api_route("/browser-any-url", methods=["GET", "POST"])
    def blocked_dangerous() -> JSONResponse:
        return JSONResponse({"error": "endpoint_not_available"}, status_code=404)

    return app


app = build_app()
