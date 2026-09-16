"""Models returned by the Reflex Cloud API."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

from reflex_sdk._decode import json_name


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessScope:
    """Restricts what a new access token can do; a token without one has full access."""

    # Permission level per resource type, e.g. ``{"apps": "read"}``.
    permissions: dict[str, str]
    # The project ids the token is limited to, or ``"all"``. Typed as any string so
    # a keyword added by the server later still decodes.
    projects: str | list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenAccess:
    """What the authenticating access token is restricted to."""

    # Permission level per resource type, e.g. ``{"app": "write"}``. A resource
    # type left out cannot be accessed.
    permissions: dict[str, str]
    # Whether the project permissions apply to every project, or only to
    # ``project_ids``.
    all_projects: bool = True
    project_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class Me:
    """The identity an access token authenticates as."""

    user_id: uuid.UUID
    # The organization the token is scoped to.
    org_id: uuid.UUID
    email: str
    # The plan of the token's organization: ``"Inactive"``, ``"Free"``, ``"Pro"`` or
    # ``"Enterprise"``.
    tier: str
    is_service_account: bool = False
    # None for a token with full access. Tokens from ``reflex login`` are always
    # restricted, if only to the permissions chosen when approving the login.
    access: TokenAccess | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    """An access token, listed without its secret value."""

    name: str
    created_at: datetime.datetime = field(metadata=json_name("creation_time"))
    expires_at: datetime.datetime = field(metadata=json_name("expiration"))
    org_name: str
    access: AccessScope | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    """A user referenced by another resource."""

    id: uuid.UUID
    username: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AppSummary:
    """An app as listed or searched."""

    id: uuid.UUID
    name: str
    description: str
    project_id: uuid.UUID
    # Where the app is hosted: ``"fly"`` for Reflex Cloud, ``"gcp"`` for a connected
    # Google Cloud account.
    provider: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AppDeployment:
    """The deployment currently serving an app's production environment."""

    id: uuid.UUID
    # The URL the app is served at.
    url: str
    # E.g. ``"Running"``, ``"Stopped"`` or ``"Paused"``.
    status: str
    # Why the deployment is paused: ``"credit"`` or ``"manual"``.
    pause_reason: str | None
    reflex_version: str | None
    python_version: str | None
    created_at: datetime.datetime = field(metadata=json_name("timestamp"))
    # The region of each machine, one entry per machine.
    regions: list[str]
    vm_type_name: str
    vm_type_cpu: float
    # Memory per machine, in GB.
    vm_type_ram: float
    updated_at: datetime.datetime | None = field(metadata=json_name("last_updated"))
    updated_by: User | None = field(metadata=json_name("last_updated_by"))


@dataclass(frozen=True, slots=True, kw_only=True)
class App:
    """An app and its production deployment."""

    id: uuid.UUID
    name: str
    description: str
    project_id: uuid.UUID
    org_id: uuid.UUID | None
    # Where the app is hosted: ``"fly"`` for Reflex Cloud, ``"gcp"`` for a connected
    # Google Cloud account.
    provider: str
    # Whether the frontend is served from the app's own container rather than a CDN.
    full_deploy: bool
    min_instances: int | None
    max_instances: int | None
    has_deployments: bool
    # None until a deployment of the production environment is fully provisioned.
    latest_deployment: AppDeployment | None


@dataclass(frozen=True, slots=True, kw_only=True)
class VmType:
    """The machine size of a deployment."""

    # E.g. ``"c1m1"``.
    id: str | None
    name: str
    cpu: float
    # Memory, in GB.
    ram: float


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentRecord:
    """A deployment in an app's history."""

    id: uuid.UUID
    # The URL the app is served at.
    url: str
    # The URL the app's backend is served at.
    backend_url: str
    # E.g. ``"Running"``, ``"Stopped"`` or ``"Failed"``.
    status: str
    pause_reason: str | None
    failure_code: str | None
    failure_reason: str | None
    description: str | None
    reflex_version: str | None
    python_version: str | None
    created_at: datetime.datetime = field(metadata=json_name("timestamp"))
    updated_at: datetime.datetime | None = field(metadata=json_name("last_updated"))
    # The user who deployed it.
    deployed_by: User | None = field(metadata=json_name("deployment_user"))
    vm_type: VmType | None
    environment_id: uuid.UUID | None
    environment_name: str | None
    # Whether the app can be rolled back to this deployment.
    can_rollback: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class LogRecord:
    """A line of an app's runtime logs."""

    # When the line was logged, in nanoseconds since the Unix epoch.
    ns: int
    # When the line was logged, as an ISO 8601 string.
    timestamp: str
    # The name of the process or service that logged the line.
    name: str
    # The log line, or the structured record for JSON logs.
    message: str | dict[str, Any]
    details: str | None = None
    log_level: str | None = None
    region: str | None = None
    deployment_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectTier:
    """The plan limits of a project."""

    name: str
    cpu_quota: float
    # Memory quota, in GB.
    ram_quota: float
    deployment_quota: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectRef:
    """A project identified by id and name."""

    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectSummary:
    """A project as listed, with its usage."""

    id: uuid.UUID
    name: str
    tier: ProjectTier
    app_count: int
    deployment_count: int
    cpu_usage: float
    # Memory in use, in GB.
    memory_usage: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectAppDeployment:
    """A deployment of an app, as shown in its project."""

    id: uuid.UUID
    # The URL the app is served at.
    url: str
    # The URL the app's backend is served at.
    backend_url: str
    status: str
    pause_reason: str | None
    reflex_version: str | None
    python_version: str | None
    created_at: datetime.datetime = field(metadata=json_name("timestamp"))
    # The user who deployed it.
    deployed_by: User | None = field(metadata=json_name("deployment_user"))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectApp:
    """An app, as shown in its project."""

    id: uuid.UUID
    name: str
    description: str
    # The deployment serving the app, if any.
    current_deployment: ProjectAppDeployment | None
    latest_deployment: ProjectAppDeployment | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    """A project and its apps."""

    id: uuid.UUID
    name: str
    tier: ProjectTier
    owner_id: uuid.UUID = field(metadata=json_name("project_owner"))
    owner_email: str = field(metadata=json_name("project_owner_email"))
    # The number of members.
    seats: int = field(metadata=json_name("project_seats"))
    apps: list[ProjectApp]


@dataclass(frozen=True, slots=True, kw_only=True)
class Role:
    """A role that can be granted on a project."""

    id: uuid.UUID
    name: str
    # The built-in tier the role extends: ``"admin"``, ``"editor"`` or ``"viewer"``.
    base_tier: str
    permissions: list[str]
    is_builtin: bool
    member_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectMember:
    """A user with access to a project."""

    user_id: uuid.UUID
    email: str
    # The name of the member's role.
    role: str
    base_tier: str
    # Every permission the member has on the project, including inherited ones.
    permissions: list[str]
    is_service_account: bool
