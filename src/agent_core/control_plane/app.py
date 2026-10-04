"""
FastAPI control plane for mobile-controlled remote research agent.

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
from pydantic import BaseModel, Field

from agent_core.control_plane.auth import token_configured, verify_bearer
from agent_core.runtime.engine import ResearchRuntime
from agent_core.runtime.store import SessionStore


def _repo_root() -> Path:
    env = os.environ.get("AGENT_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    # src/agent_core/control_plane/app.py -> repo root
    return Path(__file__).resolve().parents[3]


ROOT = _repo_root()


class CreateBody(BaseModel):
    label: str = "research"
    recon_path: str = ""
    scope_path: str = ""


DEFAULT_DB = Path(os.environ.get("AGENT_SESSION_DB", str(ROOT / "data" / "sessions.db")))


def build_app(runtime: ResearchRuntime | None = None) -> FastAPI:
    store = SessionStore(DEFAULT_DB)
    rt = runtime or ResearchRuntime(store)
    app = FastAPI(title="Security Research Agent Control Plane", version="0.1.0")
    app.state.runtime = rt

    static_dir = ROOT / "static" / "mobile"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
        if not token_configured():
            raise HTTPException(status_code=503, detail="AGENT_API_TOKEN not configured (min 16 chars)")
        if not verify_bearer(authorization):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health() -> dict[str, Any]:
        h = rt.health()
        h["auth_configured"] = token_configured()
        return h

    @app.get("/api/status")
    def status(_: None = Depends(require_auth)) -> dict[str, Any]:
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
    def list_sessions(_: None = Depends(require_auth)) -> dict[str, Any]:
        return {"sessions": [s.to_dict() for s in rt.list_sessions()]}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
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
    def start(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "start")

    @app.post("/api/sessions/{session_id}/stop")
    def stop(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "stop")

    @app.post("/api/sessions/{session_id}/pause")
    def pause(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "pause")

    @app.post("/api/sessions/{session_id}/resume")
    def resume(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        return _mut(session_id, "resume")

    @app.get("/api/sessions/{session_id}/events")
    def events(session_id: str, after: int = 0, _: None = Depends(require_auth)) -> dict[str, Any]:
        if not rt.get(session_id):
            raise HTTPException(404, "session_not_found")
        evs = rt.store.list_events(session_id, after_sequence=after)
        return {"events": [e.to_dict() for e in evs]}

    @app.get("/api/sessions/{session_id}/events/stream")
    async def events_stream(session_id: str, authorization: Optional[str] = Header(default=None)):
        # SSE — auth via header (EventSource cannot set headers easily; also support ?token= for mobile)
        require_auth(authorization)
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
    def report(session_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
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
    def ui_index() -> HTMLResponse:
        index = static_dir / "index.html"
        if index.exists():
            # Always re-read from disk so Codespaces/stale processes serve the fixed UI
            body = index.read_text(encoding="utf-8")
            return HTMLResponse(
                body,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
        return HTMLResponse("<h1>Mobile UI missing</h1>", status_code=500)

    # Explicitly absent dangerous routes
    @app.api_route("/exec", methods=["GET", "POST"])
    @app.api_route("/shell", methods=["GET", "POST"])
    @app.api_route("/python", methods=["GET", "POST"])
    @app.api_route("/run-anything", methods=["GET", "POST"])
    @app.api_route("/browser-any-url", methods=["GET", "POST"])
    def blocked_dangerous() -> JSONResponse:
        return JSONResponse({"error": "endpoint_not_available"}, status_code=404)

    return app


app = build_app()
