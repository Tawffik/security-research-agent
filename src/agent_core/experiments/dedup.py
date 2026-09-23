"""
Semantic-ish deduplication for experiments/hypotheses (§68 partial).

Exact key match on normalized identity+endpoint+action+hypothesis.
Prevents repeating equivalent lab experiments without justification.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional, Set


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def experiment_fingerprint(
    *,
    method: str = "",
    path: str = "",
    identity: str = "",
    hypothesis_id: str = "",
    action: str = "",
) -> str:
    raw = "|".join(
        [
            _norm(method),
            _norm(path),
            _norm(identity),
            _norm(hypothesis_id),
            _norm(action)[:120],
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ExperimentDeduper:
    seen: Set[str] = field(default_factory=set)

    def seen_before(self, fp: str) -> bool:
        return fp in self.seen

    def register(self, fp: str) -> bool:
        """Return True if newly registered, False if duplicate."""
        if fp in self.seen:
            return False
        self.seen.add(fp)
        return True

    def check_and_register(
        self,
        *,
        method: str = "",
        path: str = "",
        identity: str = "",
        hypothesis_id: str = "",
        action: str = "",
    ) -> tuple[str, bool]:
        fp = experiment_fingerprint(
            method=method,
            path=path,
            identity=identity,
            hypothesis_id=hypothesis_id,
            action=action,
        )
        return fp, self.register(fp)
