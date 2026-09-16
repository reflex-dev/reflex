from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_sdk import AsyncReflexCloud, PermissionDeniedError
from reflex_sdk.types import (
    Project,
    ProjectMember,
    ProjectRef,
    ProjectSummary,
    ProjectTier,
    Role,
)

from tests.units.reflex_sdk.conftest import AsyncMockTransport, MockAPI, reply

PROJECT_ID = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"
ROLE_ID = "3a9d7c1e-0b4f-4e2a-9c8d-1f2e3d4c5b6a"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
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
    assert json.loads(mock_api.requests[0].content or b"") == {"name": "staging"}


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
    assert json.loads(mock_api.requests[0].content or b"") == {
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
