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
class DeploymentReport:
    """The state of a deployment and, once it has failed, why."""

    # E.g. ``"Pending"``, ``"AwaitingApproval"``, ``"Running"`` or ``"Failed"``.
    status: str
    # A stable identifier of the failure, e.g. ``"build_failed"``.
    code: str | None
    # Whose to fix: ``"customer"``, ``"platform"`` or ``"transient"``.
    fault: str | None
    # Why the deployment failed; empty until it has.
    reason: str
    # What to do about it; empty when there is nothing specific to suggest.
    guidance: str
    # The end of the build log, for a failed build.
    build_log_excerpt: str | None
    # Whether the build log exists but could not be read.
    build_log_unreadable: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class RunningDeployment:
    """The deployment running an app, or one of its environments."""

    id: uuid.UUID
    app_id: uuid.UUID
    # None for an app without environments.
    environment_id: uuid.UUID | None
    # The deployment this one was promoted from, for a promoted deployment.
    promoted_from_id: uuid.UUID | None = field(
        metadata=json_name("promoted_from_deployment_id")
    )
    # The URL the app is served at.
    url: str | None
    # The URL the app's backend is served at.
    backend_url: str
    reflex_version: str | None
    python_version: str | None
    # The machine size, e.g. ``"c1m1"``.
    vm_type_id: str | None = field(metadata=json_name("vmtype_id"))
    # How new instances replace old ones: ``"immediate"``, ``"rolling"``,
    # ``"bluegreen"`` or ``"canary"``.
    strategy: str
    # Whether the app's machines keep running when idle instead of pausing.
    persistent: bool = field(metadata=json_name("persist"))
    description: str | None
    created_at: datetime.datetime = field(metadata=json_name("deployment_ts"))
    # The id of the user who deployed it.
    deployed_by_id: uuid.UUID = field(metadata=json_name("deployment_user"))


@dataclass(frozen=True, slots=True, kw_only=True)
class AppMove:
    """The result of moving an app to another project."""

    project_id: uuid.UUID
    # The names of the integrations copied into the destination project.
    copied_integrations: list[str]
    # The builder threads whose repository access tokens were not moved, because
    # the caller cannot read them. Their repositories stay connected but cannot be
    # pushed to until they are reconnected.
    repo_tokens_withheld: list[uuid.UUID]
    # The builder threads whose repository access tokens failed to move.
    repo_tokens_failed: list[uuid.UUID]
    # What to tell the user about withheld or failed repository tokens.
    repo_token_notices: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceNameChange:
    """The result of renaming a Google Cloud app's Cloud Run service."""

    service_name: str
    # Whether the app was stopped and its old service deleted; it runs under the new
    # name from its next deployment.
    stopped: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DnsRecord:
    """A DNS record a custom domain needs."""

    # E.g. ``"A"``, ``"CNAME"`` or ``"TXT"``.
    type: str
    name: str
    value: str
    # Whether the record is in DNS: ``"found"``, ``"missing"``, ``"wrong"`` or
    # ``"unknown"``. None when adding a domain, and for callers who cannot manage
    # the app's domains.
    status: str | None = None
    # What DNS holds for the record instead, when it is wrong.
    observed: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CustomDomain:
    """An app's custom domain and whether it is ready to serve the app."""

    domain: str
    # Whether ownership of the domain has been verified.
    verified: bool
    # The records the domain needs, by purpose, e.g. ``"DNS_RECORD_CNAME"``. Empty for
    # callers who cannot manage the app's domains.
    dns_records: dict[str, DnsRecord]
    # E.g. ``"active"``, ``"no_records"``, ``"propagating"``,
    # ``"awaiting_certificate"``, or ``"unchecked"`` for callers who cannot manage
    # the app's domains.
    status: str
    # The status, explained.
    status_detail: str
    checked_at: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class EnvironmentDeployment:
    """The deployment serving an environment."""

    id: uuid.UUID = field(metadata=json_name("deployment_id"))
    # The hostname the environment is served at, or occasionally a full URL.
    url: str | None
    # ``"Running"``, ``"Paused"`` or ``"Error: Out of Memory"``.
    status: str
    created_at: datetime.datetime | None = field(metadata=json_name("deployment_ts"))
    description: str | None
    # The deployment this one was promoted from, for a promoted deployment.
    promoted_from_id: uuid.UUID | None = field(
        metadata=json_name("promoted_from_deployment_id")
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Environment:
    """A stage of an app's deployment pipeline, such as dev or production."""

    # The production environment's id is the app's id.
    id: uuid.UUID
    name: str
    # The environment's place in the pipeline. The first environment receives new
    # deployments, and each later one is promoted from the one before it.
    position: int
    # Whether promoting to this environment needs approval.
    requires_approval: bool
    # The subdomain to serve the environment at when it has no URL yet, as a single
    # label such as ``"my-app-staging"``.
    default_hostname: str | None
    # None while nothing is serving the environment.
    running: EnvironmentDeployment | None
    # Whether a deployment is in progress or awaiting approval.
    has_in_flight: bool
    # Whether a promotion to this environment is awaiting approval.
    has_pending_promotion: bool
    # Whether a deployment to this environment is awaiting approval.
    has_pending_deploy: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EnvironmentsEnabled:
    """The environments an app got when it was given a deployment pipeline."""

    # The new first environment, which receives new deployments.
    dev_environment_id: uuid.UUID
    # The environment serving the app as before, whose id is the app's id.
    production_environment_id: uuid.UUID = field(
        metadata=json_name("prod_environment_id")
    )
    # How many of the app's earlier deployments were assigned to production.
    backfilled_deployments: int
    # Whether production's secrets were copied to dev.
    secrets_copied: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class NewEnvironment:
    """An environment added to an app's pipeline."""

    id: uuid.UUID
    # Whether the requested secrets were copied; True when none were requested.
    secrets_copied: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Promotion:
    """A deployment promoting a version to the next environment of a pipeline."""

    deployment_id: uuid.UUID
    environment_id: uuid.UUID
    # The deployment whose build was promoted.
    source_deployment_id: uuid.UUID
    # The hostname the environment is served at.
    url: str
    # ``"Pending"``, or ``"AwaitingApproval"`` when the promotion needs approval.
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CopiedSecrets:
    """The secrets copied into an environment from the one before it."""

    # The name of the environment they were copied from.
    source: str
    # The names of the copied secrets, or None for callers who cannot see secret
    # names.
    names: list[str] | None
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedDatabase:
    """The Postgres database Reflex Cloud hosts for an app."""

    # The id of the database's project at the database provider, Neon.
    provider_project_id: str = field(metadata=json_name("project_id"))
    # E.g. ``"aws-us-east-2"``.
    region: str
    created_at: datetime.datetime
    # The database name.
    database: str
    # The database user.
    role: str
    # The production connection string with its credentials masked. The unmasked
    # one is in the app's ``DATABASE_URL`` secret.
    masked_connection_string: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SignInStatus:
    """Whether an app signs its users in with their Reflex accounts."""

    # Whether sign-in is set up: its settings are in the app's secrets.
    enabled: bool = field(metadata=json_name("has_auth"))
    # The OpenID Connect issuer the app signs users in with, while enabled.
    issuer: str | None = None
    # The app's OpenID Connect client id, which is the app's id, while enabled.
    client_id: str | None = None
    # Whether sign-ins are accepted. False while enabled means setting sign-in up
    # did not finish; enabling it again repairs it.
    client_enabled: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EndUser:
    """A Reflex account that has agreed to sign in to an app."""

    user_id: uuid.UUID
    # Empty unless the user shared their email address with the app.
    email: str
    # None unless the user shared their profile with the app.
    name: str | None
    first_consented_at: datetime.datetime
    # When the user last agreed to sign in.
    consented_at: datetime.datetime
    # When the user last signed in or refreshed their session, if they still have one.
    last_active_at: datetime.datetime | None
    blocked: bool
    # When the user was first blocked, while they are.
    blocked_at: datetime.datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EndUserPage:
    """A page of an app's users."""

    # The users, most recently consented first.
    users: list[EndUser]
    # How many users match the search.
    total: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EndUserExport:
    """Every user of an app, as a CSV file."""

    # The CSV, with a header row: ``Email``, ``Name``, ``First consented``,
    # ``Last active``, ``Consent last given``, ``Blocked since`` and ``User ID``.
    csv: str
    # Whether the file stops at its limit of 20,000 users.
    truncated: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EndUserBlock:
    """Whether a user is blocked from signing in to an app."""

    user_id: uuid.UUID
    blocked: bool
    blocked_at: datetime.datetime | None
    # How many of the user's sessions were ended, or None if ending them failed;
    # the rest end when they next refresh, or when the change is made again.
    revoked_sessions: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SignInInvite:
    """An email address invited to sign in to an app."""

    # The address, normalized: lowercase, and without dots in a Gmail address.
    email: str
    created_at: datetime.datetime
    # When an account with the address first signed in.
    redeemed_at: datetime.datetime | None
    redeemed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Audience:
    """Who may sign in to an app."""

    # ``"public"``: anyone with a Reflex account; ``"members"``: members of the app's
    # project; ``"invited"``: invited addresses and the app's editors;
    # ``"owner_only"``: the app's editors. None for a setting this SDK does not know,
    # which refuses every sign-in.
    audience: str | None
    # The invited addresses, newest first. None for callers who cannot edit the app.
    invites: list[SignInInvite] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AudienceChange:
    """The result of changing who may sign in to an app."""

    audience: str
    # Whether the setting was different before.
    changed: bool
    # How many sessions were ended, or None if ending them failed; the rest end when
    # they next refresh, or when the same setting is made again.
    revoked_sessions: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class InviteRemoval:
    """The result of withdrawing an invitation to sign in to an app."""

    # The address, normalized.
    email: str
    # How many of the address's sessions were ended, or None if ending them failed.
    revoked_sessions: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class HostnameReservation:
    """The URLs reserved for an app's next deployment, to export its build with."""

    # The URL the frontend will be served at.
    frontend_url: str = field(metadata=json_name("hostname"))
    # The URL the backend will be served at.
    backend_url: str = field(metadata=json_name("server"))


@dataclass(frozen=True, slots=True, kw_only=True)
class Region:
    """A region apps can be deployed to."""

    id: uuid.UUID
    name: str
    # The code to deploy with, e.g. ``"sjc"``.
    code: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MachineSize:
    """A machine size apps can be deployed with."""

    # The id to deploy with, e.g. ``"c1m1"``.
    id: str
    name: str
    cpu: float
    # Memory, in GB.
    ram: float
    # E.g. ``"SHARED"`` or ``"PERFORMANCE"``.
    cpu_kind: str


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RolePreviewMember:
    """A member who holds a role directly."""

    user_id: uuid.UUID
    email: str
    is_service_account: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class RolePreviewTeam:
    """A team that holds a role."""

    team_id: uuid.UUID
    team_name: str
    member_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RoleUpdatePreview:
    """What changing a role would change for the people holding it."""

    # The permissions the role would gain, sorted.
    gained: list[str]
    # The permissions the role would lose, sorted.
    lost: list[str]
    # The members holding the role directly.
    members: list[RolePreviewMember]
    # The teams holding the role, whose members are affected too.
    teams: list[RolePreviewTeam]


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamGrant:
    """A role an organization team holds on a project."""

    team_id: uuid.UUID
    team_name: str
    # The name of the role.
    role: str
    # ``"editor"`` or ``"viewer"``; teams cannot hold admin roles.
    base_tier: str
    # The permissions the role adds to its base tier.
    permissions: list[str]
    member_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingTeamChange:
    """A change to a team's access to a project that awaits approval."""

    team_id: uuid.UUID
    team_name: str
    # ``"grant"`` or ``"revoke"``.
    action: str
    # The name of the role to grant; None for a revocation.
    role: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TeamGrants:
    """The teams with access to a project."""

    # The roles teams hold, by team name.
    grants: list[TeamGrant]
    # The changes awaiting approval.
    pending: list[PendingTeamChange]


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditLogEntry:
    """An event in a project's audit log."""

    id: uuid.UUID
    timestamp: datetime.datetime
    # E.g. ``"ADD_USER"`` or ``"DEPLOY_APP"``.
    action: str
    # The action, readable, e.g. ``"Add User"``.
    action_label: str
    # The event, as a sentence.
    summary: str
    # The project, app or deployment the event is about.
    resource_id: uuid.UUID | None
    # ``"project"``, ``"app"``, ``"deployment"`` or ``"unknown"``.
    resource_type: str
    # The resource's name, or its id when it has none.
    resource_display: str
    actor_user_id: uuid.UUID
    # The actor's email address or name.
    actor_display: str
    actor_email: str | None
    actor_is_service_account: bool
    # The event's raw details.
    content: str
    # The user the event is about, such as a member who was added.
    target_user_id: uuid.UUID | None
    target_display: str | None
    target_is_service_account: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginRequest:
    """A browser login waiting for the user to approve it."""

    # Identifies the login; the approved token is collected with it.
    request_id: str
    # The page the user approves the login on.
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpConnection:
    """A Google Cloud project an organization deploys apps to."""

    id: uuid.UUID
    name: str
    # Whether new apps deploy to this connection unless told otherwise.
    is_default: bool
    # The Google Cloud project id.
    project_id: str
    # The Cloud Run region, e.g. ``"us-central1"``.
    region: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpStatus:
    """Whether an organization can deploy apps to its own Google Cloud."""

    # Whether a usable default connection exists.
    configured: bool
    # Whether the organization's plan and this deployment allow it.
    allowed: bool
    # The default connection's Google Cloud project id, if any.
    project_id: str | None
    # The default connection's region, if any.
    region: str | None
    # The usable connections, the default first.
    connections: list[GcpConnection]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderAccount:
    """A cloud provider account connected to an organization."""

    id: uuid.UUID
    # E.g. ``"gcp"``.
    provider: str
    name: str
    is_default: bool
    # The account's settings, e.g. ``project_id`` and ``region``. Never secrets.
    config: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class CloudRunManifest:
    """What deploying a Reflex app to Google Cloud Run yourself takes."""

    # The Dockerfile to build the app's image with.
    dockerfile: str
    # A bash script that builds and deploys the image, configured through
    # environment variables such as ``GCP_PROJECT``.
    deploy_command: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderChange:
    """The result of moving an app to another hosting provider."""

    provider: str
    # Whether the previous provider's resources were torn down; None when the
    # provider did not change.
    released: bool | None = None
    # The previous provider, while its teardown is unfinished.
    unreleased_provider: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FullDeployChange:
    """The result of changing where an app's frontend is served from."""

    full_deploy: bool
    # Whether the app was stopped to make the change.
    stopped: bool
    # Whether the stop was confirmed; the app may still be stopping otherwise.
    stop_confirmed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class InstanceBoundsChange:
    """The result of setting an app's instance bounds."""

    # ``"ok"``, or ``"unchanged"`` when the bounds were already set.
    status: str
    # Whether the running instances were restarted to apply the bounds.
    applied_now: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpBlockingApp:
    """An app that stops an organization's Google Cloud account from being removed."""

    app_id: uuid.UUID
    name: str
    project_name: str
    is_deleted: bool
    project_is_deleted: bool
    # Whether the app left Google Cloud, or was deleted, before its resources there
    # were confirmed deleted.
    release_unconfirmed: bool
    # Whether the app only waits for a deployment to settle, which happens on its own.
    awaiting_provisioning: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpCheck:
    """One check of a Google Cloud connection's access."""

    # E.g. ``"Cloud Run"`` or ``"deploy and teardown permissions"``.
    check: str
    # ``"passed"``, ``"failed"``, or ``"skipped"`` when Google did not answer.
    outcome: str
    # Why the check failed or was skipped; empty when it passed.
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpVerification:
    """Whether a Google Cloud connection's stored key can still deploy."""

    # Whether no check failed; checks may still have been skipped.
    ok: bool
    connection_name: str
    project_id: str
    # The service account the stored key belongs to; empty if the key is unreadable.
    client_email: str
    # What is wrong, as sentences.
    problems: list[str]
    checks: list[GcpCheck]


@dataclass(frozen=True, slots=True, kw_only=True)
class GcpKeyRotation:
    """The result of replacing a Google Cloud connection's service account key."""

    connection_name: str
    project_id: str
    # The service account the new key belongs to.
    client_email: str
    # The new key's id; empty if the key has none.
    new_key_id: str
    # The replaced key's id, to delete in Google Cloud: rotating does not revoke it.
    # None if the replaced key was unreadable or had no id.
    old_key_id: str | None
    old_client_email: str | None
    # The names of the checks that could not run.
    skipped_checks: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageBalance:
    """How much of an organization's plan allowance is used this period."""

    # Whether the organization has an allowance; both shares are ``"0"`` otherwise.
    has_allowance: bool
    # The share of the allowance used, as a percentage in a decimal string such as
    # ``"37.50"``. It exceeds 100 when the balance is negative.
    used_pct: str
    # The share of the allowance left, as a percentage in a decimal string. Top-ups
    # can take it past 100.
    remaining_pct: str
    # Whether the allowance refills on a rolling schedule rather than monthly.
    refresh_eligible: bool
    # When the allowance next refills, if known.
    next_refresh_at: datetime.datetime | None
    # The share of the allowance the refill brings the balance to, as a decimal
    # string.
    next_refresh_pct: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageEntry:
    """A charge or credit against an organization's plan allowance."""

    timestamp: datetime.datetime
    # The amount as a signed percentage of the allowance of its period, in an
    # unrounded decimal string: negative for charges, positive for credits. None
    # for movements before the organization's first allowance.
    amount_pct: str | None
    # E.g. ``"task_debit"`` for an AI builder generation, ``"compute_debit"`` for
    # hosting, ``"period_reset"`` for the allowance, or ``"topup"``.
    kind: str
    description: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityViolation:
    """A security or logic issue found by a security review."""

    rule_id: str
    # ``"security"`` or ``"logic"``.
    category: str
    file_path: str
    # The 1-based line the issue is on, if it is on one.
    line: int | None = None
    # ``"low"``, ``"medium"``, ``"high"`` or ``"critical"``.
    severity: str
    snippet: str
    message: str
    recommendation: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityReviewResult:
    """What a security review found."""

    summary: str
    violations: list[SecurityViolation] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityReviewJob:
    """A security review and, once it has finished, its result."""

    job_id: str
    # ``"pending"`` while queued or running, then ``"complete"`` or ``"error"``.
    status: str
    result: SecurityReviewResult | None = None
    # Why the review failed, when it did.
    error: str | None = None
