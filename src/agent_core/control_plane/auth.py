"""Single-user token auth — secrets from environment only."""

from __future__ import annotations

import hmac
import os
from typing import Optional


def get_agent_token() -> str:
    return os.environ.get("AGENT_API_TOKEN", "").strip()


def token_configured() -> bool:
    t = get_agent_token()
    return len(t) >= 16


def verify_bearer(authorization_header: Optional[str]) -> bool:
    expected = get_agent_token()
    if not expected or len(expected) < 16:
        return False
    if not authorization_header:
        return False
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    provided = parts[1].strip()
    return hmac.compare_digest(provided, expected)
