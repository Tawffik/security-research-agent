"""
BugBountyCI → Agent recon artifact contract.

Does NOT call or clone BugBountyCI.
Validates/normalizes a consumer-facing recon JSON so the same ReconResultAdapter path works
when a real BBCI export is provided later.

Honest status: CONTRACT + VALIDATOR implemented; END-TO-END with live BBCI not verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


REQUIRED_TOP_LEVEL = ("primary_host",)
OPTIONAL_LISTS = ("endpoints", "actors", "resources", "technologies", "urls", "domains")


@dataclass
class ContractIssue:
    level: str  # error | warning
    code: str
    message: str


@dataclass
class BBCIContractResult:
    ok: bool
    normalized: dict[str, Any] = field(default_factory=dict)
    issues: list[ContractIssue] = field(default_factory=list)
    source_shape: str = "unknown"

    def error_messages(self) -> list[str]:
        return [i.message for i in self.issues if i.level == "error"]


def _as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def normalize_bbci_artifact(raw: dict[str, Any]) -> BBCIContractResult:
    """
    Accept common shapes:
    - agent fixture: {primary_host, endpoints[{method,path}], actors, resources}
    - BBCI-ish: {host|target|primary_host, urls|endpoints, assets, identities}
    """
    issues: list[ContractIssue] = []
    if not isinstance(raw, dict):
        return BBCIContractResult(False, issues=[ContractIssue("error", "not_object", "artifact must be a JSON object")])

    data = dict(raw)
    # unwrap common wrappers
    for key in ("recon", "result", "data", "artifact"):
        if key in data and isinstance(data[key], dict) and "primary_host" not in data and "host" not in data:
            data = {**data[key], **{k: v for k, v in data.items() if k != key}}
            issues.append(ContractIssue("warning", "unwrapped", f"unwrapped nested key '{key}'"))
            break

    host = (
        data.get("primary_host")
        or data.get("host")
        or data.get("target")
        or data.get("domain")
        or ""
    )
    host = str(host).strip()
    if not host and isinstance(data.get("domains"), list) and data["domains"]:
        host = str(data["domains"][0])
    if not host:
        issues.append(ContractIssue("error", "missing_host", "primary_host/host/target required"))
        return BBCIContractResult(False, issues=issues, source_shape="invalid")

    endpoints_in = _as_list(data.get("endpoints") or data.get("urls") or data.get("api_endpoints"))
    endpoints: list[dict[str, Any]] = []
    for item in endpoints_in:
        if isinstance(item, str):
            endpoints.append({"method": "GET", "path": item if item.startswith("/") else f"/{item}"})
        elif isinstance(item, dict):
            path = item.get("path") or item.get("url") or item.get("uri") or ""
            method = item.get("method") or item.get("verb") or "GET"
            if path:
                # strip scheme/host if full URL
                if path.startswith("http"):
                    try:
                        from urllib.parse import urlparse

                        path = urlparse(path).path or "/"
                    except Exception:
                        pass
                endpoints.append({"method": str(method).upper(), "path": str(path)})
        else:
            issues.append(ContractIssue("warning", "skip_endpoint", f"skipped endpoint entry type={type(item).__name__}"))

    actors_in = _as_list(data.get("actors") or data.get("identities") or data.get("users"))
    actors: list[dict[str, Any]] = []
    for a in actors_in:
        if isinstance(a, str):
            actors.append({"actor_id": a, "name": a, "type": "user"})
        elif isinstance(a, dict):
            aid = a.get("actor_id") or a.get("id") or a.get("name") or a.get("username")
            if aid:
                actors.append(
                    {
                        "actor_id": str(aid),
                        "name": str(a.get("name") or aid),
                        "type": str(a.get("type") or "user"),
                        "roles": list(a.get("roles") or []),
                    }
                )

    resources_in = _as_list(data.get("resources") or data.get("objects") or data.get("assets"))
    resources: list[dict[str, Any]] = []
    for r in resources_in:
        if isinstance(r, str):
            resources.append({"name": r, "type": "object"})
        elif isinstance(r, dict):
            name = r.get("name") or r.get("id") or r.get("resource")
            if name:
                resources.append(
                    {
                        "name": str(name),
                        "type": str(r.get("type") or "object"),
                        "owner_actor_id": r.get("owner_actor_id") or r.get("owner"),
                    }
                )

    technologies = list(dict.fromkeys(_as_list(data.get("technologies") or data.get("tech") or [])))

    shape = "agent_fixture" if "primary_host" in raw else "bbci_like"
    normalized = {
        "primary_host": host,
        "technologies": [str(t) for t in technologies],
        "endpoints": endpoints,
        "actors": actors,
        "resources": resources,
        "notes": str(data.get("notes") or data.get("source") or "bbci_contract_normalized"),
        "provenance": {
            "contract": "bbci_recon_v1",
            "source_shape": shape,
        },
    }

    if not endpoints:
        issues.append(ContractIssue("warning", "no_endpoints", "no endpoints/urls found after normalize"))

    ok = not any(i.level == "error" for i in issues)
    return BBCIContractResult(ok=ok, normalized=normalized, issues=issues, source_shape=shape)
