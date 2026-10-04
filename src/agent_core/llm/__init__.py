"""Optional LLM assist (OpenRouter). Never a source of findings truth."""

from agent_core.llm.openrouter import OpenRouterClient, OpenRouterStatus, probe_openrouter

__all__ = ["OpenRouterClient", "OpenRouterStatus", "probe_openrouter"]
