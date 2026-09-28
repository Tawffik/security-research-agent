"""M4: selected Experiment reaches closed-loop evidence/interpretation."""

from pathlib import Path

from agent_core.orchestrator.closed_loop import (
    ClosedLoopRunner,
    default_idor_lab_scenario,
    secure_lab_scenario,
)
from agent_core.orchestrator.experiment_alignment import (
    align_experiment_to_scenario,
    interpret_discriminator,
)
from agent_core.schemas.research import Experiment, ExperimentStatus

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_a_experiment_provenance_on_evidence():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m4_prov")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.selected_experiment_id
    assert result.experiment_alignment
    assert result.experiment_alignment["experiment_id"] == result.selected_experiment_id
    assert result.experiment_alignment["scenario_name"]
    sources = []
    for eid in result.evidence_ids:
        row = runner.evidence.conn.execute(
            "SELECT source FROM evidence WHERE evidence_id=?",
            (eid,),
        ).fetchone()
        sources.append(row[0] if row else "")
    joined = " ".join(sources)
    assert "exp=" in joined
    assert result.selected_experiment_id in joined


def test_b_required_evidence_satisfaction_differs():
    scenario = default_idor_lab_scenario()
    exp_a = Experiment(
        experiment_id="exp_req_a",
        hypothesis_id="h1",
        description="cross identity",
        required_evidence=["cross_identity_response", "response_status"],
        discriminator="status code + ownership under two identities",
        status=ExperimentStatus.PLANNED,
    )
    exp_b = Experiment(
        experiment_id="exp_req_b",
        hypothesis_id="h1",
        description="needs side effect",
        required_evidence=["before_after_mutation_state", "side_effect_proof"],
        discriminator="before/after object state under two identities",
        status=ExperimentStatus.PLANNED,
    )
    a = align_experiment_to_scenario(exp_a, scenario, hypothesis_id="h1")
    b = align_experiment_to_scenario(exp_b, scenario, hypothesis_id="h1")
    a_map = {r.requirement: r.status for r in a.required_evidence}
    b_map = {r.requirement: r.status for r in b.required_evidence}
    assert a_map != b_map
    assert any(s == "satisfied" for s in a_map.values())
    assert any(s == "missing" for s in b_map.values())


def test_c_discriminator_affects_interpretation():
    scenario = default_idor_lab_scenario()
    o1, _ = interpret_discriminator(
        "status code + non-owner denied 403", list(scenario.observations), scenario
    )
    o2, _ = interpret_discriminator(
        "procedure:PROC-0001|compare two identities differential",
        list(scenario.observations),
        scenario,
    )
    assert o1 in ("contradicts", "ambiguous")
    assert o2 in ("supports", "ambiguous", "indeterminate")
    assert o1 != o2


def test_d_knowledge_backed_experiment_crosses_boundary():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m4_know")
    result = runner.run(FIXTURE, scenario=default_idor_lab_scenario())
    assert result.selected_experiment_id
    align = result.experiment_alignment
    assert align["discriminator_outcome"]
    assert "required_evidence" in align
    assert any(
        "experiment_alignment"
        in (
            runner.evidence.conn.execute(
                "SELECT source FROM evidence WHERE evidence_id=?", (eid,)
            ).fetchone()
            or [""]
        )[0]
        for eid in result.evidence_ids
    )


def test_e_fallback_still_works():
    runner = ClosedLoopRunner(scope_path=SCOPE, engagement_id="eng_m4_fb")
    result = runner.run(FIXTURE, scenario=secure_lab_scenario())
    assert result.scope_allowed
    assert result.experiment_alignment is not None


def test_f_existing_scenarios_still_run():
    for scen_fn in (default_idor_lab_scenario, secure_lab_scenario):
        runner = ClosedLoopRunner(
            scope_path=SCOPE, engagement_id=f"eng_m4_{scen_fn.__name__}"
        )
        result = runner.run(FIXTURE, scenario=scen_fn())
        assert result.plan is not None
        assert result.evidence_ids
