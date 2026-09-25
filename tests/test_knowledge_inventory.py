from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_knowledge_files_present():
    assert (ROOT / "sources" / "SOURCE-REGISTRY.md").exists()
    assert (ROOT / "cases" / "CASE-0002-portsWigger-idor-db-object.md").exists()
    assert (ROOT / "cases" / "CASE-0004-owasp-bola-shop-revenue.md").exists()
    assert (ROOT / "patterns" / "PAT-0002-bola-user-controlled-object-key.md").exists()
    assert (ROOT / "procedures" / "PROC-0002-object-key-substitution.md").exists()
    assert (ROOT / "strategies" / "STRAT-0001-prioritize-object-keyed-auth-apis.md").exists()
    assert (ROOT / "cases" / "CASE-0006-profile-idor-to-ato.md").exists()
    assert (ROOT / "sources" / "NOTION-INVENTORY.md").exists()
    assert (ROOT / "patterns" / "PAT-0003-bola-action-level-mutation.md").exists()
    assert (ROOT / "procedures" / "PROC-0003-mutation-object-authorization.md").exists()
    assert (ROOT / "cases" / "CASE-0007-graphql-mutation-authz-gap.md").exists()
    reg = (ROOT / "sources" / "SOURCE-REGISTRY.md").read_text()
    assert "PortSwigger" in reg and "OWASP" in reg
    assert "not bulk-scraped" in reg.lower() or "not bulk-scraped" in reg
