"""
Gate 3 — Generic knowledge-driven research contracts.

[NOTION REQUIREMENT] One engine consumes different KnowledgeObjects.
No per-methodology research engines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class KnowledgeResearchContract:
    """Normalized ingredients the generic engine can consume from retrieval."""

    property: str = ""
    pattern_ids: list[str] = field(default_factory=list)
    procedure_ids: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    negative_ids: list[str] = field(default_factory=list)
    tip_ids: list[str] = field(default_factory=list)
    competing_explanations: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    experiment_steps: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def contract_from_retrieval(retrieval: Any, *, property_hint: str = "") -> KnowledgeResearchContract:
    """Build a generic contract from RetrievalResult — methodology-agnostic."""
    if retrieval is None:
        return KnowledgeResearchContract(property=property_hint)

    evidence_req: list[str] = []
    steps: list[str] = []
    preconds: list[str] = []
    for proc in getattr(retrieval, "procedures", None) or []:
        evidence_req.extend(list(getattr(proc, "evidence_required", None) or []))
        steps.extend(list(getattr(proc, "experiment_steps", None) or []))
        # preconditions may appear as tags or abstract text
        for t in getattr(proc, "tags", None) or []:
            if t.lower() in ("precondition", "requires", "multi-identity"):
                preconds.append(t)

    prop = property_hint
    if not prop:
        for p in getattr(retrieval, "patterns", None) or []:
            if getattr(p, "security_property", None):
                prop = (p.security_property or "").split("/")[0].strip()
                break
        if not prop:
            for p in getattr(retrieval, "procedures", None) or []:
                if getattr(p, "domain", None):
                    prop = p.domain
                    break

    return KnowledgeResearchContract(
        property=prop or "",
        pattern_ids=list(getattr(retrieval, "pattern_ids", None) or []),
        procedure_ids=list(getattr(retrieval, "procedure_ids", None) or []),
        case_ids=[c.record_id for c in (getattr(retrieval, "cases", None) or [])],
        negative_ids=[n.record_id for n in (getattr(retrieval, "negatives", None) or [])],
        tip_ids=[t.record_id for t in (getattr(retrieval, "tips", None) or [])],
        competing_explanations=list(getattr(retrieval, "competing_explanations", None) or []),
        evidence_requirements=list(dict.fromkeys(evidence_req)),
        experiment_steps=list(dict.fromkeys(steps)),
        preconditions=list(dict.fromkeys(preconds)),
        provenance=list(getattr(retrieval, "provenance", None) or []),
    )


@dataclass
class ExperimentContractView:
    """Explainable view of what a discriminating experiment must carry."""

    experiment_id: str
    hypothesis_id: str
    preconditions: list[str] = field(default_factory=list)
    baseline: str = ""
    controlled_mutation: str = ""
    expected_observations: list[str] = field(default_factory=list)
    alternative_predictions: list[str] = field(default_factory=list)
    discriminator: str = ""
    evidence_requirements: list[str] = field(default_factory=list)
    stop_condition: str = ""
    next_test_policy: str = ""
    knowledge_procedure_ids: list[str] = field(default_factory=list)
    knowledge_pattern_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def experiment_contract_view(exp: Any, *, procedure_ids: list[str] | None = None) -> ExperimentContractView:
    """Map existing Experiment fields into Gate 3 contract view (no redesign)."""
    steps = list(getattr(exp, "steps", None) or [])
    baseline = ""
    mutation = ""
    for s in steps:
        role = getattr(s, "role", "") or ""
        text = getattr(s, "text", "") or getattr(s, "description", "") or ""
        if role == "baseline" and not baseline:
            baseline = text
        if role == "challenge" and not mutation:
            mutation = text
    return ExperimentContractView(
        experiment_id=getattr(exp, "experiment_id", "") or "",
        hypothesis_id=getattr(exp, "hypothesis_id", "") or "",
        preconditions=list(getattr(exp, "preconditions", None) or []),
        baseline=baseline or (getattr(exp, "description", "") or "")[:120],
        controlled_mutation=mutation,
        expected_observations=list(getattr(exp, "required_evidence", None) or []),
        alternative_predictions=[],
        discriminator=getattr(exp, "discriminator", "") or "",
        evidence_requirements=list(getattr(exp, "required_evidence", None) or []),
        stop_condition=getattr(exp, "stop_condition", "") or "",
        next_test_policy="prefer_untried_discriminating",
        knowledge_procedure_ids=list(procedure_ids or []),
        knowledge_pattern_ids=[],
    )
