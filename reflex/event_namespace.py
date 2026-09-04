"""Event namespaces bridging client sessions to the Reflex event loop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.event import _EVENT_FIELDS, Event
from starlette.websockets import WebSocket, WebSocketDisconnect

from reflex.istate.data import RouterData
from reflex.istate.manager.token import BaseStateToken
from reflex.state import StateUpdate
from reflex.utils import exceptions, format
from reflex.utils.token_manager import RedisTokenManager, TokenManager

if TYPE_CHECKING:
    from reflex.app import App

logger = logging.getLogger(__name__)

# Protocol-level message names for the plain WebSocket transport. These are
# reserved (underscore-prefixed) and never dispatched as application events.
# They must match the names in .templates/web/utils/helpers/websocket.js.
HANDSHAKE_MESSAGE = "_handshake"
PING_MESSAGE = "_ping"
PONG_MESSAGE = "_pong"

# Application-level socket event names, resolved once for the hot paths.
_EVENT = str(constants.SocketEvent.EVENT)
_PING = str(constants.SocketEvent.PING)
_CLIENT_ERROR = str(constants.SocketEvent.CLIENT_ERROR)

# The heartbeat frame is static; serialize it once.
_PING_FRAME = json.dumps([PING_MESSAGE])


class BaseEventNamespace(ABC):
    """Transport-agnostic handler for client event sessions."""

    # The application object.
    app: App

    # Maximum error-level log entries a single session may produce via the
    # client_error event before further reports from it are dropped.
    _MAX_CLIENT_ERRORS_PER_SID = 5

    # Process-wide bound on error-level client_error log entries per time
    # window; per-SID budgets alone reset on reconnect, so scripted
    # reconnects could otherwise flood the logs.
    _CLIENT_ERROR_WINDOW_SECONDS = 60.0
    _MAX_CLIENT_ERRORS_PER_WINDOW = 20

    def __init__(self, namespace: str, app: App):
        """Initialize the event namespace.

        Args:
            namespace: The namespace.
            app: The application object.
        """
        self.namespace = namespace
        self.app = app

        # Use TokenManager for distributed duplicate tab prevention
        self._token_manager = TokenManager.create()

        # Number of client_error reports logged per SID, for rate limiting.
        self._client_error_counts: dict[str, int] = {}

        # Start time and count of the current process-wide client_error window.
        self._client_error_window_start = 0.0
        self._client_error_window_count = 0

    @property
    def token_to_sid(self) -> Mapping[str, str]:
        """Token to SID mapping for backward compatibility.

        Note: this mapping is read-only.

        Returns:
            The token to SID mapping.
        """
        # For backward compatibility, expose the underlying dict
        return self._token_manager.token_to_sid

    @property
    def sid_to_token(self) -> dict[str, str]:
        """SID to token mapping for backward compatibility.

        Returns:
            The SID to token mapping dict.
        """
        # For backward compatibility, expose the underlying dict
        return self._token_manager.sid_to_token

    @abstractmethod
    async def emit(self, event: str, data: Any = None, to: str | None = None) -> None:
        """Emit an event to a connected client session.

        Args:
            event: The event name.
            data: The event payload.
            to: The session id to emit to.
        """

    async def handle_connect(
        self, sid: str, query_string: str, subprotocol: str | None
    ) -> None:
        """Handle a new client session connecting.

        Args:
            sid: The session id.
            query_string: The raw query string of the connection request.
            subprotocol: The websocket subprotocol offered by the client.
        """
        if isinstance(self._token_manager, RedisTokenManager):
            # Make sure this instance is watching for updates from other instances.
            self._token_manager.ensure_lost_and_found_task(self.emit_update)
        query_params = urllib.parse.parse_qs(query_string)
        token_list = query_params.get("token", [])
        if not token_list:
            # A Reflex client always sends a token; the transport closes the
            # session, so a warning per hostile connect would only flood logs.
            logger.debug(f"No token provided in connection for session {sid}.")
            return
        await self.link_token_to_sid(sid, token_list[0])
        # Only report the version for linked sessions; the value is
        # client-controlled, so sanitize it before it reaches the logs.
        if subprotocol and subprotocol != constants.Reflex.VERSION:
            logger.warning(
                f"Frontend version {format.sanitize_client_log_value(subprotocol)} "
                f"for session {sid} does not match the backend version {constants.Reflex.VERSION}."
            )

    def handle_disconnect(self, sid: str) -> asyncio.Task | None:
        """Handle a client session disconnecting.

        Args:
            sid: The session id.

        Returns:
            An asyncio Task for cleaning up the token, or None.
        """
        self._client_error_counts.pop(sid, None)
        # Get token before cleaning up
        disconnect_token = self.sid_to_token.get(sid)
        if disconnect_token:
            # Use async cleanup through token manager
            task = asyncio.create_task(
                self._token_manager.disconnect_token(disconnect_token, sid),
                name=f"reflex_disconnect_token|{disconnect_token}|{time.time()}",
            )
            # Don't await to avoid blocking disconnect, but handle potential errors
            task.add_done_callback(
                lambda t: (
                    t.exception()
                    and logger.error(f"Token cleanup error: {t.exception()}")
                )
            )
            return task
        return None

    async def emit_update(self, update: StateUpdate, token: str) -> None:
        """Emit an update to the client.

        Args:
            update: The state update to send.
            token: The client token (tab) associated with the event.
        """
        socket_record = self._token_manager.token_to_socket.get(token)
        if (
            socket_record is None
            or socket_record.instance_id != self._token_manager.instance_id
        ):
            if isinstance(self._token_manager, RedisTokenManager):
                # The socket belongs to another instance of the app, send it to the lost and found.
                await self._token_manager.emit_lost_and_found(token, update)
            else:
                # If the socket record is None, we are not connected to a client. Prevent sending
                # updates to all clients.
                logger.warning(
                    f"Attempting to send delta to disconnected client {token!r}"
                )
            return
        # Awaiting a task wrapping the emit blocks just the same, so await it
        # directly and skip the task overhead.
        await self.emit(_EVENT, update, to=socket_record.sid)
        # The emit only queues the packet; yield a tick so the writer can flush
        # it before the caller potentially blocks the loop.
        await asyncio.sleep(0)

    async def handle_event(
        self, sid: str, data: Any, asgi_scope: MutableMapping[str, Any]
    ) -> None:
        """Handle an incoming front-end event.

        Args:
            sid: The session id.
            data: The event data.
            asgi_scope: The ASGI scope of the client connection.

        Raises:
            EventDeserializationError: If the event data is malformed.
        """
        # Determine the token for this SID
        if (token := self.sid_to_token.get(sid)) is None:
            logger.warning(
                f"Received event from session {sid} with no associated token. This may indicate a bug. Event data: {data}"
            )
            return

        # Both transports JSON-decode the frame, so a Reflex client's event
        # arrives as a dict; anything else (including a JSON-encoded string)
        # is rejected rather than logged per frame.
        if not isinstance(data, dict):
            msg = f"Event data must be a dictionary, but received {data} of type {type(data)}."
            raise exceptions.EventDeserializationError(msg)

        try:
            # Get the event.
            event = Event(**{k: v for k, v in data.items() if k in _EVENT_FIELDS})
        except (TypeError, ValueError) as ex:
            msg = f"Failed to deserialize event data: {data}."
            raise exceptions.EventDeserializationError(msg) from ex

        # The dataclass does not validate field types.
        if (
            not isinstance(event.name, str)
            or not isinstance(event.payload, dict)
            or not isinstance(event.router_data, dict)
        ):
            msg = "Event fields have invalid types."
            raise exceptions.EventDeserializationError(msg)

        # Decode the connection headers once: the scope is per-connection
        # state, so cache the decoded mapping in it and copy per event (the
        # copy is mutated below and ends up in the event's router_data).
        base_headers = asgi_scope.get("_reflex_headers")
        if base_headers is None:
            base_headers = {
                k.decode("utf-8"): v.decode("utf-8") for (k, v) in asgi_scope["headers"]
            }
            asgi_scope["_reflex_headers"] = base_headers
        headers = dict(base_headers)

        # Get the client IP
        client = asgi_scope.get("client")
        if client:
            client_ip = client[0]
            headers["asgi-scope-client"] = client_ip
        else:
            client_ip = "0.0.0.0"

        # Unroll reverse proxy forwarded headers.
        client_ip = (
            headers
            .get(
                "x-forwarded-for",
                client_ip,
            )
            .partition(",")[0]
            .strip()
        )
        router_data = event.router_data
        try:
            # The nested values are still client-controlled.
            router_data.update({
                constants.RouteVar.QUERY: format.format_query_params(event.router_data),
                constants.RouteVar.CLIENT_TOKEN: token,
                constants.RouteVar.SESSION_ID: sid,
                constants.RouteVar.HEADERS: headers,
                constants.RouteVar.CLIENT_IP: client_ip,
            })
            router_data[constants.RouteVar.PATH] = "/" + (
                self.app.router(path) or "404"
                if (path := router_data.get(constants.RouteVar.PATH))
                else "404"
            ).removeprefix("/")
        except (AttributeError, LookupError, TypeError, ValueError) as ex:
            msg = "Failed to normalize event router_data."
            raise exceptions.EventDeserializationError(msg) from ex
        await self.app.event_processor.enqueue(token, event)

    async def handle_ping(self, sid: str) -> None:
        """Handle an application-level ping test event.

        Args:
            sid: The session id.
        """
        # Emit the test event.
        await self.emit(_PING, "pong", to=sid)

    async def handle_client_error(self, sid: str, data: Any) -> None:
        """Handle errors reported by the frontend.

        This is a dedicated socket event rather than a state event
        (``FrontendEventExceptionState.handle_frontend_exception``) because a
        state event is addressed by a handler name the frontend derives from
        its own state definitions. When those definitions are what disagree
        with the backend -- the case this handler exists to report -- the name
        may not resolve and the report is lost. A fixed socket event name
        cannot drift, and it still gets through after the frontend has stopped
        sending events on detecting the mismatch.

        Reports are routed through the app's ``frontend_exception_handler``,
        so frontend errors (especially state update processing errors) are
        visible in backend logs and reach custom exception handlers.

        Args:
            sid: The session id.
            data: The error data from the client.
        """
        if not isinstance(data, dict):
            logger.debug(f"Ignoring malformed client_error payload from SID {sid}.")
            return

        # Check the sender and the rate limits before sanitizing: sanitizing is
        # linear in the size of the client-supplied values, and reports that are
        # dropped here must not cost more than the check itself.
        if sid not in self.sid_to_token:
            # Sockets without a linked token are not known clients; don't let
            # them write error-level entries into the backend logs.
            logger.debug(f"Ignoring client_error report from unknown SID {sid}.")
            return

        # Rate limit per session so a client cannot flood the backend logs.
        error_count = self._client_error_counts.get(sid, 0)
        if error_count >= self._MAX_CLIENT_ERRORS_PER_SID:
            return

        # Also bound total entries per time window: per-SID budgets reset on
        # reconnect, so they alone do not stop scripted reconnect loops.
        now = time.monotonic()
        if now - self._client_error_window_start > self._CLIENT_ERROR_WINDOW_SECONDS:
            self._client_error_window_start = now
            self._client_error_window_count = 0
        if self._client_error_window_count >= self._MAX_CLIENT_ERRORS_PER_WINDOW:
            if self._client_error_window_count == self._MAX_CLIENT_ERRORS_PER_WINDOW:
                # Warn once per window so suppression is visible in the logs
                # and a flooding client cannot silently starve reports from
                # other sessions.
                self._client_error_window_count += 1
                logger.warning(
                    f"Received more than {self._MAX_CLIENT_ERRORS_PER_WINDOW} "
                    f"client_error reports in {self._CLIENT_ERROR_WINDOW_SECONDS:.0f}s; "
                    "suppressing further reports for this window."
                )
            return
        self._client_error_window_count += 1
        self._client_error_counts[sid] = error_count + 1

        error_type = format.sanitize_client_log_value(data.get("error_type", "unknown"))
        if error_type == constants.ClientErrorType.DISPATCH_MISSING:
            substate = format.sanitize_client_log_value(data.get("substate", ""))
            report = (
                f"[SID: {sid}] State update failed: "
                f"no dispatch function for substate(s) '{substate}'. "
                "This indicates a frontend/backend state mismatch. "
                "Rebuild the frontend or check that api_url points to the matching backend."
            )
        else:
            message = format.sanitize_client_log_value(
                data.get("message", "No error message provided")
            )
            report = f"[SID: {sid}] {error_type}: {message}"
        # Route through the app's frontend exception handler so custom
        # handlers (e.g. error trackers) receive client errors too.
        self.app.frontend_exception_handler(Exception(report))

    async def link_token_to_sid(self, sid: str, token: str):
        """Link a token to a session id.

        Args:
            sid: The session id.
            token: The client token.
        """
        # Use TokenManager for duplicate detection and Redis support
        new_token = await self._token_manager.link_token_to_sid(token, sid)

        if new_token:
            # Duplicate detected, emit new token to client
            await self.emit("new_token", new_token, to=sid)

        # Update client state to apply new sid/token for running background tasks.
        if self.app._state is not None:
            async with self.app.state_manager.modify_state(
                BaseStateToken(ident=new_token or token, cls=self.app._state)
            ) as state:
                state.router_data[constants.RouteVar.SESSION_ID] = sid
                state.router = RouterData.from_router_data(state.router_data)


class WebsocketEventNamespace(BaseEventNamespace):
    """Default event transport over a plain WebSocket.

    Frames are JSON arrays ``[event_name, payload]``.
    """

    def __init__(self, namespace: str, app: App):
        """Initialize the websocket event namespace.

        Args:
            namespace: The namespace.
            app: The application object.
        """
        super().__init__(namespace, app)
        self._sockets: dict[str, WebSocket] = {}

    async def emit(self, event: str, data: Any = None, to: str | None = None) -> None:
        """Emit an event to a connected client session.

        Args:
            event: The event name.
            data: The event payload.
            to: The session id to emit to.
        """
        websocket = self._sockets.get(to) if to is not None else None
        if websocket is None:
            # Routine race: the client disconnected while an event was still
            # being processed, so its remaining updates have nowhere to go.
            logger.debug(f"Attempted to emit {event!r} to unknown session {to!r}.")
            return
        try:
            await websocket.send_text(format.json_dumps([event, data]))
        except Exception:
            # The connection went away mid-send; the receive loop cleans up.
            logger.debug(f"Failed to emit {event!r} to session {to!r}.", exc_info=True)

    @staticmethod
    def _origin_allowed(origin: str | None) -> bool:
        """Check a connection's Origin header against the CORS config.

        Args:
            origin: The Origin header value, if any.

        Returns:
            Whether the connection is allowed.
        """
        if origin is None:
            # Non-browser clients don't send an Origin header.
            return True
        allowed_origins = get_config().cors_allowed_origins
        return "*" in allowed_origins or origin in allowed_origins

    async def _handle_frame(
        self, sid: str, text: str, scope: MutableMapping[str, Any], max_size: int
    ) -> int | None:
        """Validate and dispatch one inbound text frame.

        Args:
            sid: The session id.
            text: The raw frame text.
            scope: The ASGI scope of the client connection.
            max_size: The message size limit in bytes.

        Returns:
            The websocket close code the session must end with, or None to
            keep serving it.
        """
        # ASGI delivers complete messages, so the server has already buffered
        # the frame; its protocol-level caps (enforced during frame
        # reassembly) bound that allocation. This check applies the Reflex
        # policy limit on top.
        # The limit is in bytes; UTF-8 encodes 1-4 bytes per character, so
        # more characters than the limit is certainly over, and a quarter or
        # fewer certainly under -- only encode to count the exact bytes in
        # between (bounding the copy to 4x the limit).
        text_length = len(text)
        if text_length > max_size or (
            text_length * 4 > max_size and len(text.encode("utf-8")) > max_size
        ):
            logger.debug(f"Closing session {sid}: message over {max_size} bytes.")
            return 1009
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            message = None
        if (
            not isinstance(message, list)
            or not message
            or not isinstance(message[0], str)
        ):
            # A Reflex client never sends malformed frames; close instead of
            # logging per frame, which a hostile client could use to flood
            # the logs.
            logger.debug(f"Closing session {sid}: malformed frame.")
            return 1002
        event = message[0]
        data = message[1] if len(message) > 1 else None
        try:
            # Ordered by frequency: events are the hot path, heartbeat pongs
            # arrive once per ping interval.
            if event == _EVENT:
                await self.handle_event(sid, data, scope)
            elif event == PONG_MESSAGE:
                # Receiving it already refreshed the liveness deadline.
                pass
            elif event == _PING:
                await self.handle_ping(sid)
            elif event == _CLIENT_ERROR:
                await self.handle_client_error(sid, data)
            else:
                logger.debug(
                    f"Ignoring unknown socket event {event!r} from session {sid}."
                )
        except exceptions.EventDeserializationError:
            # Client-controlled input a Reflex client never sends; close
            # instead of logging per frame.
            logger.debug(f"Closing session {sid}: undeserializable event.")
            return 1002
        except Exception:
            # A failing handler is a server-side bug: log it loudly; the
            # connection survives.
            logger.exception(
                f"Error handling socket event {event!r} for session {sid}."
            )
        return None

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Serve one client websocket connection for its full lifetime.

        Args:
            websocket: The client websocket connection.
        """
        if not self._origin_allowed(websocket.headers.get("origin")):
            # Reject cross-origin connections before accepting.
            await websocket.close(code=1008)
            return
        subprotocols = websocket.scope.get("subprotocols") or []
        # Echo the client's offered subprotocol (the Reflex version); browsers
        # abort the connection if the server selects none.
        await websocket.accept(subprotocol=subprotocols[0] if subprotocols else None)

        sid = str(uuid.uuid4())
        ping_interval = environment.REFLEX_SOCKET_INTERVAL.get()
        ping_timeout = environment.REFLEX_SOCKET_TIMEOUT.get()
        max_message_size = environment.REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE.get()
        self._sockets[sid] = websocket
        last_received = time.monotonic()

        async def heartbeat() -> None:
            try:
                while True:
                    await asyncio.sleep(ping_interval)
                    if time.monotonic() - last_received > ping_interval + ping_timeout:
                        await websocket.close(code=1001)
                        return
                    await websocket.send_text(_PING_FRAME)
            except Exception:
                # Socket went away; the receive loop handles cleanup.
                return

        heartbeat_task = asyncio.create_task(
            heartbeat(), name=f"reflex_heartbeat|{sid}"
        )
        try:
            # The handshake confirms application-level liveness and carries the
            # heartbeat settings for the client's connection watchdog.
            await websocket.send_text(
                format.json_dumps([
                    HANDSHAKE_MESSAGE,
                    {"ping_interval": ping_interval, "ping_timeout": ping_timeout},
                ])
            )
            await self.handle_connect(
                sid,
                websocket.scope.get("query_string", b"").decode(),
                subprotocols[0] if subprotocols else None,
            )
            if sid not in self._token_manager.sid_to_token:
                # No token was linked; not a Reflex client.
                await websocket.close(code=1008)
                return
            while True:
                received = await websocket.receive()
                if received["type"] == "websocket.disconnect":
                    break
                last_received = time.monotonic()
                text = received.get("text")
                if text is None:
                    # Binary frame; not part of the protocol.
                    logger.debug(f"Closing session {sid}: received a binary frame.")
                    close_code = 1003
                else:
                    close_code = await self._handle_frame(
                        sid, text, websocket.scope, max_message_size
                    )
                if close_code is not None:
                    await websocket.close(code=close_code)
                    break
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat_task.cancel()
            self._sockets.pop(sid, None)
            cleanup_task = self.handle_disconnect(sid)
            if cleanup_task is not None:
                # Await the token cleanup so an immediate reconnect is not
                # treated as a duplicate tab; shielded so cancellation (e.g.
                # server shutdown) cannot abort it. Errors are logged by the
                # task's done callback.
                with contextlib.suppress(Exception):
                    await asyncio.shield(cleanup_task)
