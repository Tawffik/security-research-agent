#!/usr/bin/env bash
# Copy a BugBountyCI export into this agent repo (read-only consumer).
# Does NOT modify the BugBountyCI repository.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-}"
if [[ -z "$SRC" || ! -f "$SRC" ]]; then
  echo "Usage: $0 /path/to/target.live.txt" >&2
  exit 1
fi
DEST_DIR="${AGENT_RECON_DIR:-$ROOT/examples/fixtures/bbci}"
mkdir -p "$DEST_DIR"
BASE="$(basename "$SRC")"
cp -f "$SRC" "$DEST_DIR/$BASE"
echo "Imported (copy only): $DEST_DIR/$BASE"
echo "Restart control plane or call GET /api/artifacts to see it."
