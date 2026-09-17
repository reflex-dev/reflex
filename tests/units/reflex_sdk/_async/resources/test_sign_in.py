from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_sdk import AsyncReflexCloud
from reflex_sdk.types import (
    Audience,
    AudienceChange,
    EndUser,
    EndUserBlock,
    EndUserExport,
    EndUserPage,
    InviteRemoval,
    SignInInvite,
    SignInStatus,
)

from tests.units.reflex_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
AUTH_PATH = f"/api/v1/apps/{APP_ID}/auth"
ISSUER = "https://build.reflex.dev/oidc"
UTC = datetime.timezone.utc
NOON = datetime.datetime(2026, 9, 16, 12, tzinfo=UTC)


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


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (
            {
                "has_auth": True,
                "issuer": ISSUER,
                "client_id": APP_ID,
                "client_enabled": True,
            },
            SignInStatus(
                enabled=True, issuer=ISSUER, client_id=APP_ID, client_enabled=True
            ),
        ),
        (
            {"has_auth": False, "client_enabled": False},
            SignInStatus(enabled=False, client_enabled=False),
        ),
    ],
)
async def test_get(
    client: AsyncReflexCloud, mock_api: MockAPI, body: dict, status: SignInStatus
):
    mock_api.add("GET", AUTH_PATH, reply(200, json=body))
    assert await client.apps.sign_in.get(APP_ID) == status


async def test_enable_is_retried(client: AsyncReflexCloud, mock_api: MockAPI):
    # Enabling again converges on the same settings.
    mock_api.add(
        "POST",
        AUTH_PATH,
        reply(502, json={"detail": "secret store unavailable"}),
        reply(
            201,
            json={
                "has_auth": True,
                "issuer": ISSUER,
                "client_id": APP_ID,
                "created": True,
            },
        ),
    )
    assert await client.apps.sign_in.enable(APP_ID) == SignInStatus(
        enabled=True, issuer=ISSUER, client_id=APP_ID, client_enabled=True
    )
    assert len(mock_api.requests) == 2


async def test_disable(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", AUTH_PATH, reply(200, json={"deleted": True}))
    assert await client.apps.sign_in.disable(APP_ID) is True


async def test_list_users(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{AUTH_PATH}/users",
        reply(
            200,
            json={
                "users": [
                    {
                        "user_id": USER_ID,
                        "email": "",
                        "name": None,
                        "first_consented_at": "2026-09-16T12:00:00+00:00",
                        "last_active_at": None,
                        "consented_at": "2026-09-16T12:00:00+00:00",
                        "blocked_at": None,
                        "blocked": False,
                    }
                ],
                "total": 7,
                "limit": 1,
                "offset": 3,
                "search": "",
            },
        ),
    )
    page = await client.apps.sign_in.list_users(APP_ID, limit=1, offset=3)
    assert page == EndUserPage(
        users=[
            EndUser(
                user_id=uuid.UUID(USER_ID),
                email="",
                name=None,
                first_consented_at=NOON,
                consented_at=NOON,
                last_active_at=None,
                blocked=False,
                blocked_at=None,
            )
        ],
        total=7,
    )
    assert parse_qs(urlsplit(mock_api.requests[0].url).query) == {
        "limit": ["1"],
        "offset": ["3"],
    }


@pytest.mark.parametrize(
    ("filename", "truncated"),
    [("app-users.csv", False), ("app-users.partial.csv", True)],
)
async def test_export_users(
    client: AsyncReflexCloud, mock_api: MockAPI, filename: str, truncated: bool
):
    csv = "Email,Name,First consented,Last active,Consent last given,Blocked since,User ID\r\n"
    mock_api.add(
        "GET",
        f"{AUTH_PATH}/users/export",
        reply(
            200,
            text=csv,
            headers={
                "content-type": "text/csv; charset=utf-8",
                "content-disposition": f'attachment; filename="{filename}"',
            },
        ),
    )
    assert await client.apps.sign_in.export_users(APP_ID) == EndUserExport(
        csv=csv, truncated=truncated
    )


@pytest.mark.parametrize("action", ["block", "unblock"])
async def test_block_and_unblock(
    client: AsyncReflexCloud, mock_api: MockAPI, action: str
):
    # A failed session sweep still answers 200, with revoked_sessions null.
    body = {
        "user_id": USER_ID,
        "blocked": True,
        "blocked_at": "2026-09-16T12:00:00+00:00",
        "revoked_sessions": None,
    }
    mock_api.add("POST", f"{AUTH_PATH}/users/{USER_ID}/{action}", reply(200, json=body))
    method = getattr(client.apps.sign_in, f"{action}_user")
    assert await method(APP_ID, uuid.UUID(USER_ID)) == EndUserBlock(
        user_id=uuid.UUID(USER_ID),
        blocked=True,
        blocked_at=NOON,
        revoked_sessions=None,
    )


INVITE = {
    "email": "someone@example.com",
    "created_at": "2026-09-16T12:00:00+00:00",
    "redeemed_at": None,
    "redeemed": False,
}
SIGN_IN_INVITE = SignInInvite(
    email="someone@example.com", created_at=NOON, redeemed_at=None, redeemed=False
)


@pytest.mark.parametrize(
    ("body", "audience"),
    [
        (
            {"audience": "invited", "invites": [INVITE]},
            Audience(audience="invited", invites=[SIGN_IN_INVITE]),
        ),
        # Callers who cannot edit the app get no invites, and an unknown setting
        # reads as null.
        ({"audience": None}, Audience(audience=None)),
    ],
)
async def test_get_audience(
    client: AsyncReflexCloud, mock_api: MockAPI, body: dict, audience: Audience
):
    mock_api.add("GET", f"{AUTH_PATH}/audience", reply(200, json=body))
    assert await client.apps.sign_in.get_audience(APP_ID) == audience


async def test_set_audience(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{AUTH_PATH}/audience",
        reply(
            200, json={"audience": "members", "changed": True, "revoked_sessions": 12}
        ),
    )
    assert await client.apps.sign_in.set_audience(APP_ID, "members") == AudienceChange(
        audience="members", changed=True, revoked_sessions=12
    )
    assert json_body(mock_api.requests[0]) == {"audience": "members"}


async def test_invite(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", f"{AUTH_PATH}/invites", reply(201, json=INVITE))
    assert (
        await client.apps.sign_in.invite(APP_ID, "Someone@Example.com")
        == SIGN_IN_INVITE
    )
    assert json_body(mock_api.requests[0]) == {"email": "Someone@Example.com"}


async def test_uninvite(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        f"{AUTH_PATH}/invites",
        reply(200, json={"email": "a+b@example.com", "revoked_sessions": 0}),
    )
    assert await client.apps.sign_in.uninvite(
        APP_ID, "a+b@example.com"
    ) == InviteRemoval(email="a+b@example.com", revoked_sessions=0)
    # The address goes in the query, where "+" must be encoded.
    assert "email=a%2Bb%40example.com" in mock_api.requests[0].url
