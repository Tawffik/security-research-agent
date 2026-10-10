"""
Skill decision advisor — injects methodology policy into ResearchLoop.

Skills under /skills are progressive-disclosure packages (metadata + SKILL.md).
This advisor does NOT execute tools, grant permissions, or bypass ScopeGuard.
It only contributes decision-policy metadata:

- competing explanations (false-positive alternatives)
- evidence requirement hints
- vulnerability-class / methodology routing signals

Provenance is recorded so benchmarks can separate:
selected → loaded → influenced → improved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_core.skills.registry import Skill, SkillRegistry


# Default skills root relative to repository
_DEFAULT_SKILLS = Path(__file__).resolve().parents[3] / "skills"


@dataclass
class SkillAdvice:
    """Observable skill influence package for research traces."""

    selected: list[str] = field(default_factory=list)
    loaded: list[str] = field(default_factory=list)
    competing_explanations: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    vulnerability_hints: list[str] = field(default_factory=list)
    provenance: list[dict] = field(default_factory=list)
    influenced: bool = False

    def to_dict(self) -> dict:
        return {
            "selected": list(self.selected),
            "loaded": list(self.loaded),
            "competing_explanations": list(self.competing_explanations),
            "evidence_requirements": list(self.evidence_requirements),
            "vulnerability_hints": list(self.vulnerability_hints),
            "provenance": list(self.provenance),
            "influenced": self.influenced,
        }


def _extract_skeptic_prompts(body: str) -> list[str]:
    """Pull alternative-explanation lines from SKILL.md skeptic sections."""
    out: list[str] = []
    if not body:
        return out
    # Lines under skeptic / alternative / false-positive style headings
    in_section = False
    for line in body.splitlines():
        low = line.lower().strip()
        if low.startswith("##") and any(
            k in low for k in ("skeptic", "alternative", "false positive", "not a finding")
        ):
            in_section = True
            continue
        if low.startswith("##"):
            in_section = False
        if not in_section:
            continue
        # bullet lines
        m = re.match(r"^[-*]\s+(.+)$", line.strip())
        if m:
            text = m.group(1).strip()
            if len(text) > 12:
                out.append(text[:200])
    return out[:8]


class SkillDecisionAdvisor:
    """Route internal skills and extract decision-policy metadata only."""

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        *,
        registry: Optional[SkillRegistry] = None,
        load_bodies: bool = True,
    ):
        self.skills_dir = Path(skills_dir) if skills_dir else _DEFAULT_SKILLS
        self.registry = registry or SkillRegistry()
        if registry is None and self.skills_dir.is_dir():
            self.registry.load_directory(self.skills_dir)
        self.load_bodies = load_bodies
        self.last_advice: Optional[SkillAdvice] = None

    def advise(
        self,
        *,
        methodology: Optional[str] = None,
        technologies: Optional[list[str]] = None,
        vulnerability_hint: Optional[str] = None,
    ) -> SkillAdvice:
        tech = [t.lower() for t in (technologies or [])]
        meth = (methodology or "").lower().strip()
        hint = vulnerability_hint
        if not hint and meth in ("authorization", "authz", "bola", "idor"):
            hint = "idor"
        if not hint and meth:
            hint = meth

        # Metadata routing only — ignore engagement-graph dependencies here
        selected = self.registry.route(
            technologies=tech,
            vulnerability_hint=hint,
        )
        # Prefer authz skill when methodology is authorization even if tech empty
        if meth in ("authorization", "authz", "bola", "idor"):
            try:
                authz = self.registry.get("authz-idor-analysis")
                if authz not in selected:
                    selected = [authz] + list(selected)
            except KeyError:
                pass

        advice = SkillAdvice()
        for skill in selected:
            meta = skill.metadata
            # Trust gate: internal or high trust only
            if meta.provenance != "internal" and meta.trust_score < 0.6:
                continue
            # Research-loop: report packaging never drives hypothesis selection.
            if meta.name == "report-generator":
                continue
            # Passive recon only when JS tech is present on the target.
            if meta.name == "recon-js-surface":
                if not {"react", "vue", "angular", "nextjs"}.intersection(tech):
                    continue
            advice.selected.append(meta.name)
            advice.vulnerability_hints.extend(meta.vulnerability_classes or [])
            for req in meta.evidence_requirements or []:
                if req and req not in advice.evidence_requirements:
                    advice.evidence_requirements.append(req)
            advice.provenance.append(
                {
                    "skill": meta.name,
                    "version": meta.version,
                    "provenance": meta.provenance,
                    "trust_score": meta.trust_score,
                    "source": str(skill.root_dir / "metadata.yaml"),
                }
            )
            if self.load_bodies:
                body = skill.body()
                advice.loaded.append(meta.name)
                for alt in _extract_skeptic_prompts(body):
                    tagged = f"skill:{meta.name}:{alt}"
                    if tagged not in advice.competing_explanations:
                        advice.competing_explanations.append(tagged)

        advice.influenced = bool(
            advice.competing_explanations or advice.evidence_requirements
        )
        self.last_advice = advice
        return advice

    def apply_to_retrieval(self, retrieval, advice: Optional[SkillAdvice] = None) -> int:
        """
        Merge skill competing explanations into RetrievalResult.
        Returns count of newly added explanations (observable influence).
        """
        advice = advice or self.last_advice
        if retrieval is None or advice is None:
            return 0
        added = 0
        existing = list(getattr(retrieval, "competing_explanations", None) or [])
        for alt in advice.competing_explanations:
            if alt not in existing:
                existing.append(alt)
                added += 1
        # Cap to avoid context bloat
        retrieval.competing_explanations = existing[:16]
        if added:
            advice.influenced = True
        return added

    @staticmethod
    def normalize_evidence_requirements(texts: list[str]) -> list[str]:
        """
        Map free-text skill evidence requirements to alignment-friendly tokens.
        Does not invent new security claims — only structures stated requirements.
        """
        out: list[str] = []
        for t in texts or []:
            low = (t or "").lower()
            if not low:
                continue
            # Align with experiment_alignment keyword maps (identities a/b, ownership, …)
            if any(
                k in low
                for k in (
                    "two different",
                    "two identities",
                    "diffed response",
                    "replayed under two",
                )
            ) or (
                "identity" in low
                and any(k in low for k in ("diff", "two", "pair", "both", "replay"))
            ):
                out.append("Identities A/B")
                out.append("cross_identity_pair")
            elif "ownership" in low or ("object" in low and "bound" in low):
                out.append("ownership_proof")
            else:
                # keep a short hash of free text for traceability
                token = "skill_req:" + "".join(
                    ch if ch.isalnum() or ch in "_-" else "_" for ch in low
                )[:48]
                out.append(token)
        # dedupe preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for x in out:
            if x not in seen:
                seen.add(x)
                ordered.append(x)
        return ordered

    def apply_to_experiments(
        self,
        experiments: list,
        advice: Optional[SkillAdvice] = None,
    ) -> int:
        """
        Merge normalized skill evidence requirements into Experiment.required_evidence.
        Returns number of requirement tokens newly attached across experiments.
        Only requirements from vulnerability-class skills are applied (recon packaging
        requirements must not inflate authorization experiment evidence gates).
        """
        advice = advice or self.last_advice
        if not experiments or advice is None:
            return 0
        # Prefer requirements from skills that declare vulnerability classes
        vuln_reqs: list[str] = []
        for p in advice.provenance or []:
            name = p.get("skill") or ""
            try:
                sk = self.registry.get(name)
            except KeyError:
                continue
            if sk.metadata.vulnerability_classes:
                vuln_reqs.extend(sk.metadata.evidence_requirements or [])
        # Only vulnerability-class skills may attach experiment evidence gates.
        # Recon packaging requirements must not inflate SSRF/business-logic labs.
        if not vuln_reqs:
            return 0
        tokens = self.normalize_evidence_requirements(vuln_reqs)
        tokens = [t for t in tokens if not t.startswith("skill_req:")]
        if not tokens:
            return 0
        added = 0
        for exp in experiments:
            existing = list(getattr(exp, "required_evidence", None) or [])
            for tok in tokens:
                if tok not in existing:
                    existing.append(tok)
                    added += 1
            try:
                exp.required_evidence = existing[:12]
            except Exception:
                pass
        if added:
            advice.influenced = True
        return added
