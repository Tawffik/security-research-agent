"""
Memory WriteGuard (§63).

Target content (HTML/JS/API body/errors) must NEVER become trusted
semantic memory directly.

Pipeline:
  Observation → Evidence → Verification → Episode → (optional) generalization
  → WriteGuard → Memory candidate
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class MemoryWriteDecision:
    allowed: bool
    reason: str
    sanitized_summary: str = ""


class MemoryWriteGuard:
    """
    Allow structured research summaries only.
    Reject raw target payloads and instruction-like strings.
    """

    BLOCK_MARKERS = (
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "you are now",
        "<script",
        "javascript:",
    )

    def evaluate(
        self,
        *,
        content: str,
        source: str,
        has_evidence: bool = False,
        is_structured_summary: bool = False,
    ) -> MemoryWriteDecision:
        text = (content or "").strip()
        if not text:
            return MemoryWriteDecision(False, "empty_content")

        lower = text.lower()
        for m in self.BLOCK_MARKERS:
            if m in lower:
                return MemoryWriteDecision(
                    False,
                    "blocked_instruction_like_or_script_marker",
                    sanitized_summary="",
                )

        # Raw target body heuristic: long JSON/HTML-looking without structured flag
        if not is_structured_summary:
            if source in ("target_body", "target_html", "raw_response"):
                return MemoryWriteDecision(
                    False,
                    "raw_target_content_not_allowed",
                )
            if len(text) > 2000 and not has_evidence:
                return MemoryWriteDecision(False, "oversized_unstructured_without_evidence")

        if is_structured_summary and (has_evidence or source in ("episode", "lesson", "belief", "surprise")):
            # truncate for memory
            summary = text[:500]
            return MemoryWriteDecision(True, "structured_research_summary", summary)

        if source in ("episode", "lesson", "adaptive_note") and len(text) <= 500:
            return MemoryWriteDecision(True, "short_research_note", text)

        return MemoryWriteDecision(False, "failed_write_policy")
