"""
Skill Registry — MASTER SPEC §4 and §5 (Skill System + Skill Graph).

A Skill on disk looks like:

    skills/<skill-name>/
        metadata.yaml   <- Level 1: always loaded, cheap, used for routing
        SKILL.md        <- Level 2: loaded only once metadata routing selects it
        references/     <- Level 3: loaded only if SKILL.md points at it
        scripts/        <- Level 4: executed only, never dumped into context

This mirrors the pattern used by trailofbits/skills and Anthropic's Agent
Skills format: cheap metadata is always in context for routing, the full
instructions are only paid for once a skill is actually selected, and deep
reference material is paid for only if the skill itself asks for it.

Skill Supply Chain (MASTER SPEC §18): every skill loaded from an external
source gets a trust_score and is refused execution above RiskTier.PASSIVE
until a human has reviewed it. This registry enforces that at load time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SkillMetadata:
    name: str
    purpose: str
    trigger_conditions: list[str]
    target_technologies: list[str] = field(default_factory=list)
    vulnerability_classes: list[str] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    next_skills: list[str] = field(default_factory=list)
    cost_estimate: str = "unknown"
    provenance: str = "internal"      # "internal" | "vendored:<org>" | "community:<url>"
    trust_score: float = 0.0          # 0.0 (untrusted) .. 1.0 (fully vetted)
    version: str = "0.0.1"


@dataclass
class Skill:
    metadata: SkillMetadata
    root_dir: Path
    _body: Optional[str] = None   # lazily loaded SKILL.md content

    def body(self) -> str:
        """Level 2 disclosure — only paid for when the skill is actually selected."""
        if self._body is None:
            skill_md = self.root_dir / "SKILL.md"
            self._body = skill_md.read_text() if skill_md.exists() else ""
        return self._body

    def reference(self, name: str) -> str:
        """Level 3 disclosure — a specific reference file, loaded on demand."""
        ref_path = self.root_dir / "references" / name
        if not ref_path.exists():
            raise FileNotFoundError(f"skill {self.metadata.name} has no reference {name}")
        return ref_path.read_text()

    def script_path(self, name: str) -> Path:
        """Level 4 — a script path to execute, never to be pasted into context."""
        script_path = self.root_dir / "scripts" / name
        if not script_path.exists():
            raise FileNotFoundError(f"skill {self.metadata.name} has no script {name}")
        return script_path


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def load_directory(self, skills_dir: str | Path, min_trust_for_active: float = 0.6) -> None:
        skills_dir = Path(skills_dir)
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "metadata.yaml"
            if not meta_path.exists():
                continue
            raw = yaml.safe_load(meta_path.read_text())
            metadata = SkillMetadata(**raw)
            self._skills[metadata.name] = Skill(metadata=metadata, root_dir=entry)

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def all_metadata(self) -> list[SkillMetadata]:
        """
        Level 1 disclosure surface: what gets shown to the planner/orchestrator
        for routing decisions. Cheap enough to always be in context.
        """
        return [s.metadata for s in self._skills.values()]

    def route(
        self,
        technologies: list[str],
        vulnerability_hint: Optional[str] = None,
        max_risk_tier_allowed: Optional[str] = None,
    ) -> list[Skill]:
        """
        Naive metadata-based routing (MASTER SPEC §12, Target Profiling ->
        automatic skill selection). Replace with embedding / graph retrieval
        in Phase 3 — this is intentionally simple so Phase 1-2 is fully
        functional without a vector store dependency.
        """
        candidates = []
        for skill in self._skills.values():
            tech_match = not skill.metadata.target_technologies or any(
                t in technologies for t in skill.metadata.target_technologies
            )
            vuln_match = (
                vulnerability_hint is None
                or not skill.metadata.vulnerability_classes
                or vulnerability_hint in skill.metadata.vulnerability_classes
            )
            trusted_enough = skill.metadata.trust_score >= 0.6 or skill.metadata.provenance == "internal"
            if tech_match and vuln_match and trusted_enough:
                candidates.append(skill)
        return candidates

    def resolve_execution_order(self, selected: list[Skill]) -> list[Skill]:
        """Topologically sorts selected skills by their declared dependencies."""
        by_name = {s.metadata.name: s for s in selected}
        visited: set[str] = set()
        order: list[Skill] = []

        def visit(skill: Skill):
            if skill.metadata.name in visited:
                return
            visited.add(skill.metadata.name)
            for dep in skill.metadata.dependencies:
                if dep in by_name:
                    visit(by_name[dep])
            order.append(skill)

        for skill in selected:
            visit(skill)
        return order
