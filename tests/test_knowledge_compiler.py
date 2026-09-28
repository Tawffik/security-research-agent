"""M10: Knowledge compiler — source registry + lineage, no auto skill promotion."""

from pathlib import Path

from agent_core.knowledge.compiler import KnowledgeCompiler, parse_source_registry

ROOT = Path(__file__).resolve().parents[1]


def test_parse_source_registry():
    entries = parse_source_registry(ROOT / "knowledge" / "sources" / "SOURCE-REGISTRY.md")
    assert any(e.source_id == "SRC-0001" for e in entries)
    assert all(e.source_id.startswith("SRC-") for e in entries)


def test_compile_lineage_graph():
    graph = KnowledgeCompiler(ROOT / "knowledge").compile()
    assert graph.sources
    assert graph.records_by_id
    assert graph.edges
    # procedures exist in index
    assert any(rid.startswith("PROC-") for rid in graph.records_by_id)


def test_lineage_for_procedure_includes_ancestors_when_linked():
    graph = KnowledgeCompiler(ROOT / "knowledge").compile()
    proc_ids = [r for r in graph.records_by_id if r.startswith("PROC-")]
    assert proc_ids
    chain = graph.lineage_for(proc_ids[0])
    assert chain[0] == proc_ids[0]


def test_compiler_does_not_write_skills():
    c = KnowledgeCompiler(ROOT / "knowledge")
    assert c.assert_no_auto_skill_write() is True
    assert not hasattr(c, "write_skill")
