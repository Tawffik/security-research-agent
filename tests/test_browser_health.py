from agent_core.tools.browser_capability import playwright_available, system_chrome_available
from agent_core.tools.browser_health import check_browser_health


def test_browser_health_states_are_explicit():
    h = check_browser_health(try_launch=False)
    assert h.status in (
        "PACKAGE_MISSING",
        "BROWSER_BINARY_MISSING",
        "BROWSER_LAUNCH_FAILED",
        "BROWSER_RUNTIME_READY",
    )
    if not playwright_available():
        assert h.status == "PACKAGE_MISSING"
        assert h.playwright is False
    elif not system_chrome_available():
        assert h.status == "BROWSER_BINARY_MISSING"
    else:
        assert h.playwright is True
        assert h.chrome is True
        # without try_launch, READY means package+chrome present
        assert h.status == "BROWSER_RUNTIME_READY"
