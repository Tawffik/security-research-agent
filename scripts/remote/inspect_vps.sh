#!/usr/bin/env bash
# Read-only VPS / host inspection. Does not print secrets.
set -euo pipefail
echo "=== SRA remote inspect $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "hostname: $(hostname 2>/dev/null || echo unknown)"
echo "kernel: $(uname -srm 2>/dev/null || true)"
echo "arch: $(uname -m 2>/dev/null || true)"
command -v free >/dev/null 2>&1 && free -h | head -2 || true
command -v df >/dev/null 2>&1 && df -h / | tail -1 || true
echo "--- runtimes ---"
command -v java >/dev/null 2>&1 && java -version 2>&1 | head -1 || echo "java: missing"
command -v node >/dev/null 2>&1 && node -v || echo "node: missing"
command -v npm >/dev/null 2>&1 && npm -v || echo "npm: missing"
command -v python3 >/dev/null 2>&1 && python3 -V || echo "python3: missing"
command -v opencode >/dev/null 2>&1 && opencode --version 2>&1 | head -1 || echo "opencode: missing"
command -v npx >/dev/null 2>&1 && echo "npx: present" || echo "npx: missing"
echo "--- browsers ---"
found=0
for b in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$b" >/dev/null 2>&1; then echo "browser: $b"; found=1; break; fi
done
[ "$found" = 0 ] && echo "browser: none found"
echo "DISPLAY=${DISPLAY:-unset}"
echo "=== inspect complete ==="
