# Generated from tests/units/reflex_build_sdk/_async/resources/test_auth.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import datetime
import inspect
import uuid
from collections.abc import Iterator

import pytest
from reflex_build_sdk import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    LoginDeniedError,
    LoginTimeoutError,
    ReflexBuild,
)
from reflex_build_sdk.transports import Request, Response, TransportError
from reflex_build_sdk.types import (
    AccessScope,
    CreatedToken,
    LoginRequest,
    Me,
    RotatedToken,
    Token,
    TokenAccess,
)

from tests.units.reflex_build_sdk.conftest import (
    Handler,
    MockAPI,
    MockTransport,
    json_body,
    reply,
)

USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"
PROJECT_ID = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"


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
    "app_id": None,
    "_memo": {},
    "_project_of": {},
    "_org_projects": None,
    "_org_projects_consistency": None,
    "_impersonation_org_of": {},
}


def test_me(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=ME))
    assert client.auth.me() == Me(
        user_id=uuid.UUID(USER_ID),
        org_id=uuid.UUID(ORG_ID),
        email="dev@example.com",
        tier="Enterprise",
    )
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"
    assert "?" not in request.url


def test_me_records_the_login_source(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=ME))
    client.auth.me(source="reflex")
    assert mock_api.requests[0].url.endswith("/authenticate/me?source=reflex")


def test_me_scoped_token(client: ReflexBuild, mock_api: MockAPI):
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
    me = client.auth.me()
    assert me.is_service_account
    assert me.access == TokenAccess(
        permissions={"app": "write", "project": "read"},
        all_projects=False,
        project_ids=[uuid.UUID(PROJECT_ID)],
    )


def test_me_app_token(client: ReflexBuild, mock_api: MockAPI):
    # An app token grants nothing: its access map is empty.
    app_id = str(uuid.uuid4())
    body = {
        **ME,
        "access": {"permissions": {}, "all_projects": True, "project_ids": []},
        "app_id": app_id,
    }
    mock_api.add("POST", "/api/v1/authenticate/me", reply(200, json=body))
    me = client.auth.me()
    assert me.app_id == uuid.UUID(app_id)
    assert me.access == TokenAccess(permissions={})


def test_me_invalid_token(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/authenticate/me",
        reply(401, json={"detail": "Token not found or is inactive"}),
    )
    with pytest.raises(AuthenticationError, match="Token not found or is inactive"):
        client.auth.me()


def test_create_token(client: ReflexBuild, mock_api: MockAPI):
    token_id = str(uuid.uuid4())
    mock_api.add(
        "POST",
        "/api/v1/user/token/create",
        reply(
            200,
            json={
                "token": token_id,
                "name": "ci",
                "expiration": "2026-10-16T10:00:00+00:00",
            },
        ),
    )
    assert client.auth.tokens.create("ci") == CreatedToken(
        token=token_id,
        name="ci",
        expires_at=datetime.datetime(2026, 10, 16, 10, tzinfo=datetime.timezone.utc),
    )
    assert json_body(mock_api.requests[0]) == {
        "name": "ci",
        "expiration": None,
    }


def test_create_scoped_token(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/user/token/create",
        reply(200, json={"token": "token", "name": "deploy", "expiration": None}),
    )
    client.auth.tokens.create(
        "deploy",
        expires_in_days=7,
        access=AccessScope(permissions={"apps": "write"}, projects=["p1"]),
    )
    assert json_body(mock_api.requests[0]) == {
        "name": "deploy",
        "expiration": 7,
        "access": {"permissions": {"apps": "write"}, "projects": ["p1"]},
    }


def test_list_tokens(client: ReflexBuild, mock_api: MockAPI):
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


def test_delete_token_quotes_name(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        "/api/v1/user/token/ci%2Fprod%20key",
        reply(200, json={"message": "success"}),
    )
    assert client.auth.tokens.delete("ci/prod key") is None


def test_revoke_token(client: ReflexBuild, mock_api: MockAPI):
    token = str(uuid.uuid4())
    mock_api.add(
        "POST", "/api/v1/user/token/revoke", reply(200, json={"message": "success"})
    )
    assert client.auth.tokens.revoke(token) is None
    # The token goes in the body, where access logs don't record it.
    assert json_body(mock_api.requests[0]) == {"token_id": token}


def test_revoke_self(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add("POST", "/api/v1/user/token/revoke-self", reply(204))
    assert client.auth.tokens.revoke_self() is None
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"
    assert request.content is None


@pytest.mark.parametrize("previous_revoked", [True, False])
def test_refresh_token(client: ReflexBuild, mock_api: MockAPI, previous_revoked: bool):
    old, new = str(uuid.uuid4()), str(uuid.uuid4())
    mock_api.add(
        "POST",
        "/api/v1/user/token/rotate",
        reply(
            200,
            json={
                "token": new,
                "name": "ci",
                "expiration": None,
                "previous_revoked": previous_revoked,
            },
        ),
    )
    assert client.auth.tokens.refresh(old) == RotatedToken(
        token=new, name="ci", expires_at=None, previous_revoked=previous_revoked
    )
    assert json_body(mock_api.requests[0]) == {"token_id": old}


def _lose_response(request: Request) -> Response:
    msg = "connection reset after the request was processed"
    raise TransportError(msg, request=request, sent=True)


# Failures after which the server may have processed the request.
AMBIGUOUS_FAILURES = pytest.mark.parametrize(
    ("handler", "error"),
    [(reply(503), APIStatusError), (_lose_response, APIConnectionError)],
    ids=["unavailable", "lost_response"],
)


@AMBIGUOUS_FAILURES
def test_create_token_is_not_retried(
    client: ReflexBuild,
    mock_api: MockAPI,
    handler: Handler,
    error: type[Exception],
):
    # A retry would create another token with the same name.
    mock_api.add("POST", "/api/v1/user/token/create", handler)
    with pytest.raises(error):
        client.auth.tokens.create("ci")
    assert len(mock_api.requests) == 1


@AMBIGUOUS_FAILURES
def test_refresh_token_is_not_retried(
    client: ReflexBuild,
    mock_api: MockAPI,
    handler: Handler,
    error: type[Exception],
):
    # A retry would mint another token and revoke the one just issued.
    mock_api.add("POST", "/api/v1/user/token/rotate", handler)
    with pytest.raises(error):
        client.auth.tokens.refresh(str(uuid.uuid4()))
    assert len(mock_api.requests) == 1


def test_assign_token_to_service_account(client: ReflexBuild, mock_api: MockAPI):
    account_id = str(uuid.uuid4())
    mock_api.add(
        "POST",
        "/api/v1/user/token/ci/service-account",
        reply(200, json={"message": "success", "service_account_name": "deployer"}),
    )
    assert (
        client.auth.tokens.assign_to_service_account("ci", uuid.UUID(account_id))
        == "deployer"
    )
    assert json_body(mock_api.requests[0]) == {"service_account_id": account_id}


@pytest.mark.parametrize(
    ("ui_url", "env", "base"),
    [
        (None, {}, "https://build.reflex.dev"),
        (
            None,
            {"REFLEX_CLOUD_URL": "https://cloud.example.com/"},
            "https://cloud.example.com",
        ),
        (
            None,
            {"REFLEX_BUILD_URL": "https://ui.example.com/"},
            "https://ui.example.com",
        ),
        (
            None,
            {
                "REFLEX_BUILD_URL": "https://ui.example.com",
                "REFLEX_CLOUD_URL": "https://cloud.example.com",
            },
            "https://ui.example.com",
        ),
        (
            "https://explicit.example.com",
            {"REFLEX_BUILD_URL": "https://ui.example.com"},
            "https://explicit.example.com",
        ),
    ],
)
def test_begin_login(
    mock_api: MockAPI,
    monkeypatch: pytest.MonkeyPatch,
    ui_url: str | None,
    env: dict[str, str],
    base: str,
):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    # Starting a login sends nothing, so it needs no event loop or token.
    client = ReflexBuild(transport=MockTransport(mock_api))
    login = client.auth.begin_login(ui_url=ui_url)
    assert len(login.request_id) == 32
    assert login.url == f"{base}/cli/login?request_id={login.request_id}"
    assert client.auth.begin_login().request_id != login.request_id
    assert not mock_api.requests


LOGIN = LoginRequest(request_id="abc123", url="https://build.reflex.dev/cli/login")


def test_finish_login_waits_for_approval(mock_api: MockAPI):
    token = str(uuid.uuid4())
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(404, json={"detail": "Token not found or not yet approved"}),
        reply(404, json={"detail": "Token not found or not yet approved"}),
        reply(200, json={"token_id": token}),
    )
    # No token is needed to log in.
    with ReflexBuild(transport=MockTransport(mock_api)) as client:
        assert client.auth.finish_login(LOGIN, poll_interval=0) == token
    assert len(mock_api.requests) == 3
    for request in mock_api.requests:
        assert request.url.endswith("/cli/token?request_id=abc123")
        assert "X-API-TOKEN" not in request.headers


def test_finish_login_does_not_retry_a_lost_response(
    client: ReflexBuild, mock_api: MockAPI
):
    mock_api.add("GET", "/api/v1/cli/token", _lose_response)
    # A retry would find the token gone and keep waiting for a done approval.
    with pytest.raises(APIConnectionError, match="connection reset"):
        client.auth.finish_login(LOGIN, poll_interval=0)
    assert len(mock_api.requests) == 1


def test_finish_login_retries_an_unsent_request(client: ReflexBuild, mock_api: MockAPI):
    token = str(uuid.uuid4())

    def refuse_connection(request: Request) -> Response:
        msg = "connection refused"
        raise TransportError(msg, request=request, sent=False)

    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        refuse_connection,
        reply(200, json={"token_id": token}),
    )
    # The server never saw the first request, so the token is still there.
    assert client.auth.finish_login(LOGIN, poll_interval=0) == token
    assert len(mock_api.requests) == 2


def test_finish_login_denied(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(403, json={"detail": "Authorization request was denied"}),
    )
    with pytest.raises(LoginDeniedError):
        client.auth.finish_login(LOGIN, poll_interval=0)


def test_finish_login_waits_ten_minutes_by_default(mock_api: MockAPI):
    client = ReflexBuild(transport=MockTransport(mock_api))
    timeout = inspect.signature(client.auth.finish_login).parameters["timeout"]
    assert timeout.default == pytest.approx(600.0)


def test_finish_login_timeout(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/cli/token",
        reply(404, json={"detail": "Token not found or not yet approved"}),
    )
    with pytest.raises(LoginTimeoutError):
        client.auth.finish_login(LOGIN, timeout=0.05, poll_interval=60)
