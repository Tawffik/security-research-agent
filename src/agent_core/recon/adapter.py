"""
ReconResultAdapter (V2 §7).

Raw Recon → Validation → Normalization → Deduplication → Classification → Target Model inputs.

Does NOT depend on BugBountyCI at runtime. Accepts any dict/JSON matching the
fixture shape; when BugBountyCI artifacts are available they plug in the same path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

from agent_core.schemas.target import (
    Actor,
    ActorType,
    Endpoint,
    Relationship,
    RelationshipKind,
    Resource,
    ResourceType,
    Role,
    TargetContext,
    TargetGraph,
)


class RawRecon:
    """Thin wrapper over a recon dict for validation."""

    def __init__(self, data: dict[str, Any]):
        if not isinstance(data, dict):
            raise TypeError("recon must be a dict")
        self.data = data

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "RawRecon":
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawRecon":
        return cls(data)


class ReconResultAdapter:
    """
    Deterministic normalizer: same recon → same TargetContext + TargetGraph.
    """

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id

    def adapt(self, recon: RawRecon) -> tuple[TargetContext, TargetGraph, dict[str, Any]]:
        data = recon.data
        self._validate(data)

        primary_host = str(data.get("primary_host") or "")
        technologies = list(dict.fromkeys(data.get("technologies") or []))

        actors = self._normalize_actors(data.get("actors") or [])
        roles = self._derive_roles(actors)
        resources = self._normalize_resources(data.get("resources") or [])
        endpoints = self._normalize_endpoints(data.get("endpoints") or [])

        ctx = TargetContext(
            engagement_id=self.engagement_id,
            primary_host=primary_host,
            technologies=technologies,
            actors=actors,
            roles=roles,
            resources=resources,
            endpoints=endpoints,
            notes=str(data.get("notes") or ""),
        )

        graph = self._build_graph(ctx, data)
        normalized = {
            "recon_id": data.get("recon_id"),
            "source": data.get("source", "unknown"),
            "hosts": data.get("hosts") or ([primary_host] if primary_host else []),
            "endpoint_count": len(endpoints),
            "actor_count": len(actors),
            "resource_count": len(resources),
        }
        return ctx, graph, normalized

    def _validate(self, data: dict[str, Any]) -> None:
        if not data.get("primary_host") and not (data.get("hosts") or data.get("endpoints")):
            raise ValueError("recon must include primary_host, hosts, or endpoints")

    def _normalize_actors(self, raw: list[dict[str, Any]]) -> list[Actor]:
        seen: set[str] = set()
        out: list[Actor] = []
        for i, a in enumerate(raw):
            name = str(a.get("name") or f"actor_{i}")
            actor_id = f"actor:{name}"
            if actor_id in seen:
                continue
            seen.add(actor_id)
            roles = list(a.get("roles") or [])
            identity = a.get("identity")
            identities = [str(identity)] if identity else []
            actor_type = ActorType.ADMIN if "admin" in roles else ActorType.USER
            out.append(
                Actor(
                    actor_id=actor_id,
                    name=name,
                    actor_type=actor_type,
                    roles=roles,
                    identities=identities,
                    attributes={k: v for k, v in a.items() if k not in ("name", "roles", "identity")},
                )
            )
        return out

    def _derive_roles(self, actors: list[Actor]) -> list[Role]:
        role_names: dict[str, Role] = {}
        for a in actors:
            for r in a.roles:
                if r not in role_names:
                    role_names[r] = Role(role_id=f"role:{r}", name=r)
        return list(role_names.values())

    def _normalize_resources(self, raw: list[dict[str, Any]]) -> list[Resource]:
        seen: set[str] = set()
        out: list[Resource] = []
        for i, r in enumerate(raw):
            name = str(r.get("name") or f"resource_{i}")
            rid = f"resource:{name}"
            if rid in seen:
                continue
            seen.add(rid)
            owner = r.get("owner")
            owner_id = f"actor:{owner}" if owner else None
            rtype = ResourceType.OBJECT
            if str(r.get("type", "")).lower() == "collection":
                rtype = ResourceType.COLLECTION
            out.append(
                Resource(
                    resource_id=rid,
                    resource_type=rtype,
                    name=name,
                    owner_actor_id=owner_id,
                    state=r.get("state"),
                    attributes={k: v for k, v in r.items() if k not in ("name", "type", "owner", "state")},
                )
            )
        return out

    def _normalize_endpoints(self, raw: list[dict[str, Any]]) -> list[Endpoint]:
        seen: set[str] = set()
        out: list[Endpoint] = []
        for i, e in enumerate(raw):
            method = str(e.get("method") or "GET").upper()
            path = str(e.get("path") or f"/unknown/{i}")
            host = str(e.get("host") or "")
            eid = f"endpoint:{method}:{host}{path}"
            if eid in seen:
                continue
            seen.add(eid)
            out.append(
                Endpoint(
                    endpoint_id=eid,
                    method=method,
                    path=path,
                    host=host,
                    parameters=list(e.get("parameters") or []),
                    auth_required=bool(e.get("auth_required", True)),
                    technologies=list(e.get("technologies") or []),
                )
            )
        return out

    def _build_graph(self, ctx: TargetContext, data: dict[str, Any]) -> TargetGraph:
        nodes: list[dict[str, Any]] = []
        edges: list[Relationship] = []

        for a in ctx.actors:
            nodes.append({"id": a.actor_id, "kind": "actor", "label": a.name, "roles": a.roles})
        for r in ctx.resources:
            nodes.append(
                {
                    "id": r.resource_id,
                    "kind": "resource",
                    "label": r.name,
                    "state": r.state,
                    "owner": r.owner_actor_id,
                }
            )
            if r.owner_actor_id:
                edges.append(
                    Relationship(
                        relationship_id=f"rel:{r.owner_actor_id}:owns:{r.resource_id}",
                        kind=RelationshipKind.OWNS,
                        source_id=r.owner_actor_id,
                        target_id=r.resource_id,
                        action="owns",
                    )
                )
        for e in ctx.endpoints:
            nodes.append(
                {
                    "id": e.endpoint_id,
                    "kind": "endpoint",
                    "label": f"{e.method} {e.path}",
                    "host": e.host,
                    "auth_required": e.auth_required,
                }
            )
            # Heuristic: object-id path params suggest resource access surface
            if "{id}" in e.path or any(p in ("id", "order_id", "user_id") for p in e.parameters):
                for res in ctx.resources:
                    edges.append(
                        Relationship(
                            relationship_id=f"rel:{e.endpoint_id}:accesses:{res.resource_id}",
                            kind=RelationshipKind.CAN_ACCESS,
                            source_id=e.endpoint_id,
                            target_id=res.resource_id,
                            action=e.method.lower(),
                            condition="auth_required" if e.auth_required else "public",
                        )
                    )

        return TargetGraph(engagement_id=self.engagement_id, nodes=nodes, edges=edges, version=1)
