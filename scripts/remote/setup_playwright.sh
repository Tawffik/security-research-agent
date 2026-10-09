#!/usr/bin/env bash
# Python Playwright extra + official Microsoft Playwright MCP guidance.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="${1:---check}"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
case "$MODE" in
  --check)
    python3 -c "from agent_core.tools.browser_health import check_browser_health; h=check_browser_health(try_launch=False); print(h.status, h.detail); raise SystemExit(0 if h.playwright else 1)"
    ;;
  --install)
    python3 -m pip install -q -e ".[browser]" --index-url https://pypi.org/simple 2>/dev/null || python3 -m pip install -q -e ".[browser]"
    python3 -m playwright install chromium 2>/dev/null || true
    echo "playwright python extra installed"
    ;;
  --mcp-help)
    echo "npx @playwright/mcp@latest --headless --port 8931"
    echo "Endpoint: http://127.0.0.1:8931/mcp"
    echo "Template: config/remote/opencode-mcp.example.json"
    echo "Docs: https://playwright.dev/docs/getting-started-mcp"
    ;;
  *)
    echo "usage: $0 --check | --install | --mcp-help" >&2
    exit 2
    ;;
esac
