"""Independent verification evidence package.

The Skeptic/Verifier receives a structured package — not the researcher's
confidence score. Confidence is never a substitute for evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class EvidencePackage:
    package_id: str
    target: str = ""
    endpoint: str = ""
    parameter: str = ""
    hypothesis_id: str = ""
    hypothesis_statement: str = ""
    expected_security_property: str = ""
    falsification_condition: str = ""
    claim: str = ""
    source_evidence_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    experiment_ids: list[str] = field(default_factory=list)
    counter_evidence_ids: list[str] = field(default_factory=list)
    authorization_context: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    proposed_verdict: str = "candidate"
    researcher_confidence: float = 0.0  # informational only — not decisive

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_verifiable(self) -> bool:
        """Package must carry evidence or explicit counter-evidence to evaluate."""
        return bool(self.source_evidence_ids or self.counter_evidence_ids)


def build_evidence_package(
    *,
    package_id: str,
    hypothesis_id: str,
    hypothesis_statement: str,
    claim: str,
    supporting_evidence_ids: list[str],
    counter_evidence_ids: list[str] | None = None,
    expected_security_property: str = "",
    falsification_condition: str = "",
    target: str = "",
    endpoint: str = "",
    experiment_ids: list[str] | None = None,
    authorization_context: dict | None = None,
    researcher_confidence: float = 0.0,
    proposed_verdict: str = "candidate",
) -> EvidencePackage:
    return EvidencePackage(
        package_id=package_id,
        target=target,
        endpoint=endpoint,
        hypothesis_id=hypothesis_id,
        hypothesis_statement=hypothesis_statement,
        expected_security_property=expected_security_property,
        falsification_condition=falsification_condition,
        claim=claim,
        source_evidence_ids=list(supporting_evidence_ids or []),
        counter_evidence_ids=list(counter_evidence_ids or []),
        experiment_ids=list(experiment_ids or []),
        authorization_context=dict(authorization_context or {}),
        researcher_confidence=float(researcher_confidence or 0.0),
        proposed_verdict=proposed_verdict,
        provenance={"builder": "evidence_package.v1"},
    )
