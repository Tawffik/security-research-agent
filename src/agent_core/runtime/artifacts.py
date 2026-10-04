"""Discover recon artifacts the control plane may consume (read-only).

BugBountyCI remains an external producer — we only read exported files
(e.g. live.txt / JSON) from configured directories. We never modify BBCI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    env = os.environ.get("AGENT_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def artifact_search_dirs() -> list[Path]:
    root = _repo_root()
    dirs = [
        root / "examples" / "fixtures",
        root / "examples" / "fixtures" / "bbci",
    ]
    extra = os.environ.get("AGENT_RECON_DIR", "").strip()
    if extra:
        dirs.append(Path(extra).resolve())
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen and d.is_dir():
            seen.add(key)
            out.append(d)
    return out


def list_recon_artifacts() -> list[dict[str, Any]]:
    """Return selectable recon + paired scope hints for the mobile UI."""
    items: list[dict[str, Any]] = []
    for d in artifact_search_dirs():
        for p in sorted(d.iterdir()):
            if not p.is_file():
                continue
            suf = p.suffix.lower()
            if suf not in (".txt", ".json"):
                continue
            kind = "bbci_live_txt" if suf == ".txt" else "recon_json"
            scope_hint = ""
            if kind == "bbci_live_txt":
                # common pairing: same stem or oneplus_offline_scope.yaml nearby
                for cand in (
                    p.with_name(p.stem.replace(".live", "") + "_offline_scope.yaml"),
                    p.with_name(p.stem + "_offline_scope.yaml"),
                    p.parent / "oneplus_offline_scope.yaml",
                ):
                    if cand.is_file():
                        scope_hint = str(cand)
                        break
            elif kind == "recon_json":
                root = _repo_root()
                default_scope = root / "examples" / "demo_program_scope.yaml"
                if default_scope.is_file():
                    scope_hint = str(default_scope)
            items.append(
                {
                    "id": p.name,
                    "path": str(p.resolve()),
                    "kind": kind,
                    "scope_hint": scope_hint,
                    "label": f"{kind}: {p.name}",
                }
            )
    return items


def resolve_recon_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_file():
        return p.resolve()
    # relative to repo
    cand = _repo_root() / path_str
    if cand.is_file():
        return cand.resolve()
    raise FileNotFoundError(path_str)
