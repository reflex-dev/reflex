"""Socket.IO event transport (requires the optional python-socketio dependency)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, MutableMapping
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from reflex_base import otel
from reflex_base.utils.types import ASGIApp, Message, Receive, Scope, Send
from socketio import ASGIApp as EngineIOApp
from socketio import AsyncNamespace, AsyncServer

from reflex.event_namespace import (
    _CLIENT_ERROR,
    _EVENT,
    _PING,
    BaseEventNamespace,
    _dumps,
    _socket_policy,
    utf8_size,
)

if TYPE_CHECKING:
    import asyncio

    from reflex_base.config import Config

    from reflex.app import App


def _sio_dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize an outgoing Socket.IO packet, recording its size when telemetry is on.

    Serialized like a plain transport frame: compact, with the non-finite
    float tokens the frontend revives, and valid UTF-8.

    Args:
        obj: The packet payload.
        **kwargs: Encoder options; socket.io only asks for compact separators.

    Returns:
        The JSON string.
    """
    data = _dumps(obj)
    if otel.enabled:
        otel.record_message_size(utf8_size(data), "transmit")
    return data


def _sio_loads(data: str | bytes, **kwargs: Any) -> Any:
    """Deserialize an incoming Socket.IO packet, recording its size when telemetry is on.

    Args:
        data: The JSON string.
        **kwargs: Options forwarded to the JSON decoder.

    Returns:
        The decoded payload.
    """
    if otel.enabled:
        otel.record_message_size(utf8_size(data), "receive")
    return json.loads(data, **kwargs)


# The JSON codec socket.io serializes packets with.
_SOCKET_JSON_CODEC = SimpleNamespace(
    dumps=staticmethod(_sio_dumps),
    loads=staticmethod(_sio_loads),
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
        # ASGI scope per session, so the per-event path reaches the connection
        # state it caches without going through the Socket.IO server.
        self._scopes: dict[str, MutableMapping[str, Any]] = {}

    async def on_connect(
        self, sid: str, environ: dict, auth: Any = None
    ) -> bool | None:
        """Event for when the websocket is connected.

        Args:
            sid: The Socket.IO session id.
            environ: The request information, including HTTP headers.
            auth: The payload of the CONNECT packet, carrying the boot event
                and the frontend state schema.

        Returns:
            False to refuse a session that linked no token or whose boot event
            failed, else None.
        """
        if (scope := environ.get("asgi.scope")) is not None:
            self._scopes[sid] = scope
        linked, boot_event = await self._open_session(
            sid,
            auth,
            environ.get("QUERY_STRING", ""),
            environ.get("HTTP_SEC_WEBSOCKET_PROTOCOL"),
        )
        # A failed boot event refuses the connect rather than raising, which
        # would keep the connect registered yet unanswered, or disconnecting,
        # which would acknowledge a session that never hydrated.
        if linked and (
            boot_event is None
            or await self._handle_boot_event(sid, boot_event, self._scope(sid)) is None
        ):
            return None
        # Socket.IO runs no disconnect handler for a refused connect, so undo
        # this one here.
        self.on_disconnect(sid)
        return False

    def on_disconnect(self, sid: str) -> asyncio.Task | None:
        """Event for when the websocket disconnects.

        Args:
            sid: The Socket.IO session id.

        Returns:
            An asyncio Task for cleaning up the token, or None.
        """
        self._scopes.pop(sid, None)
        return self.handle_disconnect(sid)

    async def on_event(self, sid: str, data: Any):
        """Event for receiving front-end websocket events.

        Args:
            sid: The Socket.IO session id.
            data: The event data.
        """
        # Inline rather than through _run_handler, which costs a coroutine
        # frame: this runs for every event.
        try:
            await self.handle_event(sid, data, self._scope(sid))
        except Exception as exc:
            if self._handler_failed(sid, f"socket event {_EVENT!r}", exc):
                await self.disconnect(sid)

    async def _run_handler(self, sid: str, event: str, handler: Awaitable[None]):
        """Await a socket event handler under the shared failure policy.

        Raising into python-socketio would log a traceback per frame, outside
        the budget that bounds client-triggered error logs.

        Args:
            sid: The Socket.IO session id.
            event: The socket event name, for the log.
            handler: The handler's coroutine.
        """
        try:
            await handler
        except Exception as exc:
            if self._handler_failed(sid, f"socket event {event!r}", exc):
                await self.disconnect(sid)

    def _scope(self, sid: str) -> MutableMapping[str, Any]:
        """Get the ASGI scope of a session's connection.

        A plain function, not a coroutine: it runs for every event.

        Args:
            sid: The Socket.IO session id.

        Returns:
            The ASGI scope.

        Raises:
            RuntimeError: If the Socket.IO is badly initialized.
        """
        if (scope := self._scopes.get(sid)) is not None:
            return scope
        # The connection was not seen by on_connect (e.g. the namespace was
        # registered after the socket connected); ask the server.
        if self.app.sio is None:
            msg = "Socket.IO is not initialized."
            raise RuntimeError(msg)
        environ = self.app.sio.get_environ(sid, self.namespace)
        if environ is None:
            msg = "Socket.IO environ is not initialized."
            raise RuntimeError(msg)
        scope = self._scopes[sid] = environ["asgi.scope"]
        return scope

    async def on_ping(self, sid: str):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        await self._run_handler(sid, _PING, self.handle_ping(sid))

    async def on_client_error(self, sid: str, data: Any = None):
        """Handle errors reported by the frontend.

        Args:
            sid: The Socket.IO session id.
            data: The error data from the client. Defaults to None because
                python-socketio dispatches a payload-less emit as
                ``on_client_error(sid)``; the malformed-payload guard then
                drops it without raising.
        """
        await self._run_handler(sid, _CLIENT_ERROR, self.handle_client_error(sid, data))


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
        polling = config.transport == "polling"
        policy = _socket_policy()
        app.sio = AsyncServer(
            async_mode="asgi",
            # An empty list disables CORS handling; engineio reads "*" among
            # the origins as allowing any.
            cors_allowed_origins=[] if polling else list(config.cors_allowed_origins),
            cors_credentials=not polling,
            max_http_buffer_size=policy.max_message_size,
            ping_interval=policy.ping_interval,
            ping_timeout=policy.ping_timeout,
            json=_SOCKET_JSON_CODEC,
            allow_upgrades=False,
            transports=["polling" if polling else "websocket"],
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
