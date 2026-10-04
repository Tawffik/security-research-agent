#!/usr/bin/env bash
# Remote control plane for mobile browser (Codespaces-friendly).
# Does not print secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
export AGENT_CONTROL_PLANE_AUTO_SESSION="${AGENT_CONTROL_PLANE_AUTO_SESSION:-1}"
export AGENT_SESSION_DB="${AGENT_SESSION_DB:-$ROOT/data/sessions.db}"

# Reuse existing token file if present (Codespaces); never echo it.
if [[ -z "${AGENT_API_TOKEN:-}" && -f /tmp/agent-token ]]; then
  AGENT_API_TOKEN="$(tr -d '\n\r' < /tmp/agent-token)"
  export AGENT_API_TOKEN
fi

if [[ -z "${AGENT_API_TOKEN:-}" ]]; then
  echo "Set AGENT_API_TOKEN (min 16 chars) or place it in /tmp/agent-token before starting." >&2
  exit 1
fi

# Codespaces HTTPS port-forward: prefer Secure cookies by default.
if [[ -n "${CODESPACES:-}" || -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  export AGENT_COOKIE_SECURE="${AGENT_COOKIE_SECURE:-1}"
fi

HOST="${AGENT_HOST:-0.0.0.0}"
PORT="${AGENT_PORT:-8080}"
echo "Starting control plane on ${HOST}:${PORT} (auto_session=${AGENT_CONTROL_PLANE_AUTO_SESSION}, cookie_secure=${AGENT_COOKIE_SECURE:-auto})"
exec python3 -m uvicorn agent_core.control_plane.app:app --host "$HOST" --port "$PORT"
