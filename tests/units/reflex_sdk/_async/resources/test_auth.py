from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator

import pytest
from reflex_sdk import (
    AsyncReflexCloud,
    AuthenticationError,
    LoginDeniedError,
    LoginTimeoutError,
)
from reflex_sdk.types import AccessScope, LoginRequest, Me, Token, TokenAccess

from tests.units.reflex_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"
PROJECT_ID = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"


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


# The shape the control plane returns: its AuthZ dataclass through FastAPI's encoder,
# including fields the SDK does not model.
ME = {
    "user_id": USER_ID,
    "org_id": ORG_ID,
    "tier": "Enterprise",
    "superuser": False,
    "email": "dev@example.com",
    "pilot": False,
    "access": None,
    "is_service_account": False,
    "impersonated_by": None,
    "impersonation_expires_at": None,
    "_memo": {},
    "_project_of": {},
    "_org_projects": None,
    "_org_projects_consistency": None,
    "_impersonation_org_of": {},
}


async def test_me(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=ME))
    assert await client.auth.me() == Me(
        user_id=uuid.UUID(USER_ID),
        org_id=uuid.UUID(ORG_ID),
        email="dev@example.com",
        tier="Enterprise",
    )
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"
    assert "?" not in request.url


async def test_me_records_the_login_source(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=ME))
    await client.auth.me(source="reflex")
    assert mock_api.requests[0].url.endswith("/authenticate/me?source=reflex")


async def test_me_scoped_token(client: AsyncReflexCloud, mock_api: MockAPI):
    # Every token `reflex login` mints carries an access map.
    body = {
        **ME,
        "is_service_account": True,
        "access": {
            "permissions": {"app": "write", "project": "read"},
            "all_projects": False,
            "project_ids": [PROJECT_ID],
        },
    }
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=body))
    me = await client.auth.me()
    assert me.is_service_account
    assert me.access == TokenAccess(
        permissions={"app": "write", "project": "read"},
        all_projects=False,
        project_ids=[uuid.UUID(PROJECT_ID)],
    )


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


@pytest.mark.parametrize(
    ("ui_url", "env", "base"),
    [
        (None, None, "https://build.reflex.dev"),
        (None, "https://cloud.example.com/", "https://cloud.example.com"),
        (
            "https://ui.example.com",
            "https://cloud.example.com",
            "https://ui.example.com",
        ),
    ],
)
def test_begin_login(
    mock_api: MockAPI,
    monkeypatch: pytest.MonkeyPatch,
    ui_url: str | None,
    env: str | None,
    base: str,
):
    if env is not None:
        monkeypatch.setenv("REFLEX_CLOUD_URL", env)
    # Starting a login sends nothing, so it needs no event loop or token.
    client = AsyncReflexCloud(transport=AsyncMockTransport(mock_api))
    login = client.auth.begin_login(ui_url=ui_url)
    assert len(login.request_id) == 32
    assert login.url == f"{base}/cli/login?request_id={login.request_id}"
    assert client.auth.begin_login().request_id != login.request_id
    assert not mock_api.requests


LOGIN = LoginRequest(request_id="abc123", url="https://build.reflex.dev/cli/login")


async def test_finish_login_waits_for_approval(mock_api: MockAPI):
    token = str(uuid.uuid4())
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(404, json={"detail": "Token not found or not yet approved"}),
        reply(404, json={"detail": "Token not found or not yet approved"}),
        reply(200, json={"token_id": token}),
    )
    # No token is needed to log in.
    async with AsyncReflexCloud(transport=AsyncMockTransport(mock_api)) as client:
        assert await client.auth.finish_login(LOGIN, poll_interval=0) == token
    assert len(mock_api.requests) == 3
    for request in mock_api.requests:
        assert request.url.endswith("/cli/token?request_id=abc123")
        assert "X-API-TOKEN" not in request.headers


async def test_finish_login_denied(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(403, json={"detail": "Authorization request was denied"}),
    )
    with pytest.raises(LoginDeniedError):
        await client.auth.finish_login(LOGIN, poll_interval=0)


async def test_finish_login_timeout(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(404, json={"detail": "Token not found or not yet approved"}),
    )
    with pytest.raises(LoginTimeoutError):
        await client.auth.finish_login(LOGIN, timeout=0.05, poll_interval=60)
