# Remote Execution Validation — Evidence Log

## Git

- Starting HEAD (reconciled): `7757f00`
- Branch: `feat/sengi-remote-execution-validation`
- Scope: SRA only (BugBountyCI unmodified)

## Components

| Component | Status | Evidence |
|-----------|--------|----------|
| MCP adapters + fail-closed tests | VERIFIED (local) | `tests/test_mcp_adapters.py` |
| Remote scripts | VERIFIED (local syntax/check) | `scripts/remote/*` |
| Workflow YAML committed | VERIFIED | `.github/workflows/remote-execution-validation.yml` |
| Sengi workflow run | PENDING until dispatch succeeds | Requires runner registered for this repo |
| OpenCode on runner | PENDING/optional | workflow input `run_opencode_install` |
| Playwright MCP live process | PENDING package probe | workflow input |
| Burp MCP live | BLOCKED_EXTERNAL | Needs Burp license + GUI/extension on host |
| Android direct connection | BLOCKED_EXTERNAL | Ephemeral runner; use VPS+VPN later |
| Live lab HTTP | BLOCKED_AUTHORIZATION | Gate 6B |

## Local regression

Recorded at implementation time in the same cycle (see commit message / CI logs).
