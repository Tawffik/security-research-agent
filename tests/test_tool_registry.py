from agent_core.tools.registry import ToolRegistry


def test_default_tools_present():
    reg = ToolRegistry()
    assert reg.get("http_request") is not None
    assert reg.get("diff_response_by_identity") is not None
    assert len(reg.list_all()) >= 3


def test_retrieve_for_authz_task():
    reg = ToolRegistry()
    tools = reg.retrieve("cross identity authenticated request diff", limit=3)
    names = [t.name for t in tools]
    assert "diff_response_by_identity" in names or "authenticated_http_request" in names
