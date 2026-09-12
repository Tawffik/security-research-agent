"""
Phase-A engagement runner.

Wires EngagementOrchestrator against the demo scope file and mock transport.
No live network. Demonstrates:

  ScopeGuard → Ledger (auth session + budget) → Skills → Content Isolation
  → EvidenceStore → VerificationLoop → optional report skill

Run:
  python examples/run_engagement.py
  python examples/run_engagement.py --skip authz-idor-analysis
  python examples/run_engagement.py --reject H-idor-invoices
  python examples/run_engagement.py --live-http   # authorized targets only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.orchestrator import EngagementConfig, EngagementOrchestrator

ROOT = Path(__file__).parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Phase-A mock engagement")
    parser.add_argument(
        "--scope",
        type=Path,
        default=ROOT / "examples" / "demo_program_scope.yaml",
        help="Path to program scope YAML",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data" / "engagements",
        help="Directory for ledger/evidence SQLite files",
    )
    parser.add_argument(
        "--host",
        default="api.acme-demo.test",
        help="Primary in-scope host",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Live steering: skip a skill by name (repeatable)",
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        help="Live steering: reject a hypothesis id (repeatable)",
    )
    parser.add_argument(
        "--engagement-id",
        default="engagement-demo",
        help="Id used as SQLite filename prefix",
    )
    parser.add_argument(
        "--live-http",
        action="store_true",
        help=(
            "Use HttpTransport against primary_host. "
            "AUTHORIZED RESEARCH ONLY — host must pass ScopeGuard."
        ),
    )
    parser.add_argument(
        "--http-scheme",
        default="https",
        choices=["https", "http"],
        help="Scheme for live HTTP (default https)",
    )
    args = parser.parse_args(argv)

    steering = [f"skip:{s}" for s in args.skip] + [f"reject:{r}" for r in args.reject]

    config = EngagementConfig(
        scope_path=args.scope,
        skills_dir=ROOT / "skills",
        data_dir=args.data_dir,
        primary_host=args.host,
        steering=steering,
        engagement_id=args.engagement_id,
        use_live_http=args.live_http,
        http_scheme=args.http_scheme,
    )

    print("=" * 70)
    print("EngagementOrchestrator — Phase A")
    print("=" * 70)
    print(f"scope:     {config.scope_path}")
    print(f"host:      {config.primary_host}")
    print(f"steering:  {config.steering or '(none)'}")
    transport_name = "HttpTransport" if config.use_live_http else "MockTransport"
    print(f"transport: {transport_name}")
    print()

    orch = EngagementOrchestrator(config)
    result = orch.run()

    print("skills run:     ", result.skills_run)
    print("skills skipped: ", result.skills_skipped)
    print("accepted:       ", result.accepted)
    print("finding_id:     ", result.finding_id)
    print("final_status:   ", result.final_status)
    print("reason:         ", result.reason)
    print("chain valid:    ", result.evidence_chain_valid)
    print("unresolved:     ", result.unresolved_nodes)
    print("budget:         ", result.budget)
    print("audit log:      ", result.audit_log_path)
    print()
    print("Done.")
    return 0 if result.evidence_chain_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
