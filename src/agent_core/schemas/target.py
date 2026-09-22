"""Target Model — Actor, Role, Resource, Endpoint, Relationship, TargetContext, TargetGraph."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    USER = "user"
    SERVICE = "service"
    ADMIN = "admin"
    ANONYMOUS = "anonymous"
    TENANT = "tenant"
    OTHER = "other"


class ResourceType(str, Enum):
    OBJECT = "object"
    COLLECTION = "collection"
    ENDPOINT = "endpoint"
    WORKFLOW = "workflow"
    SESSION = "session"
    TOKEN = "token"
    OTHER = "other"


class Actor(BaseModel):
    actor_id: str
    name: str = ""
    actor_type: ActorType = ActorType.USER
    roles: list[str] = Field(default_factory=list)
    identities: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class Role(BaseModel):
    role_id: str
    name: str
    privileges: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.OBJECT
    name: str = ""
    owner_actor_id: Optional[str] = None
    tenant_id: Optional[str] = None
    state: Optional[str] = None
    sensitivity: str = "unknown"
    attributes: dict[str, Any] = Field(default_factory=dict)


class Endpoint(BaseModel):
    endpoint_id: str
    method: str = "GET"
    path: str
    host: str = ""
    parameters: list[str] = Field(default_factory=list)
    auth_required: bool = True
    technologies: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class RelationshipKind(str, Enum):
    OWNS = "owns"
    CAN_ACCESS = "can_access"
    PERFORMS = "performs"
    BELONGS_TO = "belongs_to"
    TRANSITIONS_TO = "transitions_to"
    DEPENDS_ON = "depends_on"
    OTHER = "other"


class Relationship(BaseModel):
    """Actor → Action → Resource → Condition edge (V2 §9)."""

    relationship_id: str
    kind: RelationshipKind
    source_id: str
    target_id: str
    action: Optional[str] = None
    condition: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TargetContext(BaseModel):
    """Normalized view of the target after ReconResultAdapter."""

    engagement_id: str
    primary_host: str = ""
    technologies: list[str] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    notes: str = ""


class TargetGraph(BaseModel):
    """Graph-friendly representation: nodes + edges."""

    engagement_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[Relationship] = Field(default_factory=list)
    version: int = 1
