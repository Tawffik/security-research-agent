"""Tests for MockTransport and HttpTransport (no live network required)."""

from __future__ import annotations

import io
import ssl
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_core.orchestrator.transport import HttpTransport, MockTransport, TransportResponse


def test_mock_known_fixture():
    t = MockTransport()
    r = t.fetch("api.acme-demo.test", "/v1/me")
    assert r.status == 200
    assert "user-A" in r.body


def test_mock_unknown_is_404():
    t = MockTransport()
    r = t.fetch("api.acme-demo.test", "/nope")
    assert r.status == 404


def test_http_rejects_absolute_url_in_path():
    ht = HttpTransport(scheme="https")
    try:
        ht.fetch("example.com", "https://evil.test/x")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "absolute URL" in str(e)


def test_http_rejects_invalid_host():
    ht = HttpTransport()
    try:
        ht.fetch("evil/../x", "/a")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_http_fetch_success_mocked():
    ht = HttpTransport(scheme="https", timeout_sec=5.0)

    raw_headers = {"Content-Type": "application/json; charset=utf-8"}

    class FakeResp(io.BytesIO):
        def __init__(self):
            super().__init__(b'{"ok":true}')
            self.status = 200
            self.headers = MagicMock()
            self.headers.get_content_charset.return_value = "utf-8"
            self.headers.items.return_value = list(raw_headers.items())
            self.headers.get_all.return_value = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()) as m:
        r = ht.fetch("api.example.com", "/v1/me")
        assert r.status == 200
        assert r.body == '{"ok":true}'
        assert r.error is None
        assert m.called
        req = m.call_args[0][0]
        assert req.full_url == "https://api.example.com/v1/me"


def test_http_cookie_jar_roundtrip():
    ht = HttpTransport()
    ht.set_cookie("session", "abc")

    class FakeResp(io.BytesIO):
        def __init__(self):
            super().__init__(b"ok")
            self.status = 200
            self.headers = MagicMock()
            self.headers.get_content_charset.return_value = "utf-8"
            self.headers.items.return_value = []
            self.headers.get_all.return_value = ["token=xyz; Path=/; HttpOnly"]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()) as m:
        ht.fetch("api.example.com", "/")
        req = m.call_args[0][0]
        assert "session=abc" in req.headers.get("Cookie", "")
    assert ht.cookie_jar.get("token") == "xyz"


def test_http_disallowed_method():
    ht = HttpTransport()
    try:
        ht.fetch("example.com", "/", method="DELETE")
        assert False
    except ValueError:
        pass
