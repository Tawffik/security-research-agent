import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.skills.registry import SkillRegistry

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def test_loads_all_example_skills():
    registry = SkillRegistry()
    registry.load_directory(SKILLS_DIR)
    names = {m.name for m in registry.all_metadata()}
    assert names == {"recon-js-surface", "authz-idor-analysis", "report-generator"}


def test_progressive_disclosure_body_lazy_loaded():
    registry = SkillRegistry()
    registry.load_directory(SKILLS_DIR)
    skill = registry.get("recon-js-surface")
    assert skill._body is None  # not loaded yet — Level 1 metadata only so far
    body = skill.body()
    assert "Purpose" in body
    assert skill._body is not None  # now cached


def test_routing_by_technology_and_vuln_class():
    registry = SkillRegistry()
    registry.load_directory(SKILLS_DIR)
    routed = registry.route(technologies=["react"], vulnerability_hint="idor")
    names = {s.metadata.name for s in routed}
    # recon has no tech restriction issue (matches react), authz has no tech
    # restriction (empty list = matches anything) and matches "idor" hint.
    assert "recon-js-surface" in names
    assert "authz-idor-analysis" in names


def test_dependency_ordering():
    registry = SkillRegistry()
    registry.load_directory(SKILLS_DIR)
    selected = [registry.get("authz-idor-analysis"), registry.get("recon-js-surface")]
    ordered = registry.resolve_execution_order(selected)
    names_in_order = [s.metadata.name for s in ordered]
    # authz-idor-analysis depends on recon-js-surface, so recon must come first
    assert names_in_order.index("recon-js-surface") < names_in_order.index("authz-idor-analysis")
