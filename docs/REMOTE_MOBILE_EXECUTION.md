# Remote Mobile Execution (VPS + OpenCode + MCP)

## Architecture

```
Android phone (control)
  -> private VPN / Tailscale
  -> VPS
       OpenCode server   127.0.0.1:4096
       SRA control plane 8080 (optional)
       Playwright MCP    127.0.0.1:8931
       Burp MCP          127.0.0.1:9876 (PortSwigger official)
         -> Security Research Agent (ScopeGuard + evidence)
```

BugBountyCI remains a separate recon producer.

## Defaults

- MCP adapters disabled; live_mode false
- No public bind
- Tool output cannot grant permissions
- Page/Burp content is untrusted observation

## Scripts

- `scripts/remote/inspect_vps.sh`
- `scripts/remote/setup_opencode.sh` (`--check|--install|--serve-help`)
- `scripts/remote/setup_playwright.sh` (`--check|--install|--mcp-help`)
- `scripts/remote/setup_burp_mcp.sh` (`--check|--help`)
- `scripts/remote/healthcheck.sh`

## OpenCode

https://opencode.ai/docs/server/

```bash
./scripts/remote/setup_opencode.sh --install
OPENCODE_SERVER_PASSWORD='...' opencode serve --hostname 127.0.0.1 --port 4096
```

## Playwright MCP

https://playwright.dev/docs/getting-started-mcp

```bash
npx @playwright/mcp@latest --headless --port 8931
```

## Burp MCP

https://github.com/PortSwigger/mcp-server

BApp Store or build JAR; enable on 127.0.0.1:9876.

## SRA

`agent_core.integrations.mcp_adapters.authorize_mcp_action` — authorize only; does not auto-execute live traffic.
