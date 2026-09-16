"""Models returned by the Reflex Cloud API."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field


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
    creation_time: datetime.datetime
    expiration: datetime.datetime
    org_name: str
    access: AccessScope | None = None
