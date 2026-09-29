"""Gate 1 — Real Knowledge Bridge (offline bounded corpus)."""

from pathlib import Path

from agent_core.knowledge.bridge import KnowledgeBridge
from agent_core.knowledge.case_extract import extract_case_from_text
from agent_core.knowledge.index import KnowledgeIndex

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"


def test_fixture_writeups_exist():
    paths = list((KROOT / "sources" / "fixtures").glob("WRITEUP-*.md"))
    assert len(paths) >= 2


def test_bridge_compiles_with_lineage_and_fp():
    report = KnowledgeBridge(KROOT).compile_fixtures()
    assert report.sources_processed >= 2
    assert report.cases_extracted >= 2
    assert report.lineage_complete is True
    assert report.fp_guidance_preserved is True
    for u in report.units:
        assert u.lineage
        assert u.trusted is False  # not auto-promoted
        if u.kind == "case":
            assert u.case is not None
            assert u.source_id


def test_fp_section_extracted_not_fabricated():
    text = (KROOT / "sources" / "fixtures" / "WRITEUP-BOLA-sample.md").read_text()
    case = extract_case_from_text(text, case_id="C", source_id="SRC-FX-0001")
    assert case.false_positive_guidance
    assert any("public" in x.lower() or "shared" in x.lower() for x in case.false_positive_guidance)
    # unknowns remain if sections missing - experiment present
    assert case.hypothesis
    assert case.observation


def test_no_lab_fixture_as_trusted_knowledge():
    report = KnowledgeBridge(KROOT).compile_fixtures()
    assert all(u.trusted is False for u in report.units)


def test_compiler_pipeline_still_has_lineage_edges():
    out = KnowledgeBridge(KROOT).compiler_pipeline_with_lineage()
    assert out["lineage_edges"] >= 1
    assert out["sources"] >= 1


def test_negative_guidance_unit_present():
    report = KnowledgeBridge(KROOT).compile_fixtures()
    negs = [u for u in report.units if u.kind == "negative"]
    assert negs
    assert negs[0].false_positive_guidance


def test_curated_corpus_still_loads():
    idx = KnowledgeIndex(KROOT).load()
    assert any(r.record_id.startswith("PROC-") for r in idx.records)
