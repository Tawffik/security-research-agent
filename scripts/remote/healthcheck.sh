#!/usr/bin/env bash
# Loopback health probes for remote stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
echo "=== SRA remote health $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
python3 -c "from agent_core.integrations.mcp_adapters import list_mcp_contracts, McpAdapterConfig; print('mcp_contracts', len(list_mcp_contracts())); print('enabled', McpAdapterConfig().enabled); print('live', McpAdapterConfig().live_mode)"
for pair in "control_plane:8080:/health" "opencode:4096:/global/health"; do
  name="${pair%%:*}"; rest="${pair#*:}"; port="${rest%%:*}"; path="${rest#*:}"
  if curl -sf "http://127.0.0.1:${port}${path}" >/dev/null 2>&1; then echo "$name: UP"; else echo "$name: down"; fi
done
for pair in "playwright_mcp:8931" "burp_mcp:9876"; do
  name="${pair%%:*}"; port="${pair#*:}"
  if curl -sf "http://127.0.0.1:${port}/mcp" >/dev/null 2>&1; then echo "$name: probe ok"; else echo "$name: down"; fi
done
echo "=== health done ==="
