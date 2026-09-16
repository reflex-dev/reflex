from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator

import pytest
from reflex_sdk import AsyncReflexCloud, AuthenticationError
from reflex_sdk.types import AccessScope, Me, Token

from tests.units.reflex_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"


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


async def test_me(client: AsyncReflexCloud, mock_api: MockAPI):
    # The shape returned by the control plane, including fields the SDK does not model.
    mock_api.add(
        "POST",
        "/api/v1/authenticate/me",
        reply(
            200,
            json={
                "user_id": USER_ID,
                "org_id": ORG_ID,
                "tier": "enterprise",
                "superuser": False,
                "email": "dev@example.com",
                "pilot": False,
                "access": {"permissions": {"apps": "read"}, "projects": "all"},
                "is_service_account": True,
                "impersonated_by": None,
                "impersonation_expires_at": None,
            },
        ),
    )
    assert await client.auth.me() == Me(
        user_id=uuid.UUID(USER_ID),
        org_id=uuid.UUID(ORG_ID),
        email="dev@example.com",
        tier="enterprise",
        is_service_account=True,
        access=AccessScope(permissions={"apps": "read"}, projects="all"),
    )
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"
    assert "?" not in request.url


async def test_me_invalid_token(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/authenticate/me",
        reply(401, json={"detail": "Token not found or is inactive"}),
    )
    with pytest.raises(AuthenticationError, match="Token not found or is inactive"):
        await client.auth.me()


async def test_create_token(client: AsyncReflexCloud, mock_api: MockAPI):
    token_id = str(uuid.uuid4())
    mock_api.add("POST", "/api/v1/user/token", reply(200, json=token_id))
    assert await client.auth.tokens.create("ci") == token_id
    assert json_body(mock_api.requests[0]) == {
        "name": "ci",
        "expiration": None,
    }


async def test_create_scoped_token(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/user/token", reply(200, json="token"))
    await client.auth.tokens.create(
        "deploy",
        expires_in_days=7,
        access=AccessScope(permissions={"apps": "write"}, projects=["p1"]),
    )
    assert json_body(mock_api.requests[0]) == {
        "name": "deploy",
        "expiration": 7,
        "access": {"permissions": {"apps": "write"}, "projects": ["p1"]},
    }


async def test_list_tokens(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/user/token",
        reply(
            200,
            json=[
                {
                    "name": "ci",
                    "expiration": "2026-10-16T10:00:00+00:00",
                    "creation_time": "2026-09-16T10:00:00+00:00",
                    "org_name": "Acme",
                    "access": None,
                }
            ],
        ),
    )
    utc = datetime.timezone.utc
    assert await client.auth.tokens.list() == [
        Token(
            name="ci",
            created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=utc),
            expires_at=datetime.datetime(2026, 10, 16, 10, tzinfo=utc),
            org_name="Acme",
        )
    ]


async def test_delete_token_quotes_name(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        "/api/v1/user/token/ci%2Fprod%20key",
        reply(200, json={"message": "success"}),
    )
    assert await client.auth.tokens.delete("ci/prod key") is None
