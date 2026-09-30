"""HTTP and WebSocket transport for browser session credentials."""

from __future__ import annotations

import dataclasses
import json
import logging
from contextlib import nullcontext
from ipaddress import ip_address
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from reflex_base import constants
from reflex_base.environment import environment
from reflex_base.event.context import EventContext
from reflex_base.session import SessionToken, SessionTokenManager
from reflex_base.utils.exceptions import SessionAuthorizationError
from reflex_base.utils.types import ASGIApp, Message, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from reflex_base.config import Config

logger = logging.getLogger(__name__)


def _origin(url: str) -> str:
    """Extract a normalized HTTP origin from a configured URL.

    Args:
        url: The configured frontend or API URL.

    Returns:
        The URL's origin, or an empty string for non-HTTP URLs.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    port = parsed.port
    if port is not None and port != (443 if parsed.scheme == "https" else 80):
        host += f":{port}"
    return f"{parsed.scheme}://{host}"


def trusted_session_origins(config: Config) -> tuple[str, ...]:
    """Get the explicit browser origins allowed to install session credentials.

    A wildcard CORS policy cannot authorize credential exchange: accepting a
    session chosen by another origin would permit session fixation.

    Args:
        config: The application configuration.

    Returns:
        The trusted frontend, API, and explicitly configured CORS origins.
    """
    urls = [config.api_url, config.deploy_url or "", *config.cors_allowed_origins]
    if environment.REFLEX_ENV_MODE.get() == constants.Env.DEV:
        port = config.frontend_port or constants.DefaultPorts.FRONTEND_PORT
        urls.extend(
            f"http://{host}:{port}" for host in ("localhost", "127.0.0.1", "[::1]")
        )
    return tuple(dict.fromkeys(origin for url in urls if (origin := _origin(url))))


def _secure_cookie(api_url: str) -> bool:
    """Choose cookie security from the public API URL, including behind proxies.

    Args:
        api_url: The configured externally reachable backend URL.

    Returns:
        False only for development HTTP on a non-loopback host.
    """
    url = urlsplit(api_url)
    if url.scheme != "http" or environment.REFLEX_ENV_MODE.get() != constants.Env.DEV:
        return True
    hostname = url.hostname or ""
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _cookie_name(manager: SessionTokenManager, secure: bool) -> str:
    """Get the app-specific cookie name for this transport.

    Args:
        manager: The app's session manager.
        secure: Whether the cookie uses the secure host prefix.

    Returns:
        The cookie name.
    """
    return f"__Host-{manager.cookie_name}" if secure else manager.cookie_name


def _session_cookie(
    manager: SessionTokenManager, session: SessionToken, secure: bool
) -> bytes:
    """Serialize a session cookie without requiring Python's Partitioned support.

    Args:
        manager: The app's session manager.
        session: The session to encode.
        secure: Whether to use a secure, partitioned cookie.

    Returns:
        The Set-Cookie header value.
    """
    attributes = "SameSite=None; Secure; Partitioned" if secure else "SameSite=Lax"
    return (
        f"{_cookie_name(manager, secure)}={manager.encode(session)}; "
        f"Path=/; Max-Age={manager.ttl}; HttpOnly; {attributes}"
    ).encode("ascii")


class SessionMiddleware:
    """Validate sessions, hide their credentials, and scope HTTP state access."""

    def __init__(self, app: ASGIApp, manager: SessionTokenManager, api_url: str):
        """Wrap an ASGI app with browser session handling.

        Args:
            app: The next ASGI application.
            manager: The app's session manager.
            api_url: The configured externally reachable backend URL.
        """
        self.app = app
        self.manager = manager
        self.secure = _secure_cookie(api_url)
        self.cookie_name = _cookie_name(manager, self.secure)
        self._cookie_names = {manager.cookie_name, f"__Host-{manager.cookie_name}"}
        if not self.secure:
            logger.warning(
                "Session cookies use insecure SameSite=Lax on this development HTTP "
                "API URL. Use HTTPS for secure, cross-site session cookies."
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate credentials before invoking HTTP or WebSocket handlers.

        Args:
            scope: The incoming ASGI scope.
            receive: The request message receiver.
            send: The response message sender.

        Raises:
            SessionAuthorizationError: If state access fails after a response started.
        """
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        credentials = []
        headers = []
        for name, value in scope.get("headers", []):
            if name.lower() != b"cookie":
                headers.append((name, value))
                continue
            remaining = []
            for part in value.decode("latin-1").split(";"):
                cookie_name, _, cookie_value = part.strip().partition("=")
                if cookie_name in self._cookie_names:
                    if cookie_name == self.cookie_name:
                        credentials.append(cookie_value)
                else:
                    remaining.append(part)
            if remaining:
                headers.append((name, ";".join(remaining).strip().encode("latin-1")))

        scope["headers"] = headers
        session = self.manager.decode(credentials[0]) if len(credentials) == 1 else None
        scope["reflex.session"] = session
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_with_session(message: Message) -> None:
            """Refresh valid sessions when the HTTP response has no session cookie.

            Args:
                message: The outgoing ASGI message.
            """
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = message.setdefault("headers", [])
                if (
                    session is not None
                    and self.manager.should_refresh(session)
                    and not any(
                        name.lower() == b"set-cookie"
                        and value.startswith(f"{self.cookie_name}=".encode("ascii"))
                        for name, value in response_headers
                    )
                ):
                    response_headers.append((
                        b"set-cookie",
                        _session_cookie(
                            self.manager, self.manager.refresh(session), self.secure
                        ),
                    ))
            await send(message)

        try:
            context = dataclasses.replace(
                EventContext.get(), token="", session_token=session
            )
        except LookupError:
            context = nullcontext()
        with context:
            try:
                await self.app(scope, receive, send_with_session)
            except SessionAuthorizationError as error:
                if response_started:
                    raise
                response = await session_authorization_error(Request(scope), error)
                await response(scope, receive, send_with_session)


async def session_authorization_error(  # noqa: RUF029
    _request: Request, _exception: Exception
) -> JSONResponse:
    """Reject unauthorized state access without disclosing credential details.

    Args:
        _request: The incoming request.
        _exception: The authorization failure.

    Returns:
        A no-store forbidden response.
    """
    return JSONResponse(
        {"detail": "The session does not authorize this client token."},
        status_code=403,
        headers={"Cache-Control": "no-store"},
    )


async def session_endpoint(
    request: Request,
    *,
    manager: SessionTokenManager,
    api_url: str,
    allowed_origins: tuple[str, ...] = (),
) -> JSONResponse:
    """Create or renew a browser session and return a bound client token.

    The JSON response never includes the session credential. Non-simple fetch
    requests are required so browser cross-origin requests must pass CORS.
    Installing a credential supplied by a WebSocket bootstrap additionally
    requires an explicit trusted Origin to prevent session fixation.

    Args:
        request: The incoming POST request, after SessionMiddleware.
        manager: The app's session manager.
        api_url: The configured externally reachable backend URL.
        allowed_origins: Explicit browser origins trusted to exchange credentials.

    Returns:
        A no-store response with session metadata or a request rejection.
    """
    if request.headers.get("sec-fetch-mode") == "navigate" or (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
        and "reflex-client-token" not in request.headers
    ):
        return JSONResponse(
            {"detail": "Use a JSON fetch request to establish a session."},
            status_code=403,
            headers={"Cache-Control": "no-store"},
        )

    try:
        payload = json.loads(await request.body() or b"{}")
    except (ValueError, UnicodeError):
        payload = None
    if not isinstance(payload, dict) or (
        "session_token" in payload and not isinstance(payload["session_token"], str)
    ):
        return JSONResponse(
            {"detail": "Expected a JSON object with an optional session_token string."},
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    session = request.scope.get("reflex.session")
    if session is None and "session_token" in payload:
        origin = request.headers.get("origin")
        if origin is None or origin == "null" or origin not in allowed_origins:
            return JSONResponse(
                {"detail": "Session exchange requires a trusted Origin."},
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        session = manager.decode(payload["session_token"])
        if session is None:
            return JSONResponse(
                {"detail": "Invalid or expired session token."},
                status_code=401,
                headers={"Cache-Control": "no-store"},
            )
    session = manager.refresh(session) if session is not None else manager.create()
    client_token = request.headers.get("reflex-client-token", "")
    if not session.authorizes(client_token):
        client_token = manager.create_client_token(session)
    response = JSONResponse(
        {
            "token_type": "cookie",
            "expires_in": manager.ttl,
            "client_token": client_token,
        },
        headers={"Cache-Control": "no-store"},
    )
    response.raw_headers.append((
        b"set-cookie",
        _session_cookie(manager, session, _secure_cookie(api_url)),
    ))
    return response
