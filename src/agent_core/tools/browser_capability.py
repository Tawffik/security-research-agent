"""
Browser capability — Tool Contract + ScopeGuard boundary.

Real Playwright is optional. Synthetic runtime enables offline verification.
Live navigation requires contract.live_http_allowed AND ScopeGuard ALLOW
AND explicit live_mode. Knowledge never grants permission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

from agent_core.scope.guard import RiskTier, ScopeGuard
from agent_core.tools.capability import FailureClass
from agent_core.tools.contracts import ToolAuthorizationResult, ToolContract, authorize_tool
from agent_core.tools.failure_policy import next_action_for_failure


BROWSER_NAVIGATE = ToolContract(
    name="browser_navigate",
    purpose="Navigate an in-scope URL in a constrained browser session",
    inputs=["url", "identity", "wait_until"],
    outputs=["final_url", "title", "dom_excerpt", "status"],
    cost=0.4,
    risk=0.45,
    side_effects="read",
    evidence_value=0.65,
    required_skill="browser-ui-observation",
    authorization_required=True,
    live_http_allowed=False,  # fail-closed until explicitly enabled
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
    authorized: bool = False
    synthetic: bool = True
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def host_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def authorize_browser_action(
    contract: ToolContract,
    *,
    guard: ScopeGuard,
    url: str,
    live_mode: bool = False,
    risk_tier: RiskTier = RiskTier.ACTIVE_SAFE,
) -> ToolAuthorizationResult:
    host = host_from_url(url)
    if not host:
        return ToolAuthorizationResult(
            allowed=False,
            reason="missing_or_invalid_url",
            contract_name=contract.name,
        )
    # ScopeGuard path (also covers risk tiers when used via authorize_tool)
    auth = authorize_tool(
        contract,
        guard=guard,
        host=host,
        action_description=f"{contract.name}:{url}",
        live_mode=live_mode,
    )
    if not auth.allowed:
        return auth
    # Defense in depth: re-check ScopeGuard directly for navigation host
    decision = guard.authorize(
        host=host,
        risk_tier=risk_tier,
        action_description=contract.name,
    )
    from agent_core.scope.guard import Decision
    if decision != Decision.ALLOW:
        return ToolAuthorizationResult(
            allowed=False,
            reason=f"scope_{decision.value}",
            scope_decision=decision.value,
            contract_name=contract.name,
        )
    return auth


class SyntheticBrowserRuntime:
    """
    Offline browser fixture. Does not open real network connections.
    Used for capability/contract/ScopeGuard tests without Playwright.
    """

    def __init__(self, pages: dict[str, dict[str, Any]] | None = None):
        # url -> {title, status, dom_excerpt}
        self.pages = dict(pages or {})
        self.history: list[BrowserObservation] = []
        self._n = 0

    def navigate(
        self,
        url: str,
        *,
        guard: ScopeGuard,
        live_mode: bool = False,
        identity: str = "",
    ) -> BrowserObservation:
        self._n += 1
        auth = authorize_browser_action(
            BROWSER_NAVIGATE, guard=guard, url=url, live_mode=live_mode
        )
        if not auth.allowed:
            fc = FailureClass.SCOPE_BLOCK if "scope" in auth.reason else FailureClass.AUTHORIZATION_DENIED
            if "live_http" in auth.reason:
                fc = FailureClass.ENVIRONMENT_FAILURE
            obs = BrowserObservation(
                observation_id=f"bobs-{self._n:04d}",
                action="navigate",
                url=url,
                error=auth.reason,
                failure_class=fc.value,
                authorized=False,
                synthetic=True,
                provenance={
                    "contract": BROWSER_NAVIGATE.name,
                    "next_action": next_action_for_failure(fc),
                    "identity": identity,
                },
            )
            self.history.append(obs)
            return obs

        page = self.pages.get(url) or self.pages.get(host_from_url(url)) or {}
        if not page and url not in self.pages:
            # Authorized but no fixture → observation failure (not a finding)
            obs = BrowserObservation(
                observation_id=f"bobs-{self._n:04d}",
                action="navigate",
                url=url,
                error="synthetic_page_missing",
                failure_class=FailureClass.OBSERVATION_FAILURE.value,
                authorized=True,
                synthetic=True,
                provenance={"contract": BROWSER_NAVIGATE.name, "identity": identity},
            )
            self.history.append(obs)
            return obs

        obs = BrowserObservation(
            observation_id=f"bobs-{self._n:04d}",
            action="navigate",
            url=url,
            final_url=page.get("final_url") or url,
            title=str(page.get("title") or ""),
            status=int(page.get("status") or 200),
            dom_excerpt=str(page.get("dom_excerpt") or "")[:500],
            authorized=True,
            synthetic=True,
            provenance={"contract": BROWSER_NAVIGATE.name, "identity": identity},
        )
        self.history.append(obs)
        return obs


def playwright_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False
