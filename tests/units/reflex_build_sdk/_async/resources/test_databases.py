from __future__ import annotations

import datetime
from collections.abc import AsyncIterator

import pytest
from reflex_build_sdk import APIResponseValidationError, AsyncReflexBuild
from reflex_build_sdk.types import ManagedDatabase

from tests.units.reflex_build_sdk.conftest import AsyncMockTransport, MockAPI, reply

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
DATABASE_PATH = f"/api/v1/apps/{APP_ID}/database"

DATABASE = {
    "has_database": True,
    "project_id": "wispy-cloud-12345678",
    "region": "aws-us-east-2",
    "created_at": "2026-09-16T10:00:00Z",
    "database": "neondb",
    "role": "neondb_owner",
    "masked_connection_string": "postgresql://****@ep-x-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require",
}

MANAGED_DATABASE = ManagedDatabase(
    provider_project_id="wispy-cloud-12345678",
    region="aws-us-east-2",
    created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=datetime.timezone.utc),
    database="neondb",
    role="neondb_owner",
    masked_connection_string="postgresql://****@ep-x-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require",
)


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexBuild(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


async def test_get(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", DATABASE_PATH, reply(200, json=DATABASE))
    assert await client.apps.database.get(APP_ID) == MANAGED_DATABASE


async def test_get_without_a_database(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", DATABASE_PATH, reply(200, json={"has_database": False}))
    assert await client.apps.database.get(APP_ID) is None


async def test_get_rejects_an_incomplete_database(
    client: AsyncReflexBuild, mock_api: MockAPI
):
    mock_api.add("GET", DATABASE_PATH, reply(200, json={"has_database": True}))
    with pytest.raises(APIResponseValidationError):
        await client.apps.database.get(APP_ID)


async def test_create_is_retried(client: AsyncReflexBuild, mock_api: MockAPI):
    # Creating again converges on the database the first attempt made.
    mock_api.add(
        "POST",
        DATABASE_PATH,
        reply(502, json={"detail": "Neon API error 500"}),
        reply(201, json={**DATABASE, "created": False}),
    )
    assert await client.apps.database.create(APP_ID) == MANAGED_DATABASE
    first, retry = mock_api.requests
    assert first.headers["X-Request-ID"] == retry.headers["X-Request-ID"]


@pytest.mark.parametrize("deleted", [True, False])
async def test_delete(client: AsyncReflexBuild, mock_api: MockAPI, deleted: bool):
    mock_api.add("DELETE", DATABASE_PATH, reply(200, json={"deleted": deleted}))
    assert await client.apps.database.delete(APP_ID) is deleted
