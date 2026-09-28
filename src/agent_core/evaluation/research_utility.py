"""
Research-utility A/B benchmark: does knowledge change research decisions?

Oracle is evaluation-only. Never passed into ResearchLoop / ClosedLoopRunner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from agent_core.knowledge.index import KnowledgeIndex, KnowledgeRecord
from agent_core.knowledge.retrieve import KnowledgeRetriever
from agent_core.orchestrator.closed_loop import (
    ClosedLoopResult,
    ClosedLoopRunner,
    LabScenario,
    default_idor_lab_scenario,
    public_resource_lab_scenario,
    secure_lab_scenario,
    shared_object_lab_scenario,
)


class KnowledgeCondition(str, Enum):
    NONE = "none"
    CURATED = "curated"
    GENERATED = "generated"
    CURATED_PLUS_GENERATED = "curated_plus_generated"
    IRRELEVANT = "irrelevant"


@dataclass
class ScenarioSpec:
    scenario_id: str
    factory: str
    # Hidden from agent
    ground_truth: str  # vulnerable | secure | public | shared | ambiguous
    expected_outcome: str  # confirmed | rejected | incomplete


@dataclass
class InfluenceTrace:
    condition: str
    scenario_id: str
    knowledge_ids_retrieved: list[str] = field(default_factory=list)
    hyp_mode: str = ""
    hyp_ids: list[str] = field(default_factory=list)
    hyp_statements: list[str] = field(default_factory=list)
    procedure_ids: list[str] = field(default_factory=list)
    selected_experiment_id: str = ""
    experiment_description: str = ""
    knowledge_driven_experiment: bool = False
    agent_outcome: str = ""
    referee_accepted: bool = False
    evidence_count: int = 0
    n_experiments_designed: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UtilityMetrics:
    condition: str
    scenario_id: str
    true_positive: bool = False
    true_negative: bool = False
    false_positive: bool = False
    false_negative: bool = False
    knowledge_retrieved: bool = False
    knowledge_changed_hyp_mode: bool = False
    knowledge_changed_experiment: bool = False
    retrieval_had_effect: bool = False
    irrelevant_contamination: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_SCENARIOS = [
    ScenarioSpec("pos_authz", "default_idor", "vulnerable", "confirmed"),
    ScenarioSpec("secure_authz", "secure", "secure", "rejected"),
    ScenarioSpec("public_res", "public", "public", "rejected"),
    ScenarioSpec("shared_res", "shared", "shared", "rejected"),
]


def _scenario(name: str) -> LabScenario:
    if name == "default_idor":
        return default_idor_lab_scenario()
    if name == "secure":
        return secure_lab_scenario()
    if name == "public":
        return public_resource_lab_scenario()
    if name == "shared":
        return shared_object_lab_scenario()
    raise ValueError(name)


def _irrelevant_record() -> KnowledgeRecord:
    return KnowledgeRecord(
        record_id="IRR-9999-css-padding",
        kind="pattern",
        title="Irrelevant CSS padding pattern",
        domain="ui",
        path="generated://irrelevant",
        security_property="ui_layout",
        abstraction="CSS padding does not affect object-level authorization",
        tags=["irrelevant", "ui", "noise"],
        provenance={"origin": "benchmark_irrelevant", "untrusted": True},
    )


class EmptyKnowledgeIndex(KnowledgeIndex):
    def load(self) -> "EmptyKnowledgeIndex":
        self.records.clear()
        self.by_id.clear()
        return self


def build_retriever(
    condition: KnowledgeCondition,
    knowledge_root: Path,
) -> KnowledgeRetriever:
    if condition == KnowledgeCondition.NONE:
        idx = EmptyKnowledgeIndex(knowledge_root).load()
        return KnowledgeRetriever(idx)

    if condition == KnowledgeCondition.CURATED:
        return KnowledgeRetriever(KnowledgeIndex(knowledge_root).load())

    if condition == KnowledgeCondition.GENERATED:
        from agent_core.knowledge.registry import KnowledgeRegistry

        reg = KnowledgeRegistry(knowledge_root)
        idx = EmptyKnowledgeIndex(knowledge_root).load()
        # only generated overlay
        full = reg.load_with_generated()
        for r in full.records:
            if "generated_candidate" in (r.tags or []) or str(r.path).startswith(
                "generated://"
            ):
                idx.records.append(r)
                idx.by_id[r.record_id.upper()] = r
        return KnowledgeRetriever(idx)

    if condition == KnowledgeCondition.CURATED_PLUS_GENERATED:
        from agent_core.knowledge.registry import KnowledgeRegistry

        return KnowledgeRetriever(
            KnowledgeRegistry(knowledge_root).load_with_generated()
        )

    if condition == KnowledgeCondition.IRRELEVANT:
        idx = EmptyKnowledgeIndex(knowledge_root).load()
        irr = _irrelevant_record()
        idx.records.append(irr)
        idx.by_id[irr.record_id.upper()] = irr
        return KnowledgeRetriever(idx)

    raise ValueError(condition)


def _outcome(result: ClosedLoopResult) -> str:
    if not result.scope_allowed:
        return "scope_denied"
    if result.referee_accepted:
        return "confirmed"
    if result.final_status == "rejected":
        return "rejected"
    return result.final_status or "incomplete"


def run_condition(
    *,
    condition: KnowledgeCondition,
    scenario: ScenarioSpec,
    recon_path: Path,
    scope_path: Path,
    knowledge_root: Path,
    engagement_suffix: str = "",
) -> tuple[InfluenceTrace, UtilityMetrics, ClosedLoopResult]:
    retriever = build_retriever(condition, knowledge_root)
    eng = f"util_{condition.value}_{scenario.scenario_id}{engagement_suffix}"
    runner = ClosedLoopRunner(
        scope_path=scope_path,
        engagement_id=eng,
        knowledge_retriever=retriever,
    )
    result = runner.run(recon_path, scenario=_scenario(scenario.factory))

    hyp_engine = runner.research.hypothesis_engine
    designer = runner.research.experiment_designer
    retrieval = runner.research.last_retrieval

    kid: list[str] = []
    if retrieval:
        kid = list(retrieval.pattern_ids or []) + list(retrieval.procedure_ids or [])

    exp = None
    if result.selected_experiment_id and result.plan.experiments:
        for e in result.plan.experiments:
            if e.experiment_id == result.selected_experiment_id:
                exp = e
                break
        if exp is None and result.plan.experiments:
            exp = result.plan.experiments[0]

    knowledge_driven_exp = bool(designer.last_procedure_ids) or (
        exp is not None and "procedure:" in (exp.discriminator or "")
    )

    trace = InfluenceTrace(
        condition=condition.value,
        scenario_id=scenario.scenario_id,
        knowledge_ids_retrieved=kid,
        hyp_mode=getattr(hyp_engine, "last_mode", "") or "",
        hyp_ids=[h.hypothesis_id for h in (result.plan.hypotheses or [])],
        hyp_statements=[(h.statement or "")[:120] for h in (result.plan.hypotheses or [])],
        procedure_ids=list(getattr(designer, "last_procedure_ids", None) or []),
        selected_experiment_id=result.selected_experiment_id or "",
        experiment_description=(exp.description if exp else "")[:200],
        knowledge_driven_experiment=knowledge_driven_exp,
        agent_outcome=_outcome(result),
        referee_accepted=bool(result.referee_accepted),
        evidence_count=len(result.evidence_ids or []),
        n_experiments_designed=len(result.plan.experiments or []),
        notes=[
            f"hyp_mode={getattr(hyp_engine, 'last_mode', '')}",
            f"retrieved={kid[:5]}",
        ],
    )

    # Oracle evaluation (outside agent)
    gt = scenario.ground_truth
    outcome = trace.agent_outcome
    tp = gt == "vulnerable" and outcome == "confirmed"
    tn = gt != "vulnerable" and outcome in ("rejected", "incomplete")
    fp = gt != "vulnerable" and outcome == "confirmed"
    fn = gt == "vulnerable" and outcome != "confirmed"

    hyp_knowledge = trace.hyp_mode == "knowledge_driven"
    metrics = UtilityMetrics(
        condition=condition.value,
        scenario_id=scenario.scenario_id,
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        knowledge_retrieved=bool(kid),
        knowledge_changed_hyp_mode=hyp_knowledge,
        knowledge_changed_experiment=knowledge_driven_exp,
        retrieval_had_effect=hyp_knowledge or knowledge_driven_exp,
        irrelevant_contamination=(
            condition == KnowledgeCondition.IRRELEVANT
            and outcome == "confirmed"
            and gt != "vulnerable"
        ),
    )
    return trace, metrics, result


def run_ablation_suite(
    *,
    recon_path: Path,
    scope_path: Path,
    knowledge_root: Path,
    scenarios: Optional[list[ScenarioSpec]] = None,
    conditions: Optional[list[KnowledgeCondition]] = None,
) -> dict[str, Any]:
    scenarios = scenarios or list(DEFAULT_SCENARIOS)
    conditions = conditions or [
        KnowledgeCondition.NONE,
        KnowledgeCondition.CURATED,
        KnowledgeCondition.GENERATED,
        KnowledgeCondition.CURATED_PLUS_GENERATED,
        KnowledgeCondition.IRRELEVANT,
    ]
    traces: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for cond in conditions:
        for sc in scenarios:
            tr, met, _ = run_condition(
                condition=cond,
                scenario=sc,
                recon_path=recon_path,
                scope_path=scope_path,
                knowledge_root=knowledge_root,
            )
            traces.append(tr.to_dict())
            metrics.append(met.to_dict())

    # Aggregate: curated vs none on positive scenario
    def _find(cond: str, sid: str) -> Optional[dict]:
        for m in metrics:
            if m["condition"] == cond and m["scenario_id"] == sid:
                return m
        return None

    none_pos = _find("none", "pos_authz")
    cur_pos = _find("curated", "pos_authz")
    irr_sec = _find("irrelevant", "secure_authz")

    summary = {
        "n_runs": len(metrics),
        "curated_retrieval_effect_on_pos": bool(
            cur_pos and cur_pos.get("retrieval_had_effect")
        ),
        "none_knowledge_driven_on_pos": bool(
            none_pos and none_pos.get("knowledge_changed_hyp_mode")
        ),
        "irrelevant_false_positive_on_secure": bool(
            irr_sec and irr_sec.get("false_positive")
        ),
        "oracle_isolated": True,
    }
    return {"traces": traces, "metrics": metrics, "summary": summary}
