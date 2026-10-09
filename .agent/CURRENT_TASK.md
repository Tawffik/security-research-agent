# Current Task

**Campaign:** IN_PROGRESS
**Focus:** Codespaces + SRA MCP gateway executable path (no VPS)

## Completed this cycle
- SraMcpGateway: authorize → SyntheticBrowserRuntime execute
- Allowlist tools: sra_scope_status / browser_* / burp_*
- Fail-closed: unknown tool, OOS, live_mode, budget, privilege keys, redirect OOS
- mcp_stdio_server probe (--list-tools / --call / optional --stdio)
- OpenCode example config uses `mcp` schema; raw Playwright/Burp disabled
- Tests: 13 gateway + prior adapters; full suite 448 passed / 8 skipped

## Still blocked (external/human)
- OpenCode install + model provider auth inside a live Codespace
- Burp Community/Pro + PortSwigger MCP extension (GUI/license)
- Real Playwright MCP process handshake (optional; synthetic path VERIFIED)
- Gate 6B live authorized target

## Next resume
User: open Codespace → run mcp_stdio_server probe → optional install OpenCode + provider key in Codespaces secrets
