"""
Tool Registry (V2 §18–19).

Tools are contracts with risk/cost/scope metadata. The LLM never sees a
flat dump of 50 tools — retrieval returns a small candidate set for JEV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolContract:
    name: str
    purpose: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    cost: str = "medium"  # low | medium | high
    risk: str = "active"  # passive | active | risky | destructive
    side_effects: str = "none"
    scope: str = "target_only"
    timeout_sec: float = 30.0
    evidence_value: float = 0.5
    required_skill: Optional[str] = None


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolContract] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            ToolContract(
                name="http_request",
                purpose="Authenticated or anonymous HTTP request to in-scope host",
                inputs=["method", "path", "headers", "body", "identity"],
                outputs=["status", "headers", "body"],
                cost="medium",
                risk="active",
                side_effects="possible",
                evidence_value=0.7,
            ),
            ToolContract(
                name="authenticated_http_request",
                purpose="HTTP request under a named engagement identity",
                inputs=["method", "path", "identity", "body"],
                outputs=["status", "body", "identity_used"],
                cost="medium",
                risk="active",
                side_effects="possible",
                evidence_value=0.85,
                required_skill="authz-idor-analysis",
            ),
            ToolContract(
                name="diff_response_by_identity",
                purpose="Compare two responses for security-relevant divergence",
                inputs=["response_a", "response_b", "identity_a", "identity_b"],
                outputs=["diff_summary", "security_relevant"],
                cost="low",
                risk="passive",
                side_effects="none",
                evidence_value=0.9,
            ),
            ToolContract(
                name="http_get",
                purpose="Safe GET only",
                inputs=["path", "host"],
                outputs=["status", "body"],
                cost="low",
                risk="passive",
                side_effects="none",
                evidence_value=0.4,
            ),
        ]
        for t in defaults:
            self._tools[t.name] = t

    def get(self, name: str) -> Optional[ToolContract]:
        return self._tools.get(name)

    def list_all(self) -> list[ToolContract]:
        return list(self._tools.values())

    def retrieve(self, task_hint: str, limit: int = 5) -> list[ToolContract]:
        """Simple keyword retrieval — replace later with better ranking."""
        hint = task_hint.lower()
        scored: list[tuple[float, ToolContract]] = []
        for t in self._tools.values():
            score = 0.0
            blob = f"{t.name} {t.purpose} {' '.join(t.inputs)}".lower()
            for token in hint.split():
                if token in blob:
                    score += 1.0
            score += t.evidence_value * 0.5
            if score > 0:
                scored.append((score, t))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:limit]] or list(self._tools.values())[:limit]

    def register(self, tool: ToolContract) -> None:
        self._tools[tool.name] = tool
