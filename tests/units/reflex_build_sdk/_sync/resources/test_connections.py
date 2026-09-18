# Generated from tests/units/reflex_build_sdk/_async/resources/test_connections.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest
from reflex_build_sdk import ConflictError, InternalServerError, ReflexBuild
from reflex_build_sdk.types import (
    ConnectionProvider,
    ConnectionStatus,
    ConnectLink,
    Credential,
)

from tests.units.reflex_build_sdk.conftest import (
    MockAPI,
    MockTransport,
    json_body,
    reply,
)

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
CONNECTIONS_PATH = f"/api/v1/apps/{APP_ID}/connections"
PROVIDER_PATH = f"{CONNECTIONS_PATH}/openai"
END_USER = "auth0|visitor-7"
UTC = datetime.timezone.utc
NOON = datetime.datetime(2026, 9, 17, 12, tzinfo=UTC)


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexBuild(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


def test_providers(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/connections/providers",
        reply(
            200,
            json=[
                {
                    "id": "openai",
                    "display_name": "OpenAI",
                    "broker": "nango",
                    "logo_url": None,
                }
            ],
        ),
    )
    assert client.apps.connections.providers() == [
        ConnectionProvider(
            id="openai", display_name="OpenAI", broker="nango", logo_url=None
        )
    ]


def test_list(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        CONNECTIONS_PATH,
        reply(
            200,
            json=[
                {
                    "provider": "openai",
                    "connected": True,
                    "broker": "nango",
                    "connected_at": "2026-09-17T12:00:00+00:00",
                }
            ],
        ),
    )
    assert client.apps.connections.list(APP_ID) == [
        ConnectionStatus(
            provider="openai", connected=True, broker="nango", connected_at=NOON
        )
    ]


def test_status_reads_the_apps_own_connection(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROVIDER_PATH}/status",
        reply(200, json={"provider": "openai", "connected": False}),
    )
    assert client.apps.connections.status(APP_ID, "openai") == ConnectionStatus(
        provider="openai", connected=False
    )
    # Absent, not empty: the API reads a missing header as the app's own connection.
    assert "X-End-User" not in mock_api.requests[0].headers


def test_status_names_a_user(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROVIDER_PATH}/status",
        reply(200, json={"provider": "openai", "connected": True}),
    )
    client.apps.connections.status(APP_ID, "openai", end_user=END_USER)
    assert mock_api.requests[0].headers["X-End-User"] == END_USER


@pytest.mark.parametrize(
    ("body", "credential"),
    [
        (
            {
                "access_token": "sk-live",
                "kind": "oauth2",
                "expires_at": "2026-09-17T12:00:00+00:00",
                "username": None,
            },
            Credential(access_token="sk-live", kind="oauth2", expires_at=NOON),
        ),
        (
            {"access_token": "hunter2", "kind": "basic", "username": "svc"},
            Credential(access_token="hunter2", kind="basic", username="svc"),
        ),
        # The API defaults the kind for a connection that predates it.
        ({"access_token": "sk-live"}, Credential(access_token="sk-live")),
    ],
)
def test_credential(
    client: ReflexBuild, mock_api: MockAPI, body: dict, credential: Credential
):
    mock_api.add("GET", f"{PROVIDER_PATH}/credential", reply(200, json=body))
    assert client.apps.connections.credential(APP_ID, "openai") == credential
    assert "X-End-User" not in mock_api.requests[0].headers


def test_credential_for_a_user(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROVIDER_PATH}/credential",
        reply(200, json={"access_token": "sk-live"}),
    )
    client.apps.connections.credential(APP_ID, "openai", end_user=END_USER)
    assert mock_api.requests[0].headers["X-End-User"] == END_USER


def test_credential_keeps_the_token_out_of_its_repr(
    client: ReflexBuild, mock_api: MockAPI
):
    mock_api.add(
        "GET",
        f"{PROVIDER_PATH}/credential",
        reply(200, json={"access_token": "sk-live"}),
    )
    credential = client.apps.connections.credential(APP_ID, "openai")
    assert credential.access_token == "sk-live"
    assert "sk-live" not in repr(credential)


def test_credential_refusal_names_its_condition(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{PROVIDER_PATH}/credential",
        reply(
            409,
            json={"detail": "not_connected"},
            headers={"x-reflex-error-code": "not_connected"},
        ),
    )
    with pytest.raises(ConflictError) as exc_info:
        client.apps.connections.credential(APP_ID, "openai")
    assert exc_info.value.code == "not_connected"


def test_connect_link_for_the_app(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{PROVIDER_PATH}/authorize",
        reply(
            200,
            json={
                "url": "https://connect.example.com/abc",
                "expires_at": "2026-09-17T12:00:00+00:00",
            },
        ),
    )
    assert client.apps.connections.connect_link(
        APP_ID, "openai", return_to="https://dashboard.reflex.run/done"
    ) == ConnectLink(url="https://connect.example.com/abc", expires_at=NOON)
    (request,) = mock_api.requests
    assert json_body(request) == {"return_to": "https://dashboard.reflex.run/done"}
    assert "X-End-User" not in request.headers


def test_connect_link_for_a_user(client: ReflexBuild, mock_api: MockAPI):
    # A user connects through a different route than the app itself.
    mock_api.add(
        "POST",
        f"{PROVIDER_PATH}/session",
        reply(200, json={"url": "https://connect.example.com/xyz"}),
    )
    link = client.apps.connections.connect_link(APP_ID, "openai", end_user=END_USER)
    assert link == ConnectLink(url="https://connect.example.com/xyz")
    (request,) = mock_api.requests
    assert json_body(request) == {"return_to": None}
    assert request.headers["X-End-User"] == END_USER


def test_disconnect_the_app(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add("DELETE", PROVIDER_PATH, reply(200, json={"disconnected": True}))
    assert client.apps.connections.disconnect(APP_ID, "openai") is None
    assert "X-End-User" not in mock_api.requests[0].headers


def test_disconnect_a_user(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST", f"{PROVIDER_PATH}/disconnect", reply(200, json={"disconnected": True})
    )
    client.apps.connections.disconnect(APP_ID, "openai", end_user=END_USER)
    assert mock_api.requests[0].headers["X-End-User"] == END_USER


def test_mutations_are_not_retried(client: ReflexBuild, mock_api: MockAPI):
    # A retried session mints a second link, so an ambiguous failure is raised.
    mock_api.add("POST", f"{PROVIDER_PATH}/session", reply(503))
    with pytest.raises(InternalServerError):
        client.apps.connections.connect_link(APP_ID, "openai", end_user=END_USER)
    assert len(mock_api.requests) == 1
