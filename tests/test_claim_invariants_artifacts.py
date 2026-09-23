from pathlib import Path

from agent_core.evidence.claim_matrix import ClaimEvidenceBuilder
from agent_core.orchestrator.artifacts import write_engagement_artifacts
from agent_core.orchestrator.closed_loop import default_idor_lab_scenario, secure_lab_scenario
from agent_core.orchestrator.run_adaptive import run_closed_then_adaptive
from agent_core.security.invariants import InvariantRegistry

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_claim_matrix_blocks_without_evidence():
    m = ClaimEvidenceBuilder("e").build(claim="x", evidence_ids=[])
    assert m.report_ready is False
    assert m.block_reason == "core_claim_missing_evidence"


def test_pipeline_matrix_and_invariant_idor():
    closed, _, _, _, _, _, matrix, inv = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_cma",
        scenario=default_idor_lab_scenario(),
    )
    assert matrix.report_ready is True
    assert matrix.rows[0].evidence_ids
    assert inv
    assert inv[0].holds is False  # non-owner got access


def test_invariant_holds_on_secure():
    closed, _, _, _, _, _, matrix, inv = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_cma_s",
        scenario=secure_lab_scenario(),
    )
    assert inv
    assert inv[0].holds is True


def test_write_artifacts(tmp_path):
    closed, adaptive, cp, regrets, surprises, mem, matrix, inv = run_closed_then_adaptive(
        recon_path=FIXTURE,
        scope_path=SCOPE,
        engagement_id="eng_art",
        scenario=default_idor_lab_scenario(),
    )
    written = write_engagement_artifacts(
        tmp_path / "engagement",
        engagement_id="eng_art",
        closed=closed,
        adaptive=adaptive,
        checkpoint=cp,
        regrets=regrets,
        surprises=surprises,
        memory_entries=mem,
        claim_matrix=matrix,
        invariant_checks=inv,
    )
    assert "engagement.json" in written
    assert "claim_evidence_matrix.json" in written
    assert (tmp_path / "engagement" / "final-report.md").exists()
