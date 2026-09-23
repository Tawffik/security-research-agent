"""
Surprise Engine (§43).

Unexpected observations become structured research signals:
  expected vs observed → candidate hypotheses / opportunities.

Does not auto-execute new attacks. Quality-first: one surprise →
focused follow-up questions, not payload spray.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class SurpriseEvent:
    surprise_id: str
    expected: str
    observed: str
    context: str
    severity: str  # low | medium | high
    candidate_hypotheses: list[str] = field(default_factory=list)
    suggested_unknowns: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SurpriseEngine:
    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self._n = 0
        self._events: list[SurpriseEvent] = []

    def evaluate_observation(
        self,
        *,
        expected_status: int,
        observed_status: int,
        identity: str = "",
        path: str = "",
        body: str = "",
        expected_denial: bool = False,
    ) -> Optional[SurpriseEvent]:
        """
        Classic authz surprise: expected 403/denial, observed 200 + body.
        Or expected 200 for owner path anomalies later.
        """
        if expected_status == observed_status and not (
            expected_denial and observed_status < 400
        ):
            # no status surprise
            if expected_denial and observed_status < 400:
                pass
            else:
                return None

        surprise = False
        expected_s = f"HTTP {expected_status}"
        observed_s = f"HTTP {observed_status}"
        hyps: list[str] = []
        unknowns: list[str] = []
        severity = "low"

        if expected_denial or expected_status >= 400:
            if observed_status < 400:
                surprise = True
                severity = "high"
                hyps = [
                    "missing object ownership check",
                    "role-only authorization",
                    "cache serving another user's object",
                    "resource intentionally public",
                    "stale session / wrong identity binding",
                ]
                unknowns = [
                    f"Why did {identity or 'actor'} receive {observed_status} on {path or 'resource'} when denial was expected?",
                    "Is the object shared, public, or mis-authorized?",
                ]
        elif expected_status < 400 and observed_status >= 400:
            surprise = True
            severity = "medium"
            hyps = [
                "ownership enforced (secure)",
                "rate limit or WAF",
                "object not found for this identity",
            ]
            unknowns = [
                f"Was denial expected security or incidental error on {path}?",
            ]

        if not surprise:
            return None

        self._n += 1
        ev = SurpriseEvent(
            surprise_id=f"SUR-{self._n:03d}",
            expected=expected_s + (" (denial)" if expected_denial else ""),
            observed=observed_s + (f" body_len={len(body)}" if body else ""),
            context=f"{identity} {path}".strip(),
            severity=severity,
            candidate_hypotheses=hyps,
            suggested_unknowns=unknowns,
            notes="Surprise recorded for research state — not auto-exploited",
        )
        self._events.append(ev)
        return ev

    def from_lab_observations(
        self,
        observations: Sequence[Any],
        *,
        suggests_authz_issue: bool,
    ) -> list[SurpriseEvent]:
        """
        Lab helper: non-owner 200 when authz issue suggested → surprise.
        Non-owner 403 when secure → no high surprise (expected denial).
        """
        events: list[SurpriseEvent] = []
        for obs in observations:
            identity = getattr(obs, "identity", "")
            status = int(getattr(obs, "status", 0))
            path = getattr(obs, "path", "")
            body = getattr(obs, "body", "") or ""
            is_owner = identity.endswith("_a") or "owner" in identity
            if is_owner:
                continue
            # non-owner
            if suggests_authz_issue:
                ev = self.evaluate_observation(
                    expected_status=403,
                    observed_status=status,
                    identity=identity,
                    path=path,
                    body=body,
                    expected_denial=True,
                )
            else:
                # secure lab: expect denial
                ev = self.evaluate_observation(
                    expected_status=403,
                    observed_status=status,
                    identity=identity,
                    path=path,
                    body=body,
                    expected_denial=True,
                )
            if ev:
                events.append(ev)
        return events

    def list_all(self) -> list[SurpriseEvent]:
        return list(self._events)
