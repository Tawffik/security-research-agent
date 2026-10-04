"""Control-plane authentication.

Two mechanisms:
1. Bearer AGENT_API_TOKEN — for trusted programmatic clients (never sent to browsers).
2. Signed HttpOnly session cookie — for the mobile UI after bootstrap on GET /.

The long-lived AGENT_API_TOKEN never leaves the server process.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Optional

COOKIE_NAME = "sra_cp_session"
# Default session lifetime: 12 hours
SESSION_TTL_SECONDS = int(os.environ.get("AGENT_SESSION_TTL_SECONDS", str(12 * 3600)))


def get_agent_token() -> str:
    return os.environ.get("AGENT_API_TOKEN", "").strip()


def token_configured() -> bool:
    t = get_agent_token()
    return len(t) >= 16


def _session_key() -> bytes:
    """Derive a signing key from AGENT_API_TOKEN without exposing the token."""
    token = get_agent_token()
    if not token:
        return b""
    return hashlib.sha256(b"sra-cp-session-v1|" + token.encode("utf-8")).digest()


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


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def mint_session_cookie_value(*, now: Optional[float] = None) -> str:
    """Create a signed session token (not the API secret)."""
    key = _session_key()
    if not key:
        raise RuntimeError("cannot_mint_session_without_agent_token")
    ts = int(now if now is not None else time.time())
    payload = f"v1.{ts}".encode("utf-8")
    sig = hmac.new(key, payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify_session_cookie_value(value: Optional[str], *, now: Optional[float] = None) -> bool:
    if not value or not token_configured():
        return False
    key = _session_key()
    if not key:
        return False
    try:
        body_b64, sig_b64 = value.split(".", 1)
        payload = _unb64(body_b64)
        sig = _unb64(sig_b64)
        expected = hmac.new(key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return False
        text = payload.decode("utf-8")
        if not text.startswith("v1."):
            return False
        ts = int(text.split(".", 1)[1])
        current = int(now if now is not None else time.time())
        if current - ts > SESSION_TTL_SECONDS:
            return False
        if ts > current + 60:
            return False  # clock skew / future token
        return True
    except Exception:
        return False


def is_authenticated(
    authorization_header: Optional[str] = None,
    session_cookie: Optional[str] = None,
) -> bool:
    if verify_bearer(authorization_header):
        return True
    if verify_session_cookie_value(session_cookie):
        return True
    return False
