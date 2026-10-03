from agent_core.tools.browser_health import check_browser_health


def test_browser_health_ready_when_playwright_and_chrome():
    h = check_browser_health(try_launch=True)
    assert h.playwright is True
    assert h.chrome is True
    assert h.status == "BROWSER_RUNTIME_READY"
