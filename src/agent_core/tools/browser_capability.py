"""
Browser capability — Tool Contract + ScopeGuard boundary.

Runtimes:
  - SyntheticBrowserRuntime: offline fixtures (always available)
  - PlaywrightBrowserRuntime: real browser when playwright + system Chrome exist

Live network navigation requires:
  contract.live_http_allowed AND explicit live_mode AND ScopeGuard ALLOW.
Knowledge never grants permission. UI visibility ≠ vulnerability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

from agent_core.scope.guard import Decision, RiskTier, ScopeGuard
from agent_core.tools.capability import FailureClass
from agent_core.tools.contracts import ToolAuthorizationResult, ToolContract, authorize_tool
from agent_core.tools.failure_policy import next_action_for_failure


BROWSER_NAVIGATE = ToolContract(
    name="browser_navigate",
    purpose="Navigate an in-scope URL in a constrained browser session (offline/default)",
    inputs=["url", "identity", "wait_until"],
    outputs=["final_url", "title", "dom_excerpt", "status"],
    cost=0.4,
    risk=0.45,
    side_effects="read",
    evidence_value=0.65,
    required_skill="browser-ui-observation",
    authorization_required=True,
    live_http_allowed=False,
)

BROWSER_NAVIGATE_LIVE = ToolContract(
    name="browser_navigate_live",
    purpose="Authorized live browser navigation (explicit live contract only)",
    inputs=["url", "identity", "wait_until"],
    outputs=["final_url", "title", "dom_excerpt", "status"],
    cost=0.5,
    risk=0.55,
    side_effects="read",
    evidence_value=0.7,
    required_skill="browser-ui-observation",
    authorization_required=True,
    live_http_allowed=True,
)

BROWSER_INTERACT = ToolContract(
    name="browser_interact",
    purpose="Constrained UI interaction on an already-authorized page",
    inputs=["selector", "action", "value"],
    outputs=["observation", "error"],
    cost=0.35,
    risk=0.5,
    side_effects="state_change",
    evidence_value=0.55,
    required_skill="browser-ui-observation",
    authorization_required=True,
    live_http_allowed=False,
)

# Browser-local failure labels mapped into FailureClass
BROWSER_FAILURE_MAP = {
    "scope_block": FailureClass.SCOPE_BLOCK,
    "authorization_denied": FailureClass.AUTHORIZATION_DENIED,
    "auth_state_missing": FailureClass.AUTH_STATE_MISSING,
    "capability_not_exposed": FailureClass.CAPABILITY_NOT_EXPOSED,
    "browser_runtime_failure": FailureClass.ENVIRONMENT_FAILURE,
    "navigation_failure": FailureClass.TOOL_FAILURE,
    "interaction_failure": FailureClass.TOOL_FAILURE,
    "observation_failure": FailureClass.OBSERVATION_FAILURE,
    "timeout": FailureClass.ENVIRONMENT_FAILURE,
    "environment_failure": FailureClass.ENVIRONMENT_FAILURE,
}


@dataclass
class BrowserObservation:
    observation_id: str
    action: str
    url: str = ""
    final_url: str = ""
    title: str = ""
    status: int = 0
    dom_excerpt: str = ""
    error: str = ""
    failure_class: str = ""
    browser_failure: str = ""  # specific browser taxonomy label
    authorized: bool = False
    synthetic: bool = True
    selector: str = ""
    polarity_hint: str = "neutral"  # never treated as finding alone
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def host_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_local_only_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("data:") or u.startswith("about:") or u.startswith("file://")


def playwright_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False


def system_chrome_available() -> bool:
    from pathlib import Path

    return any(
        Path(p).exists()
        for p in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser")
    )


def authorize_browser_action(
    contract: ToolContract,
    *,
    guard: ScopeGuard,
    url: str,
    live_mode: bool = False,
    risk_tier: RiskTier = RiskTier.ACTIVE_SAFE,
) -> ToolAuthorizationResult:
    # data:/about: local fixtures need no host scope; still no live network
    if is_local_only_url(url) and not live_mode:
        return ToolAuthorizationResult(
            allowed=True,
            reason="local_fixture_url",
            scope_decision="local",
            contract_name=contract.name,
        )

    host = host_from_url(url)
    if not host:
        return ToolAuthorizationResult(
            allowed=False,
            reason="missing_or_invalid_url",
            contract_name=contract.name,
        )
    auth = authorize_tool(
        contract,
        guard=guard,
        host=host,
        action_description=f"{contract.name}:{url}",
        live_mode=live_mode,
    )
    if not auth.allowed:
        return auth
    decision = guard.authorize(
        host=host,
        risk_tier=risk_tier,
        action_description=contract.name,
    )
    if decision != Decision.ALLOW:
        return ToolAuthorizationResult(
            allowed=False,
            reason=f"scope_{decision.value}",
            scope_decision=decision.value,
            contract_name=contract.name,
        )
    return auth


class SyntheticBrowserRuntime:
    """Offline browser fixture. No network."""

    def __init__(self, pages: dict[str, dict[str, Any]] | None = None):
        self.pages = dict(pages or {})
        self.history: list[BrowserObservation] = []
        self._n = 0
        self._current_url = ""

    def _obs(self, **kwargs: Any) -> BrowserObservation:
        self._n += 1
        o = BrowserObservation(observation_id=f"bobs-{self._n:04d}", **kwargs)
        self.history.append(o)
        return o

    def navigate(
        self,
        url: str,
        *,
        guard: ScopeGuard,
        live_mode: bool = False,
        identity: str = "",
        contract: ToolContract | None = None,
    ) -> BrowserObservation:
        contract = contract or BROWSER_NAVIGATE
        auth = authorize_browser_action(contract, guard=guard, url=url, live_mode=live_mode)
        if not auth.allowed:
            bf = "scope_block" if "scope" in auth.reason else "authorization_denied"
            if "live_http" in auth.reason:
                bf = "environment_failure"
            fc = BROWSER_FAILURE_MAP[bf]
            return self._obs(
                action="navigate",
                url=url,
                error=auth.reason,
                failure_class=fc.value,
                browser_failure=bf,
                authorized=False,
                synthetic=True,
                provenance={
                    "contract": contract.name,
                    "next_action": next_action_for_failure(fc),
                    "identity": identity,
                },
            )

        page = self.pages.get(url) or self.pages.get(host_from_url(url)) or {}
        if not page and not is_local_only_url(url):
            return self._obs(
                action="navigate",
                url=url,
                error="synthetic_page_missing",
                failure_class=FailureClass.OBSERVATION_FAILURE.value,
                browser_failure="observation_failure",
                authorized=True,
                synthetic=True,
                provenance={"contract": contract.name, "identity": identity},
            )

        self._current_url = page.get("final_url") or url
        return self._obs(
            action="navigate",
            url=url,
            final_url=self._current_url,
            title=str(page.get("title") or ("local" if is_local_only_url(url) else "")),
            status=int(page.get("status") or 200),
            dom_excerpt=str(page.get("dom_excerpt") or "")[:500],
            authorized=True,
            synthetic=True,
            provenance={"contract": contract.name, "identity": identity},
        )

    def interact(
        self,
        action: str,
        *,
        guard: ScopeGuard,
        selector: str = "",
        value: str = "",
        page_url: str = "",
        identity: str = "",
    ) -> BrowserObservation:
        url = page_url or self._current_url
        if not url:
            return self._obs(
                action=action,
                error="no_current_page",
                failure_class=FailureClass.PRECONDITION_MISSING.value,
                browser_failure="precondition_missing",
                authorized=False,
                synthetic=True,
                selector=selector,
                provenance={"contract": BROWSER_INTERACT.name},
            )
        # Interaction inherits page host scope
        auth = authorize_browser_action(
            BROWSER_INTERACT, guard=guard, url=url, live_mode=False
        )
        if not auth.allowed and not is_local_only_url(url):
            return self._obs(
                action=action,
                url=url,
                error=auth.reason,
                failure_class=FailureClass.SCOPE_BLOCK.value,
                browser_failure="scope_block",
                authorized=False,
                synthetic=True,
                selector=selector,
                provenance={"contract": BROWSER_INTERACT.name},
            )
        if action not in ("click", "fill", "submit", "select", "extract"):
            return self._obs(
                action=action,
                url=url,
                error="unsupported_interaction",
                failure_class=FailureClass.CAPABILITY_NOT_EXPOSED.value,
                browser_failure="capability_not_exposed",
                authorized=True,
                synthetic=True,
                selector=selector,
            )
        page = self.pages.get(url) or {}
        elements = page.get("elements") or {}
        if selector and selector not in elements and action != "extract":
            return self._obs(
                action=action,
                url=url,
                error="selector_not_found",
                failure_class=FailureClass.TOOL_FAILURE.value,
                browser_failure="interaction_failure",
                authorized=True,
                synthetic=True,
                selector=selector,
            )
        return self._obs(
            action=action,
            url=url,
            final_url=url,
            title=str(page.get("title") or ""),
            status=200,
            dom_excerpt=str(elements.get(selector) or page.get("dom_excerpt") or value)[:500],
            authorized=True,
            synthetic=True,
            selector=selector,
            provenance={"contract": BROWSER_INTERACT.name, "identity": identity, "value": value[:80]},
        )


class PlaywrightBrowserRuntime:
    """
    Real browser via Playwright + system Chrome channel.
    Network URLs require live_mode and BROWSER_NAVIGATE_LIVE contract.
    data:/about: allowed without live_mode for deterministic tests.
    """

    def __init__(self, *, channel: str = "chrome", headless: bool = True):
        if not playwright_available():
            raise RuntimeError("playwright_not_installed")
        self.channel = channel
        self.headless = headless
        self.history: list[BrowserObservation] = []
        self._n = 0

    def _obs(self, **kwargs: Any) -> BrowserObservation:
        self._n += 1
        o = BrowserObservation(
            observation_id=f"pbobs-{self._n:04d}",
            synthetic=False,
            **kwargs,
        )
        self.history.append(o)
        return o

    def navigate(
        self,
        url: str,
        *,
        guard: ScopeGuard,
        live_mode: bool = False,
        identity: str = "",
        timeout_ms: int = 5000,
    ) -> BrowserObservation:
        contract = BROWSER_NAVIGATE_LIVE if live_mode else BROWSER_NAVIGATE
        # Network URL without live_mode → deny
        if not is_local_only_url(url) and not live_mode:
            return self._obs(
                action="navigate",
                url=url,
                error="live_mode_required_for_network_url",
                failure_class=FailureClass.ENVIRONMENT_FAILURE.value,
                browser_failure="environment_failure",
                authorized=False,
                provenance={"contract": contract.name},
            )
        auth = authorize_browser_action(contract, guard=guard, url=url, live_mode=live_mode)
        if not auth.allowed:
            bf = "scope_block" if "scope" in auth.reason else "authorization_denied"
            if "live_http" in auth.reason:
                bf = "environment_failure"
            fc = BROWSER_FAILURE_MAP.get(bf, FailureClass.AUTHORIZATION_DENIED)
            return self._obs(
                action="navigate",
                url=url,
                error=auth.reason,
                failure_class=fc.value,
                browser_failure=bf,
                authorized=False,
                provenance={"contract": contract.name, "identity": identity},
            )

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(channel=self.channel, headless=self.headless)
                page = browser.new_page()
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    status = int(resp.status) if resp else 0
                    title = page.title() or ""
                    final_url = page.url
                    body = page.content()[:500]
                    browser.close()
                    return self._obs(
                        action="navigate",
                        url=url,
                        final_url=final_url,
                        title=title,
                        status=status,
                        dom_excerpt=body,
                        authorized=True,
                        provenance={
                            "contract": contract.name,
                            "identity": identity,
                            "runtime": "playwright",
                            "channel": self.channel,
                        },
                    )
                except Exception as e:
                    browser.close()
                    msg = str(e)[:200]
                    bf = "timeout" if "timeout" in msg.lower() else "navigation_failure"
                    fc = BROWSER_FAILURE_MAP[bf]
                    return self._obs(
                        action="navigate",
                        url=url,
                        error=msg,
                        failure_class=fc.value,
                        browser_failure=bf,
                        authorized=True,
                        provenance={"contract": contract.name, "runtime": "playwright"},
                    )
        except Exception as e:
            return self._obs(
                action="navigate",
                url=url,
                error=str(e)[:200],
                failure_class=FailureClass.ENVIRONMENT_FAILURE.value,
                browser_failure="browser_runtime_failure",
                authorized=False,
                provenance={"runtime": "playwright"},
            )
