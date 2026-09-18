# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/projects.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
"""The project, role and member endpoints."""

from __future__ import annotations

import builtins
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from reflex_sdk._base import path_segment
from reflex_sdk._errors import NotFoundError
from reflex_sdk.types import (
    AuditLogEntry,
    Project,
    ProjectMember,
    ProjectRef,
    ProjectSummary,
    Role,
    RoleUpdatePreview,
    TeamGrants,
)

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud


@dataclass(frozen=True, slots=True, kw_only=True)
class _EffectivePermissions:
    """The body of a member's effective permissions."""

    user_id: uuid.UUID
    permissions: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class _TeamGrantResult:
    """The body of granting a team a role."""

    status: str
    team_id: uuid.UUID
    role: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _TeamRevokeResult:
    """The body of revoking a team's role."""

    status: str
    team_id: uuid.UUID


def _role_body(name: str, base_tier: str, permissions: Sequence[str]) -> dict[str, Any]:
    """Build the body that defines a custom role.

    Args:
        name: The role name.
        base_tier: The built-in tier the role extends.
        permissions: The permissions the role adds to its base tier.

    Returns:
        The request body.
    """
    return {"name": name, "base_tier": base_tier, "permissions": list(permissions)}


class Roles:
    """Manage the roles that can be granted on a project.

    A custom role extends a built-in tier with permissions, which are named:

    ``can_view``, ``can_create_app``, ``can_create_thread``, ``can_delete``,
    ``can_rename``, ``can_deploy``, ``can_start_apps``, ``can_stop_apps``,
    ``can_delete_apps``, ``can_manage_domains``, ``can_edit_code``,
    ``can_push_to_repo``, ``can_change_visibility``, ``can_resize_sandbox``,
    ``can_view_secret_keys``, ``can_view_secret_values``, ``can_edit_secrets``,
    ``can_manage_integrations``, ``can_edit_integrations``,
    ``can_view_audit_logs``, ``can_approve_deploy``, ``can_approve_change`` and
    ``can_manage_approvals``.

    Managing members, managing roles and billing come with the admin tier and
    cannot be added to a role. ``can_view_secret_values`` and
    ``can_edit_secrets`` each add ``can_view_secret_keys`` as well, so a role
    lists it back. An unknown name is refused with ``BadRequestError`` naming it.

    Creating, changing and previewing custom roles needs the Enterprise plan.
    """

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def list(self, project_id: uuid.UUID | str) -> builtins.list[Role]:
        """List a project's roles.

        Args:
            project_id: The project.

        Returns:
            The roles, built-in roles first.
        """
        return self._client._request(
            "GET", f"project/{path_segment(project_id)}/roles", builtins.list[Role]
        )

    def permissions(
        self, project_id: uuid.UUID | str, role_id: uuid.UUID | str
    ) -> builtins.list[str]:
        """List the permissions a role grants, including those of its base tier.

        Args:
            project_id: The project.
            role_id: The role. An unknown role grants no permissions.

        Returns:
            The permission names, sorted.
        """
        permissions = self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/role/{path_segment(role_id)}",
            builtins.list[dict[str, Any]] | None,
        )
        return [permission["name"] for permission in permissions or ()]

    def create(
        self,
        project_id: uuid.UUID | str,
        name: str,
        *,
        base_tier: Literal["admin", "editor", "viewer"],
        permissions: Sequence[str] = (),
    ) -> Role:
        """Create a custom role.

        Args:
            project_id: The project.
            name: The role name, unique within the project and not the name of a
                base tier.
            base_tier: The built-in tier the role extends.
            permissions: The permissions the role adds to its base tier, from the
                names listed on this class, e.g. ``"can_view_audit_logs"``.

        Returns:
            The new role.
        """
        return self._client._request(
            "POST",
            f"project/{path_segment(project_id)}/roles",
            Role,
            json=_role_body(name, base_tier, permissions),
        )

    def update(
        self,
        project_id: uuid.UUID | str,
        role_id: uuid.UUID | str,
        *,
        name: str,
        base_tier: Literal["admin", "editor", "viewer"],
        permissions: Sequence[str],
    ) -> None:
        """Replace a custom role's definition, applying it to everyone holding it.

        Takes effect immediately, even on a project that requires approval to change
        a member's role; check the effect first with ``preview_update``. A role held
        by a team cannot become an admin role.

        Args:
            project_id: The project.
            role_id: The custom role.
            name: The role name.
            base_tier: The built-in tier the role extends.
            permissions: Every permission the role adds to its base tier, from the
                names listed on this class.
        """
        self._client._request(
            "PATCH",
            f"project/{path_segment(project_id)}/roles/{path_segment(role_id)}",
            None,
            json=_role_body(name, base_tier, permissions),
            idempotent=True,
        )

    def preview_update(
        self,
        project_id: uuid.UUID | str,
        role_id: uuid.UUID | str,
        *,
        name: str,
        base_tier: Literal["admin", "editor", "viewer"],
        permissions: Sequence[str],
    ) -> RoleUpdatePreview:
        """Show what ``update`` would change, without changing anything.

        Args:
            project_id: The project.
            role_id: The custom role.
            name: The role name.
            base_tier: The built-in tier the role would extend.
            permissions: Every permission the role would add to its base tier, from
                the names listed on this class.

        Returns:
            The permissions the role would gain and lose, and who holds it.
        """
        return self._client._request(
            "POST",
            f"project/{path_segment(project_id)}/roles/{path_segment(role_id)}/preview",
            RoleUpdatePreview,
            json=_role_body(name, base_tier, permissions),
            idempotent=True,
        )

    def delete(self, project_id: uuid.UUID | str, role_id: uuid.UUID | str) -> None:
        """Delete a custom role that no member or team holds.

        Args:
            project_id: The project.
            role_id: The custom role.
        """
        self._client._request(
            "DELETE",
            f"project/{path_segment(project_id)}/roles/{path_segment(role_id)}",
            None,
        )


class Members:
    """Manage who has access to a project."""

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def list(self, project_id: uuid.UUID | str) -> builtins.list[ProjectMember]:
        """List the members of a project.

        Args:
            project_id: The project.

        Returns:
            The members.
        """
        members = self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/users",
            builtins.list[ProjectMember] | None,
        )
        return members or []

    def set_role(
        self, *, user_id: uuid.UUID | str, role_id: uuid.UUID | str
    ) -> Literal["applied", "pending_approval"]:
        """Grant a user a role on the role's project, adding them as a member if needed.

        Args:
            user_id: The user, a member of the project's organization.
            role_id: The role to grant.

        Returns:
            ``"applied"``, or ``"pending_approval"`` when the project requires an
            admin to approve the change first.
        """
        result = self._client._request(
            "POST",
            "project/users/invite",
            dict[str, Any] | None,
            json={"user_id": str(user_id), "role_id": str(role_id)},
        )
        return (
            "pending_approval"
            if result is not None and result.get("status") == "pending_approval"
            else "applied"
        )

    def remove(self, project_id: uuid.UUID | str, user_id: uuid.UUID | str) -> None:
        """Remove a member from a project.

        On a project that requires approval to remove members, the removal waits
        for it, and the member keeps access until then; the response does not say
        which happened. Organization admins, members with access only through a
        team, and the last admin cannot be removed.

        Args:
            project_id: The project.
            user_id: The member.
        """
        self._client._request(
            "DELETE",
            f"project/{path_segment(project_id)}/user/{path_segment(user_id)}",
            None,
        )

    def permissions(
        self, project_id: uuid.UUID | str, user_id: uuid.UUID | str
    ) -> builtins.list[str]:
        """List the permissions a user has on a project, however they got them.

        Includes permissions from the user's role, their teams, and being an
        organization admin. Needs permission to manage the project's members.

        Args:
            project_id: The project.
            user_id: The user. A user without access has no permissions.

        Returns:
            The permission names, sorted.
        """
        result = self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/users/{path_segment(user_id)}/permissions",
            _EffectivePermissions,
        )
        return result.permissions


class Teams:
    """Give an organization's teams access to a project.

    A team holds at most one role on a project, and never an admin role. Team
    members get the role's access without being members themselves.
    """

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def list(self, project_id: uuid.UUID | str) -> TeamGrants:
        """List the teams with access to a project, and changes awaiting approval.

        Needs permission to manage the project's members.

        Args:
            project_id: The project.

        Returns:
            The teams' roles and the pending changes.
        """
        return self._client._request(
            "GET", f"project/{path_segment(project_id)}/teams", TeamGrants
        )

    def grant(
        self, project_id: uuid.UUID | str, team_id: uuid.UUID | str, role: str
    ) -> str:
        """Give a team a role on a project, replacing any role it holds.

        Giving a team more access needs the Enterprise plan.

        Args:
            project_id: The project.
            team_id: A team of the project's organization.
            role: The name of the role, matched exactly, e.g. ``"editor"``.

        Returns:
            ``"granted"``, or ``"pending_approval"`` when the project requires an
            admin to approve the change first.
        """
        result = self._client._request(
            "PUT",
            f"project/{path_segment(project_id)}/teams/{path_segment(team_id)}",
            _TeamGrantResult,
            json={"role": role},
        )
        return result.status

    def revoke(self, project_id: uuid.UUID | str, team_id: uuid.UUID | str) -> str:
        """Take away the role a team holds on a project.

        Args:
            project_id: The project.
            team_id: The team.

        Returns:
            ``"revoked"``, ``"not_granted"`` if the team held no role, or
            ``"pending_approval"`` when the project requires an admin to approve the
            change first.
        """
        # Revoking again reports the outcome without changing anything.
        result = self._client._request(
            "DELETE",
            f"project/{path_segment(project_id)}/teams/{path_segment(team_id)}",
            _TeamRevokeResult,
            idempotent=True,
        )
        return result.status


class Projects:
    """Manage projects and who has access to them."""

    # Manage the roles that can be granted on a project.
    roles: Roles
    # Manage who has access to a project.
    members: Members
    # Give an organization's teams access to a project.
    teams: Teams

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.roles = Roles(client)
        self.members = Members(client)
        self.teams = Teams(client)

    def list(self) -> builtins.list[ProjectSummary]:
        """List the projects the caller can access, with their usage.

        Returns:
            The projects.
        """
        projects = self._client._request(
            "GET", "project/", builtins.list[ProjectSummary] | None
        )
        return projects or []

    def search(self, name: str) -> builtins.list[ProjectRef]:
        """Find the projects the caller can access with a name.

        Args:
            name: The exact project name.

        Returns:
            The matching projects.
        """
        try:
            return self._client._request(
                "GET",
                "project/search",
                builtins.list[ProjectRef],
                params={"project_name": name},
            )
        except NotFoundError:
            # The API reports finding no match, and having no project to search, as
            # 404; either way no accessible project has the name. App search responds
            # with an empty list instead.
            return []

    def get(self, project_id: uuid.UUID | str) -> Project:
        """Get a project and its apps.

        Args:
            project_id: The project.

        Returns:
            The project.
        """
        return self._client._request(
            "GET", f"project/{path_segment(project_id)}", Project
        )

    def create(self, name: str) -> ProjectRef:
        """Create a project in the organization of the calling token.

        Args:
            name: The project name, unique within the organization.

        Returns:
            The new project.
        """
        return self._client._request(
            "POST", "project/create", ProjectRef, json={"name": name}
        )

    def rename(self, project_id: uuid.UUID | str, name: str) -> None:
        """Rename a project.

        Args:
            project_id: The project.
            name: The new name.
        """
        self._client._request(
            "POST",
            f"project/{path_segment(project_id)}/update_name",
            None,
            json={"name": name},
            idempotent=True,
        )

    def delete(self, project_id: uuid.UUID | str) -> None:
        """Delete a project and every app in it, which cannot be undone.

        The apps are stopped and deleted in the background.

        Args:
            project_id: The project.
        """
        self._client._request("DELETE", f"project/{path_segment(project_id)}", None)

    def audit_logs(
        self, project_id: uuid.UUID | str, *, limit: int = 100
    ) -> builtins.list[AuditLogEntry]:
        """List the latest events of a project, its apps and their deployments.

        Needs the Enterprise plan and permission to view the project's audit logs.

        Args:
            project_id: The project.
            limit: How many events to list, at most 200.

        Returns:
            The events, newest first.
        """
        return self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/audit-logs",
            builtins.list[AuditLogEntry],
            params={"limit": limit},
        )
