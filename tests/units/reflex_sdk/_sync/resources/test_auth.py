# Generated from tests/units/reflex_sdk/_async/resources/test_auth.py by scripts/unasync_reflex_sdk.py. Do not edit.
from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import Iterator

import pytest
from reflex_sdk import AuthenticationError, ReflexCloud
from reflex_sdk.types import AccessScope, Me, Token

from tests.units.reflex_sdk.conftest import MockAPI, MockTransport, reply

USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexCloud(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


def test_me(client: ReflexCloud, mock_api: MockAPI):
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
    assert client.auth.me() == Me(
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


def test_me_invalid_token(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/authenticate/me",
        reply(401, json={"detail": "Token not found or is inactive"}),
    )
    with pytest.raises(AuthenticationError, match="Token not found or is inactive"):
        client.auth.me()


def test_create_token(client: ReflexCloud, mock_api: MockAPI):
    token_id = str(uuid.uuid4())
    mock_api.add("POST", "/api/v1/user/token", reply(200, json=token_id))
    assert client.auth.tokens.create("ci") == token_id
    assert json.loads(mock_api.requests[0].content or b"") == {
        "name": "ci",
        "expiration": None,
    }


def test_create_scoped_token(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/user/token", reply(200, json="token"))
    client.auth.tokens.create(
        "deploy",
        expires_in_days=7,
        access=AccessScope(permissions={"apps": "write"}, projects=["p1"]),
    )
    assert json.loads(mock_api.requests[0].content or b"") == {
        "name": "deploy",
        "expiration": 7,
        "access": {"permissions": {"apps": "write"}, "projects": ["p1"]},
    }


def test_list_tokens(client: ReflexCloud, mock_api: MockAPI):
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
    assert client.auth.tokens.list() == [
        Token(
            name="ci",
            created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=utc),
            expires_at=datetime.datetime(2026, 10, 16, 10, tzinfo=utc),
            org_name="Acme",
        )
    ]


def test_delete_token_quotes_name(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        "/api/v1/user/token/ci%2Fprod%20key",
        reply(200, json={"message": "success"}),
    )
    assert client.auth.tokens.delete("ci/prod key") is None
