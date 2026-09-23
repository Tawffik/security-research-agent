"""
Differential observation compare (§48) — identity A vs B (lab).

Compares status/body markers; does not send network requests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class DifferentialResult:
    baseline_identity: str
    compare_identity: str
    baseline_status: int
    compare_status: int
    status_differs: bool
    body_differs: bool
    same_object_path: bool
    interpretation: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_identity_pair(
    baseline: Any,
    other: Any,
    *,
    expect_denial_for_other: bool = True,
) -> DifferentialResult:
    b_status = int(getattr(baseline, "status", 0))
    o_status = int(getattr(other, "status", 0))
    b_body = getattr(baseline, "body", "") or ""
    o_body = getattr(other, "body", "") or ""
    b_path = getattr(baseline, "path", "") or ""
    o_path = getattr(other, "path", "") or ""
    same_path = b_path == o_path
    status_differs = b_status != o_status
    body_differs = b_body.strip() != o_body.strip()

    notes: list[str] = []
    if expect_denial_for_other:
        if o_status < 400 and b_status < 400 and not status_differs:
            interpretation = "possible_authorization_issue"
            notes.append("non-baseline identity received success similar to baseline")
        elif o_status >= 400 and b_status < 400:
            interpretation = "ownership_or_authz_appears_enforced"
            notes.append("compare identity denied while baseline succeeded")
        else:
            interpretation = "inconclusive"
            notes.append("status pattern does not clearly separate ownership enforcement")
    else:
        interpretation = "raw_differential"
        notes.append("no enforcement expectation applied")

    return DifferentialResult(
        baseline_identity=getattr(baseline, "identity", ""),
        compare_identity=getattr(other, "identity", ""),
        baseline_status=b_status,
        compare_status=o_status,
        status_differs=status_differs,
        body_differs=body_differs,
        same_object_path=same_path,
        interpretation=interpretation,
        notes=notes,
    )


def compare_lab_observations(observations: Sequence[Any]) -> Optional[DifferentialResult]:
    if len(observations) < 2:
        return None
    # prefer *_a as baseline
    ordered = sorted(
        list(observations),
        key=lambda o: (0 if str(getattr(o, "identity", "")).endswith("_a") else 1),
    )
    return compare_identity_pair(ordered[0], ordered[1])
