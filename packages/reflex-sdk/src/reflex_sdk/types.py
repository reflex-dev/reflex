"""Models returned by the Reflex Cloud API."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessScope:
    """Restricts what an access token can do; a token without one has full access."""

    # Permission level per resource type, e.g. ``{"apps": "read"}``.
    permissions: dict[str, str]
    # The project ids the token is limited to, or ``"all"``. Typed as any string so
    # a keyword added by the server later still decodes.
    projects: str | list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Me:
    """The identity an access token authenticates as."""

    user_id: uuid.UUID
    # The organization the token is scoped to.
    org_id: uuid.UUID
    email: str
    # The plan of the token's organization, e.g. ``"free"`` or ``"enterprise"``.
    tier: str
    is_service_account: bool = False
    access: AccessScope | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    """An access token, listed without its secret value."""

    name: str
    creation_time: datetime.datetime
    expiration: datetime.datetime
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
    # When the deployment was created.
    timestamp: datetime.datetime
    # The region of each machine, one entry per machine.
    regions: list[str]
    vm_type_name: str
    vm_type_cpu: float
    # Memory per machine, in GB.
    vm_type_ram: float
    last_updated: datetime.datetime | None
    last_updated_by: User | None


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
    # When the deployment was created.
    timestamp: datetime.datetime
    last_updated: datetime.datetime | None
    deployment_user: User | None
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
    # When the deployment was created.
    timestamp: datetime.datetime
    deployment_user: User | None


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
    project_owner: uuid.UUID
    project_owner_email: str
    project_seats: int
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
