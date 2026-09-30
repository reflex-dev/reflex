"""Tests for browser session cookies, bootstrap requests, and request contexts."""

import asyncio
from functools import partial
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from reflex_base.config import Config
from reflex_base.event.context import EventContext
from reflex_base.session import SessionToken, SessionTokenManager
from reflex_base.utils.exceptions import SessionAuthorizationError
from reflex_base.utils.types import Scope
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from reflex.session import (
    SessionMiddleware,
    session_authorization_error,
    session_endpoint,
    trusted_session_origins,
)


@pytest.fixture
def manager() -> SessionTokenManager:
    """Create an isolated session codec.

    Returns:
        A manager with a fixed test signing key.
    """
    return SessionTokenManager("session_test", ttl=100, secrets=(b"s" * 32,))


def _inspect(request: Request) -> JSONResponse:
    """Expose non-secret request details for transport assertions.

    Args:
        request: The request after middleware processing.

    Returns:
        The cookie header and public session identifier.
    """
    session = request.scope["reflex.session"]
    return JSONResponse({
        "cookies": request.headers.getlist("cookie"),
        "session": session.id if session else None,
    })


def _app(
    manager: SessionTokenManager,
    api_url: str = "https://api.test",
    allowed_origins: tuple[str, ...] = ("https://api.test",),
) -> SessionMiddleware:
    """Build the session routes without Reflex application state.

    Args:
        manager: The session manager.
        api_url: The configured public backend URL.
        allowed_origins: Origins allowed to exchange a session credential.

    Returns:
        A minimal ASGI app with session middleware.
    """
    return SessionMiddleware(
        Starlette(
            routes=[
                Route("/", _inspect),
                Route(
                    "/_reflex/session",
                    partial(
                        session_endpoint,
                        manager=manager,
                        api_url=api_url,
                        allowed_origins=allowed_origins,
                    ),
                    methods=["POST"],
                ),
            ]
        ),
        manager=manager,
        api_url=api_url,
    )


def test_bootstrap_session(manager: SessionTokenManager):
    """The bootstrap returns only a bound client token and an HttpOnly cookie.

    Args:
        manager: The session manager.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post("/_reflex/session", json={})
        cookie = response.cookies[f"__Host-{manager.cookie_name}"]
        session = manager.decode(cookie)
        assert session is not None
        assert response.json() == {
            "token_type": "cookie",
            "expires_in": 100,
            "client_token": response.json()["client_token"],
        }
        assert session.authorizes(response.json()["client_token"])
        assert cookie not in response.text
        assert response.headers["cache-control"] == "no-store"
        attributes = set(response.headers["set-cookie"].split("; ")[1:])
        assert attributes == {
            "Path=/",
            "Max-Age=100",
            "HttpOnly",
            "SameSite=None",
            "Secure",
            "Partitioned",
        }
        inspected = client.get("/")
        assert inspected.json() == {"cookies": [], "session": session.id}
        assert "set-cookie" not in inspected.headers


def test_bootstrap_preserves_owned_client_token(manager: SessionTokenManager):
    """Renewal preserves session identity and only echoes tokens it owns.

    Args:
        manager: The session manager.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        first = client.post("/_reflex/session", json={})
        first_session = manager.decode(first.cookies[f"__Host-{manager.cookie_name}"])
        assert first_session is not None
        token = first.json()["client_token"]
        second = client.post("/_reflex/session", headers={"Reflex-Client-Token": token})
        assert second.json()["client_token"] == token
        second_session = manager.decode(second.cookies[f"__Host-{manager.cookie_name}"])
        assert second_session is not None
        assert second_session.id == first_session.id

        foreign_token = manager.create_client_token(manager.create())
        third = client.post(
            "/_reflex/session", headers={"Reflex-Client-Token": foreign_token}
        )
        assert third.json()["client_token"] != foreign_token
        assert first_session.authorizes(third.json()["client_token"])


def test_exchange_websocket_session(manager: SessionTokenManager):
    """A trusted frontend can persist a session received over its WebSocket.

    Args:
        manager: The session manager.
    """
    session = manager.create()
    token = manager.create_client_token(session)
    credential = manager.encode(session)
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post(
            "/_reflex/session",
            json={"session_token": credential},
            headers={"Origin": "https://api.test", "Reflex-Client-Token": token},
        )
    assert response.status_code == 200
    exchanged = manager.decode(response.cookies[f"__Host-{manager.cookie_name}"])
    assert exchanged is not None
    assert exchanged.id == session.id
    assert response.json()["client_token"] == token
    assert credential not in response.text


@pytest.mark.parametrize(
    "origin", [None, "null", "https://evil.test", "*", "https://api.test.evil.test"]
)
def test_exchange_rejects_untrusted_origin(
    manager: SessionTokenManager, origin: str | None
):
    """An attacker cannot install a known session through wildcard CORS.

    Args:
        manager: The session manager.
        origin: An untrusted or missing request Origin.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post(
            "/_reflex/session",
            json={"session_token": manager.encode(manager.create())},
            headers={"Origin": origin} if origin else {},
        )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_exchange_cookie_has_precedence(manager: SessionTokenManager):
    """A body credential cannot replace an existing authenticated session.

    Args:
        manager: The session manager.
    """
    session = manager.create()
    cookie_name = f"__Host-{manager.cookie_name}"
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post(
            "/_reflex/session",
            json={"session_token": manager.encode(manager.create())},
            headers={
                "Cookie": f"{cookie_name}={manager.encode(session)}",
                "Origin": "https://evil.test",
            },
        )
    assert response.status_code == 200
    refreshed = manager.decode(response.cookies[cookie_name])
    assert refreshed is not None
    assert refreshed.id == session.id


@pytest.mark.parametrize(
    "body",
    [b"not-json", b"null", b"[]", b'{"session_token":null}', b'{"session_token":42}'],
)
def test_exchange_rejects_malformed_body(manager: SessionTokenManager, body: bytes):
    """Malformed exchange payloads are rejected without creating a session.

    Args:
        manager: The session manager.
        body: The malformed JSON payload.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post(
            "/_reflex/session",
            content=body,
            headers={"Content-Type": "application/json", "Origin": "https://api.test"},
        )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("navigate", [False, True])
def test_exchange_rejects_invalid_credential_or_navigation(
    manager: SessionTokenManager, navigate: bool
):
    """Only verified credentials sent by fetch can become cookies.

    Args:
        manager: The session manager.
        navigate: Whether the request is a browser navigation.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post(
            "/_reflex/session",
            json={
                "session_token": manager.encode(manager.create())
                if navigate
                else "invalid"
            },
            headers={
                "Origin": "https://api.test",
                "Sec-Fetch-Mode": "navigate" if navigate else "cors",
            },
        )
    assert response.status_code == (403 if navigate else 401)
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("mode", ["dev", "prod"])
def test_trusted_session_origins(monkeypatch: pytest.MonkeyPatch, mode: str):
    """Exchange trusts explicit configured origins and development loopbacks.

    Args:
        monkeypatch: Environment fixture.
        mode: The runtime mode.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", mode)
    config = Config(
        app_name="test",
        api_url="https://API.test:443/backend/",
        deploy_url="https://frontend.test/app/",
        frontend_port=3456,
        cors_allowed_origins=["*", "https://embed.test", "https://frontend.test"],
    )
    origins = trusted_session_origins(config)
    assert origins[:3] == (
        "https://api.test",
        "https://frontend.test",
        "https://embed.test",
    )
    assert "*" not in origins
    assert origins[3:] == (
        ("http://localhost:3456", "http://127.0.0.1:3456", "http://[::1]:3456")
        if mode == "dev"
        else ()
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/x-www-form-urlencoded"},
        {"Content-Type": "application/json", "Sec-Fetch-Mode": "navigate"},
    ],
)
def test_bootstrap_rejects_simple_requests(manager: SessionTokenManager, headers: dict):
    """Forms and navigation cannot mint a session.

    Args:
        manager: The session manager.
        headers: Headers that do not identify a permitted fetch request.
    """
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.post("/_reflex/session", headers=headers)
        assert response.status_code == 403
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers
        assert client.get("/_reflex/session").status_code == 405


@pytest.mark.parametrize("cookie", [None, "invalid"])
def test_ordinary_requests_never_create_sessions(
    manager: SessionTokenManager, mocker: MockerFixture, cookie: str | None
):
    """Missing and malformed credentials remain unauthenticated.

    Args:
        manager: The session manager.
        mocker: Mock fixture.
        cookie: An optional malformed cookie.
    """
    create = mocker.spy(manager, "create")
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.get(
            "/",
            headers={"cookie": f"__Host-{manager.cookie_name}={cookie}"}
            if cookie
            else {},
        )
    assert response.json() == {"cookies": [], "session": None}
    assert "set-cookie" not in response.headers
    create.assert_not_called()


@pytest.mark.parametrize("duplicate", [False, True])
def test_session_cookie_stripping(manager: SessionTokenManager, duplicate: bool):
    """Split cookie headers retain unrelated cookies and reject duplicate sessions.

    Args:
        manager: The session manager.
        duplicate: Whether the expected cookie name appears twice.
    """
    session = manager.create()
    cookie = manager.encode(session)
    cookie_name = f"__Host-{manager.cookie_name}"
    headers = [
        ("cookie", f"auth=enterprise; {cookie_name}={cookie}; preference=dark"),
        ("cookie", f"{manager.cookie_name}=invalid; other_app_session=keep"),
    ]
    if duplicate:
        headers.append(("cookie", f"{cookie_name}={cookie}"))
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.get("/", headers=headers)
    assert response.json() == {
        "cookies": ["auth=enterprise; preference=dark", "other_app_session=keep"],
        "session": None if duplicate else session.id,
    }


def test_http_refresh_keeps_session_identity(
    manager: SessionTokenManager, mocker: MockerFixture
):
    """Expired refresh intervals renew credentials without losing client bindings.

    Args:
        manager: The session manager.
        mocker: Mock fixture.
    """
    now = mocker.patch("reflex_base.session.time.time", return_value=1000)
    session = manager.create()
    token = manager.create_client_token(session)
    cookie_name = f"__Host-{manager.cookie_name}"
    cookie = manager.encode(session)
    now.return_value = 1060
    with TestClient(_app(manager), base_url="https://api.test") as client:
        response = client.get("/", headers={"cookie": f"{cookie_name}={cookie}"})
        refreshed = manager.decode(response.cookies[cookie_name])
        assert refreshed is not None
        assert refreshed.id == session.id
        assert refreshed.expires_at == 1160
        assert refreshed.authorizes(token)
        bootstrap = client.post(
            "/_reflex/session", json={}, headers={"cookie": f"{cookie_name}={cookie}"}
        )
        assert len(bootstrap.headers.get_list("set-cookie")) == 1


@pytest.mark.parametrize(
    ("api_url", "mode", "secure"),
    [
        ("https://api.test", "dev", True),
        ("http://localhost:8000", "dev", True),
        ("http://127.0.0.1:8000", "dev", True),
        ("http://[::1]:8000", "dev", True),
        ("http://192.168.1.5:8000", "dev", False),
        ("http://api.test", "prod", True),
    ],
)
def test_cookie_policy(
    manager: SessionTokenManager,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    api_url: str,
    mode: str,
    secure: bool,
):
    """Public API configuration controls cookies even behind HTTP proxies.

    Args:
        manager: The session manager.
        monkeypatch: Environment fixture.
        caplog: Captured log fixture.
        api_url: The externally reachable URL.
        mode: The app runtime mode.
        secure: Whether a secure cookie is expected.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", mode)
    with TestClient(_app(manager, api_url), base_url="http://internal-proxy") as client:
        response = client.post("/_reflex/session", json={})
    cookie = response.headers["set-cookie"]
    assert ("; Secure" in cookie) is secure
    assert ("; Partitioned" in cookie) is secure
    assert cookie.startswith("__Host-") is secure
    assert f"SameSite={'None' if secure else 'Lax'}" in cookie
    assert ("insecure SameSite=Lax" in caplog.text) is not secure


@pytest.mark.asyncio
async def test_websocket_validates_without_setting_cookie(
    manager: SessionTokenManager, mocker: MockerFixture
):
    """WebSocket handshakes expose the session without refreshing its credential.

    Args:
        manager: The session manager.
        mocker: Mock fixture.
    """
    session = manager.create()
    cookie = manager.encode(session)
    app, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
    refresh = mocker.spy(manager, "refresh")
    scope: Scope = {
        "type": "websocket",
        "headers": [(b"cookie", f"__Host-{manager.cookie_name}={cookie}".encode())],
    }
    await SessionMiddleware(app, manager, "https://api.test")(scope, receive, send)
    assert scope["reflex.session"].id == session.id
    assert scope["headers"] == []
    app.assert_awaited_once_with(scope, receive, send)
    refresh.assert_not_called()
    send.assert_not_called()


@pytest.mark.asyncio
async def test_http_context_isolation(manager: SessionTokenManager):
    """Concurrent requests narrow the root context and restore it afterward.

    Args:
        manager: The session manager.
    """
    sessions = [manager.create(), manager.create()]
    root = EventContext(
        token="",
        session_token=SessionToken.SYSTEM,
        state_manager=AsyncMock(),
        enqueue_impl=AsyncMock(),
    )
    observed = []

    async def inner(scope, receive, send):
        """Observe the request context across task switches."""
        await asyncio.sleep(0)
        context = EventContext.get()
        assert context.token == ""
        assert context.cached_states is not root.cached_states
        assert context.session_token is scope["reflex.session"]
        observed.append(context.session_token.id if context.session_token else None)

    middleware = SessionMiddleware(inner, manager, "https://api.test")
    with root:
        await asyncio.gather(
            *[
                middleware(
                    {
                        "type": "http",
                        "headers": [
                            (
                                b"cookie",
                                f"__Host-{manager.cookie_name}={manager.encode(session)}".encode(),
                            )
                        ],
                    },
                    AsyncMock(),
                    AsyncMock(),
                )
                for session in sessions
            ],
            middleware({"type": "http", "headers": []}, AsyncMock(), AsyncMock()),
        )
        assert EventContext.get() is root
    assert set(observed) == {None, *(session.id for session in sessions)}


@pytest.mark.asyncio
async def test_http_unauthorized_state_access_is_forbidden(
    manager: SessionTokenManager,
):
    """State authorization errors become 403 before a response starts.

    Args:
        manager: The session manager.
    """
    send = AsyncMock()
    await SessionMiddleware(
        AsyncMock(side_effect=SessionAuthorizationError("private diagnostics")),
        manager,
        "https://api.test",
    )(
        {"type": "http", "headers": []},
        AsyncMock(),
        send,
    )
    assert send.await_args_list[0].args[0]["status"] == 403
    assert b"private diagnostics" not in send.await_args_list[1].args[0]["body"]


def test_starlette_unauthorized_state_access_is_forbidden(manager: SessionTokenManager):
    """Starlette handles authorization failures before its generic 500 handler.

    Args:
        manager: The session manager.
    """

    def forbidden(request: Request) -> JSONResponse:
        """Reject access to another session's client state.

        Args:
            request: The incoming request.

        Raises:
            SessionAuthorizationError: Always.
        """
        msg = "private diagnostics"
        raise SessionAuthorizationError(msg)

    app = Starlette(
        routes=[Route("/", forbidden)],
        exception_handlers={SessionAuthorizationError: session_authorization_error},
    )
    with TestClient(SessionMiddleware(app, manager, "https://api.test")) as client:
        response = client.get("/")
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "private diagnostics" not in response.text
