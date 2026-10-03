from agent_core.tools.interpreter_safety import (
    FORBIDDEN_PRIMITIVES,
    authorize_interpreter_primitive,
)
from agent_core.tools.capability import FailureClass


def test_forbidden_primitives_denied():
    for p in ("os.system", "subprocess.Popen", "eval", "exec"):
        d = authorize_interpreter_primitive(p)
        assert d.allowed is False
        assert d.failure_class == FailureClass.CAPABILITY_NOT_EXPOSED.value


def test_knowledge_cannot_grant_shell():
    d = authorize_interpreter_primitive(
        "os.system",
        knowledge_grants_permission=True,
        skill_approved=True,
        explicit_tool_contract=True,
        scope_allowed=True,
    )
    assert d.allowed is False
    assert "knowledge_cannot_grant" in d.reason


def test_skill_alone_cannot_unlock_eval():
    d = authorize_interpreter_primitive("eval", skill_approved=True)
    assert d.allowed is False


def test_even_full_flags_still_deny_unrestricted_primitives():
    # Policy: unrestricted interpreter remains not exposed
    d = authorize_interpreter_primitive(
        "subprocess.run",
        skill_approved=True,
        explicit_tool_contract=True,
        scope_allowed=True,
    )
    assert d.allowed is False
    assert d.failure_class == FailureClass.CAPABILITY_NOT_EXPOSED.value


def test_forbidden_set_nonempty():
    assert "eval" in FORBIDDEN_PRIMITIVES
