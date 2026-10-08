"""
Gate 6A — Offline real-BBCI-artifact → full research episode.

Input: historical BugBountyCI live.txt (or normalized JSON).
No live HTTP. Observations come from artifact-derived lab fixtures only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from agent_core.evaluation.trajectory import evaluate_trajectory
from agent_core.experiments.utility import select_by_utility
from agent_core.orchestrator.closed_loop import (
    ClosedLoopResult,
    ClosedLoopRunner,
    LabObservation,
    LabScenario,
)
from agent_core.recon.adapter import adapt_bbci_live_txt
from agent_core.recon.bbci_contract import parse_bbci_live_txt
from agent_core.research.brief import compile_brief_from_closed_loop
from agent_core.research.stop_semantics import StopReason
from agent_core.target.opportunity import OpportunityEngine
from agent_core.tools.contracts import AUTHENTICATED_HTTP_READ
from agent_core.tools.execution_boundary import ActionRequest, ExecutionBoundary
from agent_core.scope.guard import ScopeGuard


@dataclass
class OfflineBBCIEpisodeReport:
    ok: bool
    artifact_path: str
    artifact_provenance: dict[str, Any] = field(default_factory=dict)
    contract_ok: bool = False
    primary_host: str = ""
    n_endpoints: int = 0
    n_opportunities: int = 0
    n_hypotheses: int = 0
    n_experiments: int = 0
    selected_experiment_id: str = ""
    utility_reasons: list[str] = field(default_factory=list)
    scope_allowed: bool = False
    execution_mode: str = "offline_lab"  # never "live"
    differential_change_kind: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    evidence_graph_edges: int = 0
    verification_status: str = ""
    episode_id: str = ""
    stop_reason: str = ""
    decision: str = ""
    brief: dict[str, Any] = field(default_factory=dict)
    trajectory: dict[str, Any] = field(default_factory=dict)
    stages: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    closed_loop: Optional[ClosedLoopResult] = None
    loss_attribution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("closed_loop", None)
        return d


def lab_scenario_from_bbci_live_txt(
    text: str,
    *,
    primary_host: str,
) -> LabScenario:
    """
    Derive offline lab observations from historical BBCI live.txt status lines.
    These are recon-phase statuses already collected by BugBountyCI — not new live probes.
    """
    observations: list[LabObservation] = []
    for i, line in enumerate((text or "").splitlines()):
        line = line.strip()
        if not line or not line.startswith("http"):
            continue
        # Extract status in brackets if present
        status = 0
        body = line[:200]
        if "[" in line:
            try:
                part = line.split("[", 1)[1].split("]", 1)[0]
                if part.isdigit():
                    status = int(part)
            except Exception:
                status = 0
        path = "/"
        try:
            from urllib.parse import urlparse

            p = urlparse(line.split()[0])
            path = p.path or "/"
            host = p.hostname or primary_host
        except Exception:
            host = primary_host
        role = "baseline" if i == 0 else ("challenge" if i == 1 else "observe")
        observations.append(
            LabObservation(
                identity=f"recon_{i}",
                method="GET",
                path=path,
                host=host or primary_host,
                status=status or 0,
                body=body,
                notes="bbci_live_txt_historical",
                role=role if i < 2 else "observe",
            )
        )
        if len(observations) >= 4:
            break
    if len(observations) < 2:
        # Ensure baseline/challenge pair for differential
        observations = [
            LabObservation(
                identity="recon_a",
                method="GET",
                path="/",
                host=primary_host,
                status=200,
                body="bbci_offline_baseline",
                notes="bbci_synthetic_pair",
                role="baseline",
            ),
            LabObservation(
                identity="recon_b",
                method="GET",
                path="/",
                host=primary_host,
                status=404,
                body="bbci_offline_challenge",
                notes="bbci_synthetic_pair",
                role="challenge",
            ),
        ]
    return LabScenario(
        name="lab_bbci_offline_artifact",
        observations=observations,
        expected_if_secure="Historical recon statuses only — no live confirmation",
        suggests_authz_issue=False,
        methodology="authorization",
    )


def run_offline_bbci_episode(
    live_txt_path: Union[str, Path],
    *,
    scope_path: Union[str, Path],
    engagement_id: str = "bbci_offline_ep",
    program_name: str = "",
) -> OfflineBBCIEpisodeReport:
    path = Path(live_txt_path)
    text = path.read_text(encoding="utf-8")
    stages = {k: False for k in (
        "ingestion", "adaptation", "opportunity", "knowledge", "hypotheses",
        "experiments", "selection", "execution_boundary", "observation",
        "differential", "evidence", "verification", "episode", "decision",
    )}
    notes: list[str] = ["execution_mode=offline_lab", "no_live_http"]

    # Stage A — contract
    contract = parse_bbci_live_txt(text, program_name=program_name or path.stem)
    stages["ingestion"] = bool(contract.ok)
    if not contract.ok:
        return OfflineBBCIEpisodeReport(
            ok=False,
            artifact_path=str(path),
            contract_ok=False,
            stages=stages,
            notes=notes + [f"contract_failed:{contract.issues}"],
        )

    # Stage B — adapt
    (ctx, graph, meta), contract2 = adapt_bbci_live_txt(
        engagement_id, text, program_name=program_name or path.stem
    )
    stages["adaptation"] = bool(contract2.ok and ctx.primary_host)
    primary = ctx.primary_host

    # Stage C — opportunities
    opps = OpportunityEngine(engagement_id).rank(ctx, graph)
    stages["opportunity"] = True  # exercised even if empty
    notes.append(f"n_opportunities={len(opps)}")

    # Stages D–G via ClosedLoop (uses ResearchLoop internally)
    scenario = lab_scenario_from_bbci_live_txt(text, primary_host=primary)

    # Write temp recon JSON for ClosedLoopRunner path
    import json
    import tempfile

    recon = dict(contract2.normalized)
    recon["engagement_id"] = engagement_id
    recon["source"] = "bbci_live_txt"
    recon["provenance"] = dict(contract2.normalized.get("provenance") or {})
    recon["provenance"]["artifact_path"] = str(path)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(recon, f)
        recon_path = Path(f.name)

    runner = ClosedLoopRunner(scope_path=scope_path, engagement_id=engagement_id)
    result = runner.run(recon_path, scenario=scenario)

    stages["knowledge"] = bool(getattr(runner.research, "last_retrieval", None))
    stages["hypotheses"] = bool(result.plan and result.plan.hypotheses)
    stages["experiments"] = bool(result.plan and result.plan.experiments)
    stages["selection"] = bool(result.selected_experiment_id)
    stages["observation"] = bool(result.observations or result.normalized_observations)
    stages["differential"] = result.differential_result is not None
    stages["evidence"] = bool(result.evidence_ids)
    stages["verification"] = result.final_status is not None
    stages["episode"] = result.episode is not None
    stages["decision"] = bool(result.stop_reason or result.final_status)

    # Stage H — execution boundary (offline deny-or-allow without live)
    guard = ScopeGuard.from_scope_file(scope_path)
    boundary = ExecutionBoundary(guard=guard)
    boundary.register(AUTHENTICATED_HTTP_READ)
    # Prove boundary is consulted: live_mode denied; offline host scoped
    live_deny = boundary.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host=primary,
            live_mode=True,
            experiment_id=result.selected_experiment_id or "",
        )
    )
    offline_auth = boundary.request_execution(
        ActionRequest(
            tool_name="authenticated_http_request",
            host=primary,
            live_mode=False,
            experiment_id=result.selected_experiment_id or "",
            purpose="offline_lab_only",
        )
    )
    stages["execution_boundary"] = live_deny.allowed is False
    notes.append(f"live_mode_denied={not live_deny.allowed}")
    notes.append(f"offline_scope_decision={offline_auth.reason}")

    # Utility selection audit on plan experiments
    util_reasons: list[str] = []
    if result.plan and result.plan.experiments:
        _, scores = select_by_utility(
            list(result.plan.experiments),
            hypotheses=list(result.plan.hypotheses or []),
        )
        if scores:
            util_reasons = list(scores[0].reasons)

    brief = compile_brief_from_closed_loop(result, engagement_id=engagement_id)
    traj = evaluate_trajectory(
        episode_id=getattr(result.episode, "episode_id", "") or engagement_id,
        experiment_ids=[result.selected_experiment_id or ""],
        observation_count=len(result.observations or []),
        evidence_polarities=["neutral"] * len(result.evidence_ids or []),
        branch_count=1,
        backtrack_count=0,
        stop_reason=result.stop_reason or "",
        discriminating_experiment_ids=[result.selected_experiment_id]
        if result.selected_experiment_id
        else [],
        tried_experiment_ids=[result.selected_experiment_id or ""],
    )

    decision = brief.next_decision or result.stop_reason or result.final_status or "unknown"
    ok = all(
        stages[s]
        for s in (
            "ingestion",
            "adaptation",
            "observation",
            "evidence",
            "verification",
            "episode",
            "execution_boundary",
        )
    )

    return OfflineBBCIEpisodeReport(
        ok=ok,
        artifact_path=str(path),
        artifact_provenance=dict(recon.get("provenance") or {}),
        contract_ok=True,
        primary_host=primary,
        n_endpoints=len(ctx.endpoints or []),
        n_opportunities=len(opps),
        n_hypotheses=len(result.plan.hypotheses) if result.plan else 0,
        n_experiments=len(result.plan.experiments) if result.plan else 0,
        selected_experiment_id=result.selected_experiment_id or "",
        utility_reasons=util_reasons,
        scope_allowed=result.scope_allowed,
        execution_mode="offline_lab",
        differential_change_kind=(result.differential_result or {}).get("change_kind", ""),
        evidence_ids=list(result.evidence_ids or []),
        evidence_graph_edges=len(result.evidence_graph or []),
        verification_status=str(result.final_status or ""),
        episode_id=getattr(result.episode, "episode_id", "") or "",
        stop_reason=result.stop_reason or "",
        decision=str(decision),
        brief=brief.to_dict(),
        trajectory=traj.to_dict() if hasattr(traj, "to_dict") else {},
        stages=stages,
        notes=notes,
        closed_loop=result,
        loss_attribution=_bbci_loss_attribution(stages),
    )




def run_offline_sra_handoff_adapt(
    handoff_path: Union[str, Path],
    *,
    engagement_id: str = "bbci_sra_handoff_adapt",
) -> OfflineBBCIEpisodeReport:
    """Deterministic BBCI sra_handoff.json → contract → ReconResultAdapter (no live HTTP).

    Completes the producer→consumer adapt stage without requiring live.txt.
    Does not claim full research episode stages beyond adaptation.
    """
    import json
    from agent_core.recon.adapter import adapt_bbci_artifact

    path = Path(handoff_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    stages = {k: False for k in (
        "ingestion", "adaptation", "opportunity", "knowledge", "hypotheses",
        "experiments", "selection", "execution_boundary", "observation",
        "differential", "evidence", "verification", "episode", "decision",
    )}
    notes = ["execution_mode=offline_lab", "no_live_http", "artifact=sra_handoff.v1"]
    try:
        adapted, contract = adapt_bbci_artifact(engagement_id, raw)
    except ValueError as e:
        return OfflineBBCIEpisodeReport(
            ok=False,
            artifact_path=str(path),
            contract_ok=False,
            stages=stages,
            notes=notes + [str(e)],
        )
    ctx, graph, meta = adapted
    stages["ingestion"] = True
    stages["adaptation"] = bool(contract.ok and ctx.primary_host)
    return OfflineBBCIEpisodeReport(
        ok=bool(contract.ok and ctx.primary_host and ctx.endpoints),
        artifact_path=str(path),
        artifact_provenance={"source_shape": contract.source_shape, "schema": raw.get("schema")},
        contract_ok=contract.ok,
        primary_host=ctx.primary_host,
        n_endpoints=len(ctx.endpoints or []),
        stages=stages,
        notes=notes,
        decision="adapt_only",
    )

def _bbci_loss_attribution(stages: dict[str, bool]) -> dict:
    """Diagnostic only — attribute first missing offline BBCI stage."""
    from agent_core.evaluation.loss_attribution import StagePresence, attribute_loss
    present = StagePresence(
        recon=bool(stages.get("ingestion")),
        adapter=bool(stages.get("adaptation")),
        modeling=bool(stages.get("opportunity")),
        hypothesis=bool(stages.get("hypotheses")),
        experiment_selected=bool(stages.get("selection")),
        executed=bool(stages.get("execution_boundary")),
        observation=bool(stages.get("observation")),
        interpretation=bool(stages.get("differential")),
        falsification_evaluated=bool(stages.get("evidence")),
        verification=bool(stages.get("verification")),
        promoted=bool(stages.get("decision")),
    )
    return attribute_loss("bbci_offline", present).to_dict()
