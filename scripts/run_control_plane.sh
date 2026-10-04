#!/usr/bin/env bash
# Remote control plane for mobile browser.
# Usage:
#   export AGENT_API_TOKEN="$(openssl rand -hex 16)"
#   ./scripts/run_control_plane.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
export AGENT_CONTROL_PLANE_AUTO_SESSION="${AGENT_CONTROL_PLANE_AUTO_SESSION:-1}"
export AGENT_SESSION_DB="${AGENT_SESSION_DB:-$ROOT/data/sessions.db}"
if [[ -z "${AGENT_API_TOKEN:-}" ]]; then
  echo "Set AGENT_API_TOKEN (min 16 chars) before starting." >&2
  exit 1
fi
HOST="${AGENT_HOST:-0.0.0.0}"
PORT="${AGENT_PORT:-8080}"
exec python3 -m uvicorn agent_core.control_plane.app:app --host "$HOST" --port "$PORT"
