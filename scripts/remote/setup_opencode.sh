#!/usr/bin/env bash
# OpenCode check/install + loopback serve guidance. Official: https://opencode.ai/docs/
set -euo pipefail
MODE="${1:---check}"
case "$MODE" in
  --check)
    if command -v opencode >/dev/null 2>&1; then
      echo "opencode: installed"
      opencode --version 2>/dev/null | head -1 || true
      exit 0
    fi
    echo "opencode: not installed"
    exit 1
    ;;
  --install)
    if command -v opencode >/dev/null 2>&1; then echo "opencode already present"; exit 0; fi
    if command -v npm >/dev/null 2>&1; then
      npm install -g opencode-ai@latest
    else
      echo "Need Node.js 20+. Or: curl -fsSL https://opencode.ai/install | bash" >&2
      exit 1
    fi
    command -v opencode >/dev/null 2>&1 || { echo "install failed" >&2; exit 1; }
    echo "opencode install ok"
    ;;
  --serve-help)
    echo "OPENCODE_SERVER_PASSWORD=... opencode serve --hostname 127.0.0.1 --port 4096"
    echo "Health: curl -s http://127.0.0.1:4096/global/health"
    echo "Do not bind 0.0.0.0 publicly. Use Tailscale/private VPN for Android."
    ;;
  *)
    echo "usage: $0 --check | --install | --serve-help" >&2
    exit 2
    ;;
esac
