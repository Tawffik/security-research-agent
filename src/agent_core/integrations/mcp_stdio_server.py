"""
Minimal stdio MCP server exposing only SRA gateway tools.

This is intentionally small: OpenCode can launch it as a local MCP process.
It does not implement the full MCP JSON-RPC stack unless the `mcp` package
is installed; when unavailable it still provides a deterministic CLI probe
mode for Codespaces health checks.

Usage:
  PYTHONPATH=src python3 -m agent_core.integrations.mcp_stdio_server --list-tools
  PYTHONPATH=src python3 -m agent_core.integrations.mcp_stdio_server --call sra_scope_status '{}'
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from agent_core.integrations.mcp_adapters import McpAdapterConfig
from agent_core.integrations.mcp_gateway import (
    SraMcpGateway,
    default_synthetic_pages,
)
from agent_core.scope.guard import ScopeGuard
from agent_core.tools.browser_capability import SyntheticBrowserRuntime


def build_gateway() -> SraMcpGateway:
    root = Path(os.environ.get("AGENT_REPO_ROOT") or Path(__file__).resolve().parents[3])
    scope = Path(os.environ.get("SRA_SCOPE_FILE") or root / "examples" / "demo_program_scope.yaml")
    if not scope.is_absolute():
        scope = root / scope
    enabled = os.environ.get("SRA_MCP_ENABLED", "1") not in ("0", "false", "False")
    guard = ScopeGuard.from_scope_file(scope)
    return SraMcpGateway(
        guard=guard,
        config=McpAdapterConfig(enabled=enabled, live_mode=False),
        browser=SyntheticBrowserRuntime(pages=default_synthetic_pages()),
        engagement_id=os.environ.get("SRA_ENGAGEMENT_ID", "codespace"),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    gw = build_gateway()

    if not argv or argv[0] in ("--list-tools", "list-tools"):
        print(json.dumps({"tools": gw.list_tools()}, indent=2))
        return 0

    if argv[0] in ("--call", "call") and len(argv) >= 2:
        tool = argv[1]
        args: dict[str, Any] = {}
        if len(argv) >= 3:
            args = json.loads(argv[2])
        result = gw.call(tool, args)
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return 0 if result.ok else 2

    if argv[0] in ("--stdio", "stdio"):
        # Best-effort: if mcp SDK present, run a real server; else refuse clearly.
        try:
            from mcp.server.fastmcp import FastMCP  # type: ignore
        except Exception:
            print(
                json.dumps(
                    {
                        "error": "mcp_sdk_unavailable",
                        "hint": "pip install mcp; or use --list-tools / --call for probe mode",
                        "tools": gw.list_tools(),
                    }
                ),
                file=sys.stderr,
            )
            return 1

        app = FastMCP("sra-gateway")

        @app.tool()
        def sra_scope_status(host: str = "", url: str = "") -> dict:
            return gw.call("sra_scope_status", {"host": host, "url": url}).to_dict()

        @app.tool()
        def sra_browser_navigate(url: str, experiment_id: str = "", identity: str = "") -> dict:
            return gw.call(
                "sra_browser_navigate",
                {"url": url, "experiment_id": experiment_id, "identity": identity},
            ).to_dict()

        @app.tool()
        def sra_browser_snapshot(url: str = "", experiment_id: str = "") -> dict:
            return gw.call(
                "sra_browser_snapshot",
                {"url": url, "experiment_id": experiment_id},
            ).to_dict()

        @app.tool()
        def sra_browser_interact(
            action: str = "click",
            selector: str = "",
            value: str = "",
            url: str = "",
            experiment_id: str = "",
        ) -> dict:
            return gw.call(
                "sra_browser_interact",
                {
                    "action": action,
                    "selector": selector,
                    "value": value,
                    "url": url,
                    "experiment_id": experiment_id,
                },
            ).to_dict()

        @app.tool()
        def sra_burp_send_request(url: str, method: str = "GET", experiment_id: str = "") -> dict:
            return gw.call(
                "sra_burp_send_request",
                {"url": url, "method": method, "experiment_id": experiment_id},
            ).to_dict()

        @app.tool()
        def sra_burp_history_read(host_filter: str = "") -> dict:
            return gw.call("sra_burp_history_read", {"host_filter": host_filter}).to_dict()

        app.run(transport="stdio")
        return 0

    print(
        "usage: python -m agent_core.integrations.mcp_stdio_server "
        "[--list-tools | --call TOOL JSON | --stdio]",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
