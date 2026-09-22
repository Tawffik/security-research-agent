"""
PoC Minimizer (V2 §44).

After confirmation: smallest reproducible steps that preserve impact,
observability, and evidence linkage. No payload inflation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence


class ObservationLike(Protocol):
    identity: str
    method: str
    path: str
    status: int
    body: str
    notes: str


@dataclass
class PoCStep:
    step: int
    actor: str
    method: str
    path: str
    expected_signal: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "actor": self.actor,
            "method": self.method,
            "path": self.path,
            "expected_signal": self.expected_signal,
            "notes": self.notes,
        }


@dataclass
class MinimizedPoC:
    poc_id: str
    finding_id: str
    title: str
    steps: list[PoCStep] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    impact_preserved: bool = True
    markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "poc_id": self.poc_id,
            "finding_id": self.finding_id,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "evidence_ids": list(self.evidence_ids),
            "impact_preserved": self.impact_preserved,
            "markdown": self.markdown,
        }


class PoCMinimizer:
    """Build a minimal ordered PoC from confirmed authorized observations."""

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._counter = 0

    def minimize(
        self,
        *,
        finding_id: str,
        observations: Sequence[ObservationLike],
        evidence_ids: list[str],
        claim: str = "",
    ) -> Optional[MinimizedPoC]:
        if not finding_id or not evidence_ids or not observations:
            return None

        self._counter += 1
        poc_id = f"POC-{self._counter:03d}"

        ordered = sorted(
            list(observations),
            key=lambda o: (
                0 if o.identity.endswith("_a") or "owner" in o.identity else 1,
                o.identity,
            ),
        )

        steps: list[PoCStep] = []
        for i, obs in enumerate(ordered, start=1):
            body = getattr(obs, "body", "") or ""
            signal = f"HTTP {obs.status}"
            if body:
                snippet = body.replace("\n", " ")[:40]
                signal += f"; body~={snippet!r}"
            if obs.status >= 400:
                notes = "authorization boundary (negative)"
            elif i == 1:
                notes = "baseline owner access"
            else:
                notes = "cross-identity access under test"
            steps.append(
                PoCStep(
                    step=i,
                    actor=obs.identity,
                    method=obs.method,
                    path=obs.path,
                    expected_signal=signal,
                    notes=notes,
                )
            )

        if len(steps) > 4:
            steps = steps[:4]

        title = "Minimal cross-identity object access PoC"
        if claim:
            title = "Minimal PoC — " + (claim[:80])

        lines = [
            f"# {title}",
            "",
            f"**PoC ID:** `{poc_id}`",
            f"**Finding:** `{finding_id}`",
            f"**Evidence:** {', '.join(f'`{e}`' for e in evidence_ids)}",
            "",
            "## Steps",
            "",
        ]
        for s in steps:
            extra = f" ({s.notes})" if s.notes else ""
            lines.append(
                f"{s.step}. As `{s.actor}`: `{s.method} {s.path}` → expect `{s.expected_signal}`{extra}"
            )
        lines.extend(
            [
                "",
                "## Notes",
                "- Ordered for reproducibility; no extra payloads.",
                "- Linked evidence IDs required; lab/fixture unless otherwise marked.",
            ]
        )

        return MinimizedPoC(
            poc_id=poc_id,
            finding_id=finding_id,
            title=title,
            steps=steps,
            evidence_ids=list(evidence_ids),
            impact_preserved=True,
            markdown="\n".join(lines),
        )
