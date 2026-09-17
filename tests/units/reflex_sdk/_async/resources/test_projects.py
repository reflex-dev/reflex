from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_sdk import AsyncReflexCloud, PermissionDeniedError
from reflex_sdk.types import (
    AuditLogEntry,
    PendingTeamChange,
    Project,
    ProjectMember,
    ProjectRef,
    ProjectSummary,
    ProjectTier,
    Role,
    RolePreviewMember,
    RolePreviewTeam,
    RoleUpdatePreview,
    TeamGrant,
    TeamGrants,
)

from tests.units.reflex_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

PROJECT_ID = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"
ROLE_ID = "3a9d7c1e-0b4f-4e2a-9c8d-1f2e3d4c5b6a"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
TEAM_ID = "4d5e6f70-8192-4a3b-9c4d-5e6f708192a3"
PROJECT_PATH = f"/api/v1/project/{PROJECT_ID}"
TIER = {"name": "pro", "cpu_quota": 8.0, "ram_quota": 16.0, "deployment_quota": 10}


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexCloud(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


async def test_list(client: AsyncReflexCloud, mock_api: MockAPI):
    project = {
        "id": PROJECT_ID,
        "name": "default",
        "tier": TIER,
        "cpu_usage": 1.0,
        "memory_usage": 2.0,
        "deployment_count": 3,
        "app_count": 2,
    }
    mock_api.add("GET", "/api/v1/project/", reply(200, json=[project]))
    assert await client.projects.list() == [
        ProjectSummary(
            id=uuid.UUID(PROJECT_ID),
            name="default",
            tier=ProjectTier(
                name="pro", cpu_quota=8.0, ram_quota=16.0, deployment_quota=10
            ),
            app_count=2,
            deployment_count=3,
            cpu_usage=1.0,
            memory_usage=2.0,
        )
    ]


async def test_list_null(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", "/api/v1/project/", reply(200, json=None))
    assert await client.projects.list() == []


async def test_search(client: AsyncReflexCloud, mock_api: MockAPI):
    found = {
        "id": PROJECT_ID,
        "name": "default",
        "org_id": USER_ID,
        "created_by": USER_ID,
        "is_deleted": False,
        "created_at_timestamp": "2026-09-16T10:00:00Z",
    }
    mock_api.add("GET", "/api/v1/project/search", reply(200, json=[found]))
    assert await client.projects.search("default") == [
        ProjectRef(id=uuid.UUID(PROJECT_ID), name="default")
    ]
    assert parse_qs(urlsplit(mock_api.requests[0].url).query) == {
        "project_name": ["default"]
    }


async def test_search_without_results(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/project/search",
        reply(404, json={"detail": "no projects found with given name."}),
    )
    assert await client.projects.search("missing") == []


async def test_get(client: AsyncReflexCloud, mock_api: MockAPI):
    info = {
        "id": PROJECT_ID,
        "name": "default",
        "tier": TIER,
        "project_owner": USER_ID,
        "project_owner_email": "dev@example.com",
        "project_seats": 2,
        "total_cpu_usage": 1.0,
        "total_ram_usage": 2.0,
        "total_running_deployments": 1,
        "apps": [
            {
                "id": ROLE_ID,
                "name": "dashboard",
                "description": "",
                "build": False,
                "current_deployment": None,
                "latest_deployment": None,
            }
        ],
    }
    mock_api.add("GET", PROJECT_PATH, reply(200, json=info))
    project = await client.projects.get(PROJECT_ID)
    assert isinstance(project, Project)
    assert project.owner_id == uuid.UUID(USER_ID)
    assert project.owner_email == "dev@example.com"
    assert project.seats == 2
    assert [app.name for app in project.apps] == ["dashboard"]


async def test_create(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/project/create",
        reply(200, json={"id": PROJECT_ID, "name": "staging"}),
    )
    assert await client.projects.create("staging") == ProjectRef(
        id=uuid.UUID(PROJECT_ID), name="staging"
    )
    assert json_body(mock_api.requests[0]) == {"name": "staging"}


async def test_roles_list(client: AsyncReflexCloud, mock_api: MockAPI):
    role = {
        "id": ROLE_ID,
        "name": "Editor",
        "base_tier": "editor",
        "permissions": ["can_deploy"],
        "is_builtin": True,
        "member_count": 1,
    }
    mock_api.add("GET", f"{PROJECT_PATH}/roles", reply(200, json=[role]))
    assert await client.projects.roles.list(PROJECT_ID) == [
        Role(
            id=uuid.UUID(ROLE_ID),
            name="Editor",
            base_tier="editor",
            permissions=["can_deploy"],
            is_builtin=True,
            member_count=1,
        )
    ]


@pytest.mark.parametrize(
    ("body", "permissions"),
    [
        ([{"name": "can_deploy"}, {"name": "can_view"}], ["can_deploy", "can_view"]),
        ([{"name": "can_deploy", "granted_via": ["editor"]}], ["can_deploy"]),
        (None, []),
    ],
)
async def test_roles_permissions(
    client: AsyncReflexCloud,
    mock_api: MockAPI,
    body: list[dict[str, Any]] | None,
    permissions: list[str],
):
    mock_api.add("GET", f"{PROJECT_PATH}/role/{ROLE_ID}", reply(200, json=body))
    assert await client.projects.roles.permissions(PROJECT_ID, ROLE_ID) == permissions


async def test_members_list(client: AsyncReflexCloud, mock_api: MockAPI):
    member = {
        "user_id": USER_ID,
        "email": "dev@example.com",
        "role": "Editor",
        "base_tier": "editor",
        "role_permissions": ["can_deploy"],
        "permissions": ["can_deploy", "can_view"],
        "is_service_account": False,
    }
    mock_api.add("GET", f"{PROJECT_PATH}/users", reply(200, json=[member]))
    assert await client.projects.members.list(PROJECT_ID) == [
        ProjectMember(
            user_id=uuid.UUID(USER_ID),
            email="dev@example.com",
            role="Editor",
            base_tier="editor",
            permissions=["can_deploy", "can_view"],
            is_service_account=False,
        )
    ]


async def test_members_list_null(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", f"{PROJECT_PATH}/users", reply(200, json=None))
    assert await client.projects.members.list(PROJECT_ID) == []


@pytest.mark.parametrize(
    ("body", "result"),
    [
        (None, "applied"),
        ({"status": "pending_approval"}, "pending_approval"),
        ({"status": "pending_approval", "request_id": 7}, "pending_approval"),
    ],
)
async def test_members_set_role(
    client: AsyncReflexCloud,
    mock_api: MockAPI,
    body: dict[str, Any] | None,
    result: str,
):
    mock_api.add("POST", "/api/v1/project/users/invite", reply(200, json=body))
    assert (
        await client.projects.members.set_role(
            user_id=uuid.UUID(USER_ID), role_id=ROLE_ID
        )
        == result
    )
    assert json_body(mock_api.requests[0]) == {
        "user_id": USER_ID,
        "role_id": ROLE_ID,
    }


async def test_members_set_role_denied(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/project/users/invite",
        reply(403, json={"detail": "custom project roles are not available"}),
    )
    with pytest.raises(PermissionDeniedError):
        await client.projects.members.set_role(user_id=USER_ID, role_id=ROLE_ID)


async def test_rename(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", f"{PROJECT_PATH}/update_name", reply(200, json=None))
    await client.projects.rename(PROJECT_ID, "staging")
    assert json_body(mock_api.requests[0]) == {"name": "staging"}


async def test_delete(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", PROJECT_PATH, reply(200, json=None))
    assert await client.projects.delete(PROJECT_ID) is None


async def test_audit_logs(client: AsyncReflexCloud, mock_api: MockAPI):
    entry = {
        "id": ROLE_ID,
        "timestamp": "2026-09-16T12:00:00Z",
        "action": "ADD_USER",
        "action_label": "Add User",
        "summary": "dev@example.com added a member",
        "resource_id": PROJECT_ID,
        "resource_type": "project",
        "resource_display": "default",
        "actor_user_id": USER_ID,
        "actor_display": "dev@example.com",
        "actor_email": "dev@example.com",
        "actor_is_service_account": False,
        "content": f"{USER_ID}|editor",
        "target_user_id": USER_ID,
        "target_display": "dev@example.com",
        "target_is_service_account": False,
    }
    mock_api.add("GET", f"{PROJECT_PATH}/audit-logs", reply(200, json=[entry]))
    (log,) = await client.projects.audit_logs(PROJECT_ID, limit=1)
    assert log == AuditLogEntry(
        id=uuid.UUID(ROLE_ID),
        timestamp=datetime.datetime(2026, 9, 16, 12, tzinfo=datetime.timezone.utc),
        action="ADD_USER",
        action_label="Add User",
        summary="dev@example.com added a member",
        resource_id=uuid.UUID(PROJECT_ID),
        resource_type="project",
        resource_display="default",
        actor_user_id=uuid.UUID(USER_ID),
        actor_display="dev@example.com",
        actor_email="dev@example.com",
        actor_is_service_account=False,
        content=f"{USER_ID}|editor",
        target_user_id=uuid.UUID(USER_ID),
        target_display="dev@example.com",
        target_is_service_account=False,
    )
    assert parse_qs(urlsplit(mock_api.requests[0].url).query) == {"limit": ["1"]}


ROLE_BODY = {
    "name": "Auditor",
    "base_tier": "viewer",
    "permissions": ["can_view_audit_logs"],
}


async def test_roles_create(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{PROJECT_PATH}/roles",
        reply(
            200,
            json={**ROLE_BODY, "id": ROLE_ID, "is_builtin": False, "member_count": 0},
        ),
    )
    role = await client.projects.roles.create(
        PROJECT_ID, "Auditor", base_tier="viewer", permissions=["can_view_audit_logs"]
    )
    assert role == Role(
        id=uuid.UUID(ROLE_ID),
        name="Auditor",
        base_tier="viewer",
        permissions=["can_view_audit_logs"],
        is_builtin=False,
        member_count=0,
    )
    assert json_body(mock_api.requests[0]) == ROLE_BODY


async def test_roles_update(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("PATCH", f"{PROJECT_PATH}/roles/{ROLE_ID}", reply(200, json=None))
    await client.projects.roles.update(
        PROJECT_ID,
        ROLE_ID,
        name="Auditor",
        base_tier="viewer",
        permissions=("can_view_audit_logs",),
    )
    assert json_body(mock_api.requests[0]) == ROLE_BODY


async def test_roles_preview_update(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{PROJECT_PATH}/roles/{ROLE_ID}/preview",
        reply(
            200,
            json={
                "gained": ["can_view_audit_logs"],
                "lost": [],
                "members": [
                    {
                        "user_id": USER_ID,
                        "email": "dev@example.com",
                        "is_service_account": False,
                    }
                ],
                "teams": [
                    {"team_id": TEAM_ID, "team_name": "Security", "member_count": 4}
                ],
            },
        ),
    )
    assert await client.projects.roles.preview_update(
        PROJECT_ID, ROLE_ID, **ROLE_BODY
    ) == RoleUpdatePreview(
        gained=["can_view_audit_logs"],
        lost=[],
        members=[
            RolePreviewMember(
                user_id=uuid.UUID(USER_ID),
                email="dev@example.com",
                is_service_account=False,
            )
        ],
        teams=[
            RolePreviewTeam(
                team_id=uuid.UUID(TEAM_ID), team_name="Security", member_count=4
            )
        ],
    )
    assert json_body(mock_api.requests[0]) == ROLE_BODY


async def test_roles_delete(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", f"{PROJECT_PATH}/roles/{ROLE_ID}", reply(200, json=None))
    assert await client.projects.roles.delete(PROJECT_ID, ROLE_ID) is None


async def test_members_remove(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", f"{PROJECT_PATH}/user/{USER_ID}", reply(200, json=None))
    assert await client.projects.members.remove(PROJECT_ID, USER_ID) is None


async def test_members_permissions(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROJECT_PATH}/users/{USER_ID}/permissions",
        reply(
            200, json={"user_id": USER_ID, "permissions": ["can_deploy", "can_view"]}
        ),
    )
    assert await client.projects.members.permissions(PROJECT_ID, USER_ID) == [
        "can_deploy",
        "can_view",
    ]


async def test_teams_list(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROJECT_PATH}/teams",
        reply(
            200,
            json={
                "grants": [
                    {
                        "team_id": TEAM_ID,
                        "team_name": "Security",
                        "role": "Auditor",
                        "base_tier": "viewer",
                        "permissions": ["can_view_audit_logs"],
                        "member_count": 4,
                    }
                ],
                "pending": [
                    {
                        "team_id": TEAM_ID,
                        "team_name": "",
                        "action": "revoke",
                        "role": None,
                    }
                ],
            },
        ),
    )
    assert await client.projects.teams.list(PROJECT_ID) == TeamGrants(
        grants=[
            TeamGrant(
                team_id=uuid.UUID(TEAM_ID),
                team_name="Security",
                role="Auditor",
                base_tier="viewer",
                permissions=["can_view_audit_logs"],
                member_count=4,
            )
        ],
        pending=[
            PendingTeamChange(
                team_id=uuid.UUID(TEAM_ID), team_name="", action="revoke", role=None
            )
        ],
    )


@pytest.mark.parametrize("status", ["granted", "pending_approval"])
async def test_teams_grant(client: AsyncReflexCloud, mock_api: MockAPI, status: str):
    mock_api.add(
        "PUT",
        f"{PROJECT_PATH}/teams/{TEAM_ID}",
        reply(200, json={"status": status, "team_id": TEAM_ID, "role": "editor"}),
    )
    assert await client.projects.teams.grant(PROJECT_ID, TEAM_ID, "editor") == status
    assert json_body(mock_api.requests[0]) == {"role": "editor"}


async def test_teams_revoke_is_retried(client: AsyncReflexCloud, mock_api: MockAPI):
    # Revoking again reports the outcome without changing anything.
    mock_api.add(
        "DELETE",
        f"{PROJECT_PATH}/teams/{TEAM_ID}",
        reply(503),
        reply(200, json={"status": "not_granted", "team_id": TEAM_ID}),
    )
    assert await client.projects.teams.revoke(PROJECT_ID, TEAM_ID) == "not_granted"
    assert len(mock_api.requests) == 2
