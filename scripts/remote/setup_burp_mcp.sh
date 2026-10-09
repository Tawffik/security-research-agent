#!/usr/bin/env bash
# Official PortSwigger Burp MCP prerequisites. https://github.com/PortSwigger/mcp-server
set -euo pipefail
MODE="${1:---check}"
case "$MODE" in
  --check)
    echo "=== Burp MCP prerequisites ==="
    if command -v java >/dev/null 2>&1; then java -version 2>&1 | head -1; else echo "java: MISSING"; fi
    echo "Burp Suite must be installed on the VPS (Pro recommended)."
    echo "Extension: BApp Store MCP Server or build from PortSwigger/mcp-server"
    echo "Default listen: http://127.0.0.1:9876 — keep loopback"
    ;;
  --help)
    echo "1. Install Burp on VPS"
    echo "2. BApp Store: MCP Server (PortSwigger) OR ./gradlew embedProxyJar"
    echo "3. MCP tab: Enabled on 127.0.0.1:9876"
    echo "4. Client uses SSE or stdio proxy from extension"
    echo "5. Never public expose; SRA ScopeGuard still gates requests"
    ;;
  *)
    echo "usage: $0 --check | --help" >&2
    exit 2
    ;;
esac
