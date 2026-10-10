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

## Sengi GitHub Actions validation

Manual workflow (ephemeral runner, not a persistent VPS):

```
Actions → Remote Execution Validation → Run workflow
```

File: `.github/workflows/remote-execution-validation.yml`  
Runner label: `sengi-standard-2-ubuntu-2404`  
Permissions: contents read only.

What it verifies:
- Runner diagnostics (OS, CPU, memory, Node, Python, Java, Chrome)
- Remote script syntax + check mode
- MCP adapter unit tests (fail-closed)
- Full pytest suite
- Optional OpenCode install + loopback health (input flag)
- Optional Playwright MCP package probe (input flag)
- Burp prerequisites only (no licensed Burp assumed)

What it does **not** prove:
- Persistent OpenCode/Burp daemons
- Public inbound access
- Android device connected to a live server
- Live authorized target testing

Artifacts: `remote-execution-validation-<run_id>` (sanitized logs).

### Android control on ephemeral runners

| Capability | Status |
|------------|--------|
| Trigger workflow from phone (GitHub app/web) | Supported by GitHub product |
| View logs/artifacts from phone | Supported by GitHub product |
| Connect phone to OpenCode on runner mid-job | Not reliable — runner is ephemeral and typically not inbound-reachable |
| Persistent remote session | Requires a real VPS/host + private VPN (Tailscale), not Actions |

### Temporary session vs persistent server

| | Sengi Actions job | Persistent VPS |
|--|-------------------|----------------|
| Lifetime | Minutes–hours, then destroyed | Continuous |
| Inbound | Usually none | Private VPN only |
| Suitable for | CI validation, offline tests | Mobile interactive control |

## Execution evidence (repo cycle)

See `docs/REMOTE_EXECUTION_EVIDENCE.md` for the latest commit/test matrix.
