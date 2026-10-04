# Mobile Control Plane

```
Android browser → HTTPS → Control Plane API/UI → ResearchRuntime → ClosedLoopRunner (offline lab)
```

Phone is **control only**. Python/Playwright/research run on the remote host.

## Quick start

```bash
export AGENT_API_TOKEN="$(openssl rand -hex 16)"   # min 16 chars
export AGENT_SESSION_DB="$PWD/data/sessions.db"
pip install -e '.[control]'   # fastapi uvicorn httpx
# optional: pip install -e '.[browser]' from official PyPI if mirror fails
./scripts/run_control_plane.sh
```

Open `http://<host>:8080/` on the phone, paste the token, create a session, Start.

## Security

- Bearer token required for all `/api/*` mutating/read APIs
- No `/exec`, `/shell`, `/python`, `/browser-any-url`
- `live_http` is always false on this path (offline lab fixtures)
- ScopeGuard remains authoritative inside ClosedLoopRunner
- Knowledge/skill cannot grant execution via the UI

## Persistence

SQLite at `AGENT_SESSION_DB` stores sessions + ordered events. Survives process restart.

## GitHub Actions

CI only. Not the interactive agent runtime.


## Authentication (mobile)

Browser uses an **HttpOnly signed session cookie** (`sra_cp_session`), bootstrapped on `GET /` when `AGENT_API_TOKEN` is configured and `AGENT_CONTROL_PLANE_AUTO_SESSION=1` (default).

- Long-lived `AGENT_API_TOKEN` stays on the server only.
- Programmatic clients may still use `Authorization: Bearer <AGENT_API_TOKEN>`.
- Set `AGENT_CONTROL_PLANE_AUTO_SESSION=0` to disable cookie auto-bootstrap (Bearer required for bootstrap).
- Set `AGENT_COOKIE_SECURE=1` when serving over HTTPS (Codespaces forwarded URL).
