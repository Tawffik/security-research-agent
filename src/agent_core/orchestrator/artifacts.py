"""
Engagement artifact writer (§85) — lab/offline subset.

Writes versionable JSON under a directory; does not claim production BBCI layout completeness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def write_engagement_artifacts(
    directory: Path,
    *,
    engagement_id: str,
    closed: Any,
    adaptive: Any = None,
    checkpoint: Any = None,
    regrets: Optional[list[Any]] = None,
    surprises: Optional[list[Any]] = None,
    memory_entries: Optional[list[Any]] = None,
    claim_matrix: Any = None,
    invariant_checks: Optional[list[Any]] = None,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def dump(name: str, obj: Any) -> Path:
        path = directory / name
        path.write_text(json.dumps(obj, indent=2, default=str))
        written[name] = path
        return path

    dump(
        "engagement.json",
        {
            "engagement_id": engagement_id,
            "mode": "lab_fixture",
            "limitations": list(getattr(closed, "limitations", None) or []),
        },
    )

    if closed.plan is not None:
        ctx = getattr(closed.plan, "target_context", None)
        if ctx is not None and hasattr(ctx, "model_dump"):
            dump("target_context.json", ctx.model_dump())
        graph = getattr(closed.plan, "target_graph", None)
        if graph is not None and hasattr(graph, "model_dump"):
            dump("target_graph.json", graph.model_dump())
        hyps = getattr(closed.plan, "hypotheses", None) or []
        dump(
            "hypotheses.json",
            [h.model_dump() if hasattr(h, "model_dump") else str(h) for h in hyps],
        )

    dump(
        "evidence.json",
        {"evidence_ids": list(closed.evidence_ids or []), "finding_id": closed.finding_id},
    )

    if closed.report is not None:
        dump("report.json", closed.report.to_dict())
        (directory / "final-report.md").write_text(closed.report.markdown or "")
        written["final-report.md"] = directory / "final-report.md"

    if closed.poc is not None:
        poc_dir = directory / "poc"
        poc_dir.mkdir(exist_ok=True)
        (poc_dir / "minimal.json").write_text(json.dumps(closed.poc.to_dict(), indent=2))
        written["poc/minimal.json"] = poc_dir / "minimal.json"

    if closed.root_cause is not None:
        dump("root_cause.json", closed.root_cause.to_dict())

    if closed.variants:
        dump("variants.json", [v.to_dict() for v in closed.variants])

    if adaptive is not None:
        dump("adaptive.json", adaptive.to_dict())

    if checkpoint is not None:
        dump("checkpoint.json", checkpoint.to_dict())

    if regrets:
        dump("action_regret.json", [r.to_dict() for r in regrets])

    if surprises:
        dump("surprises.json", [s.to_dict() for s in surprises])

    if memory_entries:
        dump("memory_episodic.json", [e.to_dict() for e in memory_entries])

    if claim_matrix is not None:
        dump("claim_evidence_matrix.json", claim_matrix.to_dict())

    if invariant_checks:
        dump("invariant_checks.json", [c.to_dict() for c in invariant_checks])

    if closed.episode is not None:
        dump("episode.json", closed.episode.to_dict())

    return written
