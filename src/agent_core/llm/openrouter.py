"""OpenRouter client — optional assist only.

Security rules:
- Findings / evidence / polarity never come from the model alone.
- Missing key → disabled (fail closed for LLM features, research loop still works).
- API key never logged or returned in API responses.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

DEFAULT_BASE = "https://openrouter.ai/api/v1"
# Free-tier oriented defaults (override with OPENROUTER_MODEL)
DEFAULT_MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "meta-llama/llama-3.2-3b-instruct:free",
)


@dataclass
class OpenRouterStatus:
    configured: bool
    reachable: bool = False
    model: str = DEFAULT_MODEL
    error: str = ""
    sample_ok: bool = False
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # never include key material
        return d


def _api_key() -> str:
    return (
        os.environ.get("OPENROUTER_API_KEY", "").strip()
        or os.environ.get("OPENROUTER_KEY", "").strip()
    )


def is_configured() -> bool:
    k = _api_key()
    return len(k) >= 8


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: float = 45.0,
    ) -> None:
        self.api_key = (api_key if api_key is not None else _api_key()).strip()
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return len(self.api_key) >= 8

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("openrouter_not_configured")
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://github.com/Tawffik/security-research-agent"),
                "X-Title": "security-research-agent",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def simple_complete(self, prompt: str, *, system: str = "") -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        out = self.chat(messages)
        choices = out.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return str(msg.get("content") or "")


def probe_openrouter(*, live_call: bool = True) -> OpenRouterStatus:
    """Connectivity probe. Does not print or return the API key."""
    st = OpenRouterStatus(configured=is_configured(), model=DEFAULT_MODEL)
    if not st.configured:
        st.error = "OPENROUTER_API_KEY not set"
        return st
    if not live_call:
        st.reachable = True
        return st
    import time

    client = OpenRouterClient()
    t0 = time.time()
    try:
        text = client.simple_complete(
            "Reply with exactly: PONG",
            system="You are a connectivity probe. Reply with only the requested token.",
        )
        st.latency_ms = int((time.time() - t0) * 1000)
        st.reachable = True
        st.sample_ok = "PONG" in (text or "").upper()
        if not st.sample_ok:
            st.error = f"unexpected_reply:{text[:80]!r}"
    except urllib.error.HTTPError as e:
        st.latency_ms = int((time.time() - t0) * 1000)
        st.error = f"http_{e.code}"
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
            st.error = f"http_{e.code}:{body}"
        except Exception:
            pass
    except Exception as e:
        st.latency_ms = int((time.time() - t0) * 1000)
        st.error = type(e).__name__ + ":" + str(e)[:120]
    return st
