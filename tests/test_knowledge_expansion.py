"""Knowledge expansion: source quality, case extract, dedup, episode feedback."""

from pathlib import Path

from agent_core.knowledge.case_extract import extract_case_from_text
from agent_core.knowledge.dedup import (
    cluster_cases_to_patterns,
    fingerprint_pattern,
    novelty_vs_existing,
)
from agent_core.knowledge.expansion import KnowledgeExpansionPipeline
from agent_core.knowledge.index import KnowledgeIndex
from agent_core.knowledge.source_quality import (
    SourceStatus,
    SourceType,
    score_writeup_text,
)
from agent_core.orchestrator.closed_loop import ClosedLoopRunner, default_idor_lab_scenario

ROOT = Path(__file__).resolve().parents[1]
KROOT = ROOT / "knowledge"
FIXTURE = ROOT / "examples" / "fixtures" / "sample_recon.json"
SCOPE = ROOT / "examples" / "demo_program_scope.yaml"


def test_source_quality_scores_without_trust():
    sig = score_writeup_text(
        "Reproduction steps: send HTTP request with object id. Root cause: missing ownership check. Impact: read other user orders.",
        origin="https://portswigger.net/example",
    )
    assert sig.priority_score() > 0.2
    assert sig.source_reliability >= 0.7


def test_extract_case_leaves_unknowns():
    case = extract_case_from_text(
        "# Title\n\nSome vague text without sections.\n",
        case_id="CASE-T1",
        source_id="SRC-T",
    )
    assert "hypothesis" in case.unknowns or case.hypothesis == ""
    assert case.provenance.get("extractor")


def test_extract_case_detects_authorization():
    text = """# IDOR writeup
## Hypothesis
Object-level authorization missing for order id.
## Observation
Non-owner received 200 with private fields.
## Root cause
Server trusted client-supplied id.
"""
    case = extract_case_from_text(text, case_id="CASE-T2", source_id="SRC-T")
    assert case.security_property == "authorization"
    assert case.hypothesis
    assert case.observation


def test_dedup_preserves_multiple_cases_same_fingerprint():
    from agent_core.knowledge.case_extract import StructuredCase

    c1 = StructuredCase(
        case_id="C1",
        security_property="authorization",
        hypothesis="missing ownership",
        root_cause="id not bound",
        preconditions=["two identities"],
    )
    c2 = StructuredCase(
        case_id="C2",
        security_property="authorization",
        hypothesis="missing ownership",
        root_cause="id not bound",
        preconditions=["two identities"],
    )
    clusters = cluster_cases_to_patterns([c1, c2])
    assert len(clusters) == 1
    assert set(clusters[0].member_case_ids) == {"C1", "C2"}


def test_expansion_rejects_empty():
    pipe = KnowledgeExpansionPipeline(KROOT)
    r = pipe.ingest_text_source(
        source_id="SRC-EMPTY", text="   ", origin="test", title="x"
    )
    assert r.source.status == SourceStatus.REJECTED
    assert r.blocked_reason == "empty_text"


def test_expansion_unverified_extracts_case_without_auto_generate_trust():
    pipe = KnowledgeExpansionPipeline(KROOT)
    text = """# Authz case
## Hypothesis
BOLA on object key
## Observation
status 200 for non-owner
## Root cause
no ownership check
"""
    r = pipe.ingest_text_source(
        source_id="SRC-U1",
        text=text,
        origin="offline-fixture",
        source_type=SourceType.WRITEUP,
        title="fixture writeup",
        auto_accept=False,
    )
    assert r.case is not None
    assert r.source.status == SourceStatus.UNVERIFIED
    # generated_ids only when ACCEPTED
    assert r.generated_ids == []


def test_expansion_accepted_can_generate_candidates():
    pipe = KnowledgeExpansionPipeline(KROOT)
    text = """# Authz case
## Hypothesis
Object-level authorization failure
## Observation
cross-identity access
## Root cause
missing ownership
## Preconditions
- two users
"""
    r = pipe.ingest_text_source(
        source_id="SRC-A1",
        text=text,
        origin="https://portswigger.net/x",
        auto_accept=True,
    )
    assert r.source.status == SourceStatus.ACCEPTED
    assert r.case is not None
    assert r.novelty in (
        "new_case",
        "strengthens_pattern",
        "duplicate_information",
        "contradiction_unknown",
    )


def test_episode_produces_structured_case():
    result = ClosedLoopRunner(scope_path=SCOPE, engagement_id="exp_case").run(
        FIXTURE, scenario=default_idor_lab_scenario()
    )
    assert result.structured_case is not None
    d = result.structured_case.to_dict()
    assert d["provenance"].get("not_trusted") is True
    assert d["case_id"].startswith("CASE-EP-")


def test_business_logic_knowledge_loaded():
    idx = KnowledgeIndex(KROOT).load()
    ids = {r.record_id.upper() for r in idx.records}
    assert any("0012" in i for i in ids)


def test_fingerprint_stable():
    a = fingerprint_pattern(security_property="ssrf", abstraction="server side url fetch")
    b = fingerprint_pattern(security_property="ssrf", abstraction="server side url fetch")
    assert a == b
