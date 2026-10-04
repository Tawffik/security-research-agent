#!/usr/bin/env bash
# One-shot Codespaces bootstrap: token + deps + control plane.
# Idempotent. Does not print secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:---start}"

export AGENT_REPO_ROOT="${AGENT_REPO_ROOT:-$ROOT}"
export AGENT_SESSION_DB="${AGENT_SESSION_DB:-/tmp/security-research-agent.db}"
export AGENT_CONTROL_PLANE_AUTO_SESSION="${AGENT_CONTROL_PLANE_AUTO_SESSION:-1}"
export AGENT_COOKIE_SECURE="${AGENT_COOKIE_SECURE:-1}"

ensure_token() {
  if [[ -n "${AGENT_API_TOKEN:-}" ]]; then
    return 0
  fi
  if [[ -f /tmp/agent-token ]]; then
    export AGENT_API_TOKEN="$(tr -d '\n\r' < /tmp/agent-token)"
    return 0
  fi
  openssl rand -hex 16 > /tmp/agent-token
  chmod 600 /tmp/agent-token
  export AGENT_API_TOKEN="$(tr -d '\n\r' < /tmp/agent-token)"
}

if [[ "$MODE" == "--install" ]]; then
  python3 -m pip install -q -e ".[control]" --index-url https://pypi.org/simple 2>/dev/null || \
    python3 -m pip install -q -e ".[control]"
  echo "bootstrap: deps installed"
  exit 0
fi

ensure_token
# Soft-start control plane if not already listening
if ! curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
  pkill -f "uvicorn.*agent_core.control_plane" 2>/dev/null || true
  nohup bash "$ROOT/scripts/run_control_plane.sh" > /tmp/security-agent.log 2>&1 &
  sleep 2
fi
if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo "bootstrap: control plane UP on :8080"
else
  echo "bootstrap: control plane not yet reachable — check /tmp/security-agent.log" >&2
fi
