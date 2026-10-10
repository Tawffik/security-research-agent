# Mobile Control Plane

```
Android browser → HTTPS (Codespaces) → Control Plane → ResearchRuntime → ClosedLoopRunner (offline)
```

Phone is **control only**. Python / tools / research run on the remote host.

## Quick start (Codespaces)

```bash
# Token once per environment (already OK if /tmp/agent-token exists)
# export AGENT_API_TOKEN="$(openssl rand -hex 16)"
# printf '%s' "$AGENT_API_TOKEN" > /tmp/agent-token

export AGENT_CONTROL_PLANE_AUTO_SESSION=1
export AGENT_COOKIE_SECURE=1   # recommended for https://*.app.github.dev
./scripts/run_control_plane.sh
```

Open the forwarded URL on the phone. **Do not paste the API token into the browser.**

Expected UI: `Auth: session active` → New session / Refresh.

## Authentication model

| Client | Mechanism |
|--------|-----------|
| Browser / phone | HttpOnly cookie `sra_cp_session` (HMAC-signed, not the raw API token) |
| CLI / automation | `Authorization: Bearer <AGENT_API_TOKEN>` |

- `GET /` mints the session cookie when `AGENT_API_TOKEN` is configured and `AGENT_CONTROL_PLANE_AUTO_SESSION=1` (default).
- `AGENT_CONTROL_PLANE_AUTO_SESSION=0` disables auto-bootstrap; Bearer required for `/api/auth/bootstrap`.
- `AGENT_COOKIE_SECURE=1` forces Secure cookies; otherwise Secure is set when `X-Forwarded-Proto: https` or HTTPS scheme is detected.
- Protected `/api/*` accept **Bearer or** valid session cookie; otherwise **401**.
- `/health` remains unauthenticated (no secrets in the body).

### Trust model (Codespaces)

Auto-session assumes **single-user** access to the Codespace port (prefer **private** port visibility). Anyone who can reach the process can obtain a control session when auto-session is on. Do not expose the port publicly without turning auto-session off and using a stricter front door.

### CSRF

State-changing routes are same-origin only; the cookie is `SameSite=Lax`; the mobile UI uses relative same-origin `fetch` with `credentials: 'same-origin'`. There is no cross-origin credentialed API design. This is appropriate for the single-origin control plane; do not enable CORS with credentials for untrusted origins.

### What must never leave the server

`AGENT_API_TOKEN` must not appear in HTML, JS, localStorage, URL, cookie value, or API response bodies.

## Security invariants (unchanged)

- No `/exec`, `/shell`, `/python`, `/run-anything`, `/browser-any-url`
- `live_http=false` on this path
- ScopeGuard remains authoritative
- Knowledge ≠ execution permission

## Persistence

SQLite at `AGENT_SESSION_DB` stores research sessions + ordered events.

## GitHub Actions

CI / temporary workers only — not the interactive mobile control-plane host.

## BugBountyCI artifacts (read-only)

BugBountyCI is **not** modified by this agent.

1. Export / copy a `*.live.txt` (or recon JSON) into a readable path, e.g.:
   - `examples/fixtures/bbci/` in this repo, or
   - any directory listed in `AGENT_RECON_DIR`
2. From the mobile UI: pick the artifact in the dropdown → **New session** → **Start**.
3. Execution stays `offline_lab` / `live_http=false` unless a future authorized live gate is enabled separately.

API:

- `GET /api/artifacts` — list available recon files + scope hints
- `POST /api/sessions` with `recon_path` / `scope_path`


## Codespaces: stop repeating setup

On create/start, `.devcontainer` runs `scripts/codespace_bootstrap.sh`:
- installs control-plane deps (postCreate)
- ensures `/tmp/agent-token` and starts uvicorn on `:8080` (postStart)

Manual recovery:
```bash
bash scripts/codespace_bootstrap.sh --start
```

## Optional OpenRouter (assist only)

Set a **Codespace secret** (not in git, not in chat):
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free   # optional
```

- `GET /api/llm/status?probe=1` — connectivity check (no key in response)
- `POST /api/llm/assist` — untrusted suggestions only
- Research findings still come from evidence loop, never from the model alone
- Without the key, the agent research loop works as before


## Codespaces + OpenCode + SRA MCP Gateway (no VPS)

### Android path (free Codespaces)

1. Open `https://github.com/Tawffik/security-research-agent` in Chrome on Android.
2. **Code → Codespaces → Create / Resume**.
3. Wait for `postCreate` / `postStart` (control plane on port 8080).
4. In the Codespace terminal:

```bash
export PYTHONPATH=src
python3 -m agent_core.integrations.mcp_stdio_server --list-tools
python3 -m agent_core.integrations.mcp_stdio_server --call sra_browser_navigate \
  '{"url":"https://api.acme-demo.test/orders/1","experiment_id":"exp-demo"}'
```

5. Optional OpenCode (if installed in the Codespace):

```bash
# Install once per Codespace (official installer — check opencode.ai/docs)
# Then copy config:
cp config/remote/opencode-mcp.example.json opencode.json
# Launch TUI / web UI via Codespaces terminal; use private port forward only.
```

6. Control plane UI: open forwarded **8080** (private) → cookie session auto-auth.

### Defaults

- MCP gateway tools only: `sra_*` allowlist
- Raw Playwright/Burp MCP **disabled** in the example profile
- `live_mode=false` — no live target traffic
- Synthetic browser pages for offline E2E

### Live target

Do **not** enable live mode until you supply an authorized program scope file and explicit approval.
