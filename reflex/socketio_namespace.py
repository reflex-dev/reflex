"""Socket.IO event transport (requires the optional python-socketio dependency)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from reflex_base.environment import environment
from reflex_base.utils.types import ASGIApp, Message, Receive, Scope, Send
from socketio import ASGIApp as EngineIOApp
from socketio import AsyncNamespace, AsyncServer

from reflex.event_namespace import BaseEventNamespace
from reflex.utils import format

if TYPE_CHECKING:
    import asyncio

    from reflex_base.config import Config

    from reflex.app import App


# The JSON codec socket.io serializes packets with: Reflex's dumps (which
# emits the non-finite float tokens the frontend revives) and the stdlib
# loads for client-supplied data.
_SOCKET_JSON_CODEC = SimpleNamespace(
    dumps=staticmethod(format.json_dumps),
    loads=staticmethod(json.loads),
)


class EventNamespace(AsyncNamespace, BaseEventNamespace):
    """The Socket.IO event namespace."""

    def __init__(self, namespace: str, app: App):
        """Initialize the event namespace.

        Args:
            namespace: The namespace.
            app: The application object.
        """
        AsyncNamespace.__init__(self, namespace)
        BaseEventNamespace.__init__(self, namespace, app)

    async def on_connect(self, sid: str, environ: dict):
        """Event for when the websocket is connected.

        Args:
            sid: The Socket.IO session id.
            environ: The request information, including HTTP headers.
        """
        await self.handle_connect(
            sid,
            environ.get("QUERY_STRING", ""),
            environ.get("HTTP_SEC_WEBSOCKET_PROTOCOL"),
        )

    def on_disconnect(self, sid: str) -> asyncio.Task | None:
        """Event for when the websocket disconnects.

        Args:
            sid: The Socket.IO session id.

        Returns:
            An asyncio Task for cleaning up the token, or None.
        """
        return self.handle_disconnect(sid)

    async def on_event(self, sid: str, data: Any):
        """Event for receiving front-end websocket events.

        Args:
            sid: The Socket.IO session id.
            data: The event data.

        Raises:
            RuntimeError: If the Socket.IO is badly initialized.
        """
        if self.app.sio is None:
            msg = "Socket.IO is not initialized."
            raise RuntimeError(msg)
        environ = self.app.sio.get_environ(sid, self.namespace)
        if environ is None:
            msg = "Socket.IO environ is not initialized."
            raise RuntimeError(msg)
        await self.handle_event(sid, data, environ["asgi.scope"])

    async def on_ping(self, sid: str):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        await self.handle_ping(sid)

    async def on_client_error(self, sid: str, data: Any = None):
        """Handle errors reported by the frontend.

        Args:
            sid: The Socket.IO session id.
            data: The error data from the client. Defaults to None because
                python-socketio dispatches a payload-less emit as
                ``on_client_error(sid)``; the malformed-payload guard then
                drops it without raising.
        """
        await self.handle_client_error(sid, data)


class _HeaderMiddleware:
    """Echo the websocket subprotocol on accept, which engineio does not."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware.

        Args:
            app: The ASGI app to wrap.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle an ASGI connection.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.

        Returns:
            The result of the wrapped app.
        """
        original_send = send

        async def modified_send(message: Message):
            if message["type"] == "websocket.accept":
                if scope.get("subprotocols"):
                    # The following *does* say "subprotocol" instead of "subprotocols", intentionally.
                    message["subprotocol"] = scope["subprotocols"][0]

                headers = dict(message.get("headers", []))
                header_key = b"sec-websocket-protocol"
                if subprotocol := headers.get(header_key):
                    message["headers"] = [
                        *message.get("headers", []),
                        (header_key, subprotocol),
                    ]

            return await original_send(message)

        return await self.app(scope, receive, modified_send)


def create_socketio_app(app: App, config: Config) -> ASGIApp:
    """Create the Socket.IO server for an app and return its ASGI app.

    Creates ``app.sio`` if the user did not supply their own server.

    Args:
        app: The Reflex app.
        config: The app configuration.

    Returns:
        The ASGI app serving the Socket.IO server.

    Raises:
        RuntimeError: If a custom ``sio`` server does not use asgi mode.
    """
    if not app.sio:
        app.sio = AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=(
                (
                    "*"
                    if config.cors_allowed_origins == ("*",)
                    else list(config.cors_allowed_origins)
                )
                if config.transport != "polling"
                else []
            ),
            cors_credentials=config.transport != "polling",
            max_http_buffer_size=environment.REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE.get(),
            ping_interval=environment.REFLEX_SOCKET_INTERVAL.get(),
            ping_timeout=environment.REFLEX_SOCKET_TIMEOUT.get(),
            json=_SOCKET_JSON_CODEC,
            allow_upgrades=False,
            transports=["polling" if config.transport == "polling" else "websocket"],
            # Handlers here only parse and enqueue (or emit a pong), so run
            # them inline on the socket's receive loop instead of paying a
            # task creation and a loop hop per incoming message.
            async_handlers=False,
        )
    elif getattr(app.sio, "async_mode", "") != "asgi":
        msg = f"Custom `sio` must use `async_mode='asgi'`, not '{app.sio.async_mode}'."
        raise RuntimeError(msg)

    # Create the socket app. Note event endpoint constant replaces the default 'socket.io' path.
    return _HeaderMiddleware(EngineIOApp(app.sio, socketio_path=""))
