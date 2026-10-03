"""Browser runtime health — distinguish package/binary/launch states."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from agent_core.tools.browser_capability import playwright_available, system_chrome_available


@dataclass
class BrowserHealth:
    status: str  # PACKAGE_MISSING | BROWSER_BINARY_MISSING | BROWSER_LAUNCH_FAILED | BROWSER_RUNTIME_READY
    playwright: bool = False
    chrome: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_browser_health(*, try_launch: bool = True) -> BrowserHealth:
    if not playwright_available():
        return BrowserHealth(status="PACKAGE_MISSING", playwright=False, chrome=system_chrome_available(), detail="playwright not importable")
    chrome = system_chrome_available()
    if not chrome:
        return BrowserHealth(status="BROWSER_BINARY_MISSING", playwright=True, chrome=False, detail="no system Chrome/Chromium found")
    if not try_launch:
        return BrowserHealth(status="BROWSER_RUNTIME_READY", playwright=True, chrome=True, detail="package+chrome present (launch not probed)")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            page.goto("data:text/html,<title>health</title>")
            title = page.title()
            browser.close()
        if title != "health":
            return BrowserHealth(status="BROWSER_LAUNCH_FAILED", playwright=True, chrome=True, detail=f"unexpected title {title!r}")
        return BrowserHealth(status="BROWSER_RUNTIME_READY", playwright=True, chrome=True, detail="channel=chrome launch ok")
    except Exception as e:
        return BrowserHealth(status="BROWSER_LAUNCH_FAILED", playwright=True, chrome=True, detail=str(e)[:200])
