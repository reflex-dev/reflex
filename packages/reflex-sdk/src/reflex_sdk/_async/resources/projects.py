"""The project, role and member endpoints."""

from __future__ import annotations

import builtins
import uuid
from typing import TYPE_CHECKING, Literal

from reflex_sdk._base import path_segment
from reflex_sdk._errors import NotFoundError
from reflex_sdk.types import Project, ProjectMember, ProjectRef, ProjectSummary, Role

if TYPE_CHECKING:
    from reflex_sdk._async._client import AsyncReflexCloud


class AsyncRoles:
    """List the roles that can be granted on a project."""

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def list(self, project_id: uuid.UUID | str) -> builtins.list[Role]:
        """List a project's roles.

        Args:
            project_id: The project.

        Returns:
            The roles, built-in roles first.
        """
        return await self._client._request(
            "GET", f"project/{path_segment(project_id)}/roles", builtins.list[Role]
        )

    async def permissions(
        self, project_id: uuid.UUID | str, role_id: uuid.UUID | str
    ) -> builtins.list[str]:
        """List the permissions a role grants, including those of its base tier.

        Args:
            project_id: The project.
            role_id: The role. An unknown role grants no permissions.

        Returns:
            The permission names, sorted.
        """
        permissions = await self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/role/{path_segment(role_id)}",
            builtins.list[dict[str, str]] | None,
        )
        return [permission["name"] for permission in permissions or ()]


class AsyncMembers:
    """Manage who has access to a project."""

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def list(self, project_id: uuid.UUID | str) -> builtins.list[ProjectMember]:
        """List the members of a project.

        Args:
            project_id: The project.

        Returns:
            The members.
        """
        members = await self._client._request(
            "GET",
            f"project/{path_segment(project_id)}/users",
            builtins.list[ProjectMember] | None,
        )
        return members or []

    async def set_role(
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
        result = await self._client._request(
            "POST",
            "project/users/invite",
            dict[str, str] | None,
            json={"user_id": str(user_id), "role_id": str(role_id)},
        )
        return (
            "pending_approval"
            if result is not None and result.get("status") == "pending_approval"
            else "applied"
        )


class AsyncProjects:
    """Manage projects and who has access to them."""

    # List the roles that can be granted on a project.
    roles: AsyncRoles
    # Manage who has access to a project.
    members: AsyncMembers

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.roles = AsyncRoles(client)
        self.members = AsyncMembers(client)

    async def list(self) -> builtins.list[ProjectSummary]:
        """List the projects the caller can access, with their usage.

        Returns:
            The projects.
        """
        projects = await self._client._request(
            "GET", "project/", builtins.list[ProjectSummary] | None
        )
        return projects or []

    async def search(self, name: str) -> builtins.list[ProjectRef]:
        """Find the projects the caller can access with a name.

        Args:
            name: The exact project name.

        Returns:
            The matching projects.
        """
        try:
            return await self._client._request(
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

    async def get(self, project_id: uuid.UUID | str) -> Project:
        """Get a project and its apps.

        Args:
            project_id: The project.

        Returns:
            The project.
        """
        return await self._client._request(
            "GET", f"project/{path_segment(project_id)}", Project
        )

    async def create(self, name: str) -> ProjectRef:
        """Create a project in the organization of the calling token.

        Args:
            name: The project name, unique within the organization.

        Returns:
            The new project.
        """
        return await self._client._request(
            "POST", "project/create", ProjectRef, json={"name": name}
        )
