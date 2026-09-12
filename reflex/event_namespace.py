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
from collections.abc import Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

from reflex_base import constants, otel
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.event import _EVENT_FIELDS, Event
from starlette.websockets import WebSocket, WebSocketDisconnect

from reflex.channels import MAX_MESSAGE_BUFFERS, ChannelSession
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
OPEN_MESSAGE = "_open"
OPENED_MESSAGE = "_opened"
CLOSE_MESSAGE = "_close"
CHANNEL_ERROR_MESSAGE = "_error"

# Wire protocol version, announced in the handshake. The client gates channel
# frames on it: a backend that predates channels closes the connection on the
# binary frames they use.
PROTOCOL_VERSION = 2

# Binary channel frames align every attachment to this boundary so the client
# can view them as typed arrays without copying.
_FRAME_ALIGNMENT = 8

# Bound on the JSON header of a binary channel frame.
_MAX_FRAME_HEADER_SIZE = 64 * 1024

# Application-level socket event names, resolved once for the hot paths.
_EVENT = str(constants.SocketEvent.EVENT)
_PING = str(constants.SocketEvent.PING)
_CLIENT_ERROR = str(constants.SocketEvent.CLIENT_ERROR)

# The heartbeat frame is static; serialize it once.
_PING_FRAME = json.dumps([PING_MESSAGE])


def utf8_size(data: str | bytes) -> int:
    """Size of a serialized message in UTF-8 bytes.

    ASCII payloads (the common case) are sized without encoding a copy.

    Args:
        data: The serialized message, text or binary.

    Returns:
        The number of bytes the message occupies on the wire.
    """
    if isinstance(data, bytes):
        return len(data)
    return len(data) if data.isascii() else len(data.encode())


def encode_channel_frame(
    event: str, data: Any, channel: str, buffers: Sequence[bytes]
) -> bytes:
    """Serialize a channel message carrying binary attachments.

    The frame is a 4-byte little-endian header length, the JSON header
    ``[event, data, channel, [lengths]]``, then the attachments, each padded
    so every payload starts on an 8-byte boundary.

    Args:
        event: The message name.
        data: The JSON-serializable metadata.
        channel: The channel name.
        buffers: The binary attachments.

    Returns:
        The frame bytes.
    """
    header = format.json_dumps([
        event,
        data,
        channel,
        [len(buffer) for buffer in buffers],
    ]).encode()
    parts = [len(header).to_bytes(4, "little"), header]
    offset = 4 + len(header)
    for buffer in buffers:
        padding = -offset % _FRAME_ALIGNMENT
        if padding:
            parts.append(bytes(padding))
        parts.append(buffer)
        offset += padding + len(buffer)
    return b"".join(parts)


def decode_channel_frame(frame: bytes) -> tuple[str, Any, str, list[bytes]]:
    """Deserialize a binary channel frame.

    Args:
        frame: The raw frame bytes.

    Returns:
        The message name, metadata, channel name and binary attachments.

    Raises:
        ValueError: If the frame does not follow the binary channel format.
    """
    if len(frame) < 4:
        msg = "Binary frame is too short to hold a header length."
        raise ValueError(msg)
    header_size = int.from_bytes(frame[:4], "little")
    if header_size > _MAX_FRAME_HEADER_SIZE or 4 + header_size > len(frame):
        msg = f"Binary frame declares an unusable header size {header_size}."
        raise ValueError(msg)
    try:
        header = json.loads(frame[4 : 4 + header_size])
    except RecursionError as ex:
        # The JSON decoder recurses per nesting level, so a header nested
        # deeper than its stack allows never parses. That is malformed input
        # like any other, and callers should not have to know that the
        # decoder signals it differently.
        msg = "Binary frame header is nested too deeply."
        raise ValueError(msg) from ex
    match header:
        case [str(event), data, str(channel), [*lengths]] if all(
            isinstance(length, int) and not isinstance(length, bool) and length >= 0
            for length in lengths
        ):
            pass
        case _:
            msg = "Binary frame header is malformed."
            raise ValueError(msg)
    if len(lengths) > MAX_MESSAGE_BUFFERS:
        msg = f"Binary frame carries more than {MAX_MESSAGE_BUFFERS} attachments."
        raise ValueError(msg)
    buffers: list[bytes] = []
    offset = 4 + header_size
    for length in lengths:
        offset += -offset % _FRAME_ALIGNMENT
        end = offset + length
        if end > len(frame):
            msg = "Binary frame is shorter than its declared attachments."
            raise ValueError(msg)
        buffers.append(frame[offset:end])
        offset = end
    return event, data, channel, buffers


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
        if otel.enabled:
            otel.record_connection(1)
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
        if otel.enabled:
            otel.record_connection(-1)
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
        if not otel.enabled:
            await self.app.event_processor.enqueue(token, event)
            return
        with otel.remote_context(data):
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
        # Open channel sessions per connection, by session id and channel name.
        self._channel_sessions: dict[str, dict[str, ChannelSession]] = {}

    async def _deliver(self, to: str | None, payload: str | bytes, label: str) -> None:
        """Write one serialized frame to a connected client session.

        Args:
            to: The session id to send to.
            payload: The serialized text or binary frame.
            label: The message name, for diagnostics.
        """
        websocket = self._sockets.get(to) if to is not None else None
        if websocket is None:
            # Routine race: the client disconnected while an event was still
            # being processed, so its remaining updates have nowhere to go.
            logger.debug(f"Attempted to emit {label!r} to unknown session {to!r}.")
            return
        if otel.enabled:
            otel.record_message_size(utf8_size(payload), "transmit")
        try:
            if isinstance(payload, str):
                await websocket.send_text(payload)
            else:
                await websocket.send_bytes(payload)
        except Exception:
            # The connection went away mid-send; the receive loop cleans up.
            logger.debug(f"Failed to emit {label!r} to session {to!r}.", exc_info=True)

    async def emit(self, event: str, data: Any = None, to: str | None = None) -> None:
        """Emit an event to a connected client session.

        Args:
            event: The event name.
            data: The event payload.
            to: The session id to emit to.
        """
        await self._deliver(to, format.json_dumps([event, data]), event)

    async def _send_channel_message(
        self,
        sid: str,
        channel: str,
        event: str,
        data: Any,
        buffers: Sequence[bytes],
    ) -> None:
        """Send one channel message to a connected client session.

        Args:
            sid: The session id to send to.
            channel: The channel name.
            event: The message name.
            data: The JSON-serializable metadata.
            buffers: The binary attachments.
        """
        payload = (
            encode_channel_frame(event, data, channel, buffers)
            if buffers
            else format.json_dumps([event, data, channel])
        )
        await self._deliver(sid, payload, event)

    async def _send_channel_error(
        self, sid: str, channel: str, code: str, message: str
    ) -> None:
        """Report a channel-level failure to a client session.

        Args:
            sid: The session id.
            channel: The channel name.
            code: The machine-readable error code.
            message: The human-readable explanation.
        """
        await self._send_channel_message(
            sid, channel, CHANNEL_ERROR_MESSAGE, {"code": code, "message": message}, ()
        )

    async def _open_channel_session(self, sid: str, channel_name: str) -> None:
        """Open a channel session for a connection, answering the client.

        Args:
            sid: The session id.
            channel_name: The channel the client is opening.
        """
        if channel_name in self._channel_sessions.get(sid, ()):
            # Opening twice would orphan the first session in its rooms; the
            # client only opens once per connection, so answer and move on.
            await self._send_channel_message(
                sid, channel_name, OPENED_MESSAGE, None, ()
            )
            return
        channel = self.app._channels.get(channel_name)
        if channel is None:
            await self._send_channel_error(
                sid,
                channel_name,
                "unknown_channel",
                f"No channel named {channel_name!r} is registered.",
            )
            return
        token = self.sid_to_token.get(sid)
        if token is None:
            # The token was unlinked while the frame was in flight.
            logger.debug(f"Ignoring channel open from session {sid} with no token.")
            return
        session = channel.open_session(sid, token, self._send_channel_message)
        # Track the session before the hook runs: on_open may join rooms, and
        # if it is interrupted the disconnect cleanup must still find it.
        sessions = self._channel_sessions.setdefault(sid, {})
        sessions[channel_name] = session
        try:
            await channel.on_open(session)
        except Exception:
            self._drop_channel_session(sid, channel_name)
            logger.exception(
                f"Error opening channel {channel_name!r} for session {sid}."
            )
            await self._send_channel_error(
                sid, channel_name, "open_failed", "The channel failed to open."
            )
            return
        await self._send_channel_message(sid, channel_name, OPENED_MESSAGE, None, ())

    async def _close_channel_session(self, sid: str, channel_name: str) -> None:
        """Close one open channel session.

        Args:
            sid: The session id.
            channel_name: The channel to close.
        """
        session = self._drop_channel_session(sid, channel_name)
        if session is not None:
            await self._notify_channel_close(sid, channel_name, session)

    def _drop_channel_session(
        self, sid: str, channel_name: str
    ) -> ChannelSession | None:
        """Remove one session from the connection, along with its rooms.

        Args:
            sid: The session id.
            channel_name: The channel to drop.

        Returns:
            The dropped session, or None if it was not open.
        """
        sessions = self._channel_sessions.get(sid)
        session = sessions.pop(channel_name, None) if sessions is not None else None
        if session is None:
            return None
        if not sessions:
            del self._channel_sessions[sid]
        session.channel.forget_session(session)
        return session

    async def _close_channel_sessions(self, sid: str) -> None:
        """Close every channel session of a disconnected connection.

        Args:
            sid: The session id.
        """
        sessions = self._channel_sessions.pop(sid, None)
        if not sessions:
            return
        # Drop rooms and tracking for all of them first: this runs during
        # teardown, where a cancellation at the first await would otherwise
        # leave the remaining sessions reachable by fan-out forever.
        for session in sessions.values():
            session.channel.forget_session(session)
        for channel_name, session in sessions.items():
            await self._notify_channel_close(sid, channel_name, session)

    @staticmethod
    async def _notify_channel_close(
        sid: str, channel_name: str, session: ChannelSession
    ) -> None:
        """Run a channel's close hook, logging a failure instead of raising.

        Args:
            sid: The session id.
            channel_name: The channel being closed.
            session: The session being closed.
        """
        try:
            await session.channel.on_close(session)
        except Exception:
            logger.exception(
                f"Error closing channel {channel_name!r} for session {sid}."
            )

    async def _handle_channel_message(
        self, sid: str, channel_name: str, event: str, data: Any, buffers: list[bytes]
    ) -> None:
        """Dispatch one inbound channel frame.

        Never raises: a channel failing is a bug in that channel, not a reason
        to drop the app's connection.

        Args:
            sid: The session id.
            channel_name: The channel the frame is addressed to.
            event: The message name.
            data: The message metadata.
            buffers: The binary attachments.
        """
        try:
            if event == OPEN_MESSAGE:
                await self._open_channel_session(sid, channel_name)
                return
            sessions = self._channel_sessions.get(sid)
            session = sessions.get(channel_name) if sessions is not None else None
            if session is None:
                await self._send_channel_error(
                    sid,
                    channel_name,
                    "channel_not_open",
                    f"Channel {channel_name!r} is not open on this connection.",
                )
                return
            if event == CLOSE_MESSAGE:
                await self._close_channel_session(sid, channel_name)
                return
            if buffers and not session.channel.accepts_binary:
                await self._send_channel_error(
                    sid,
                    channel_name,
                    "binary_not_accepted",
                    f"Channel {channel_name!r} does not accept binary attachments.",
                )
                return
            await session.channel.on_message(session, event, data, buffers)
        except Exception:
            logger.exception(
                f"Error handling {event!r} on channel {channel_name!r} "
                f"for session {sid}."
            )

    async def _handle_binary_frame(
        self, sid: str, frame: bytes, max_size: int
    ) -> int | None:
        """Validate and dispatch one inbound binary channel frame.

        Args:
            sid: The session id.
            frame: The raw frame bytes.
            max_size: The message size limit in bytes.

        Returns:
            The websocket close code the session must end with, or None to
            keep serving it.
        """
        if len(frame) > max_size:
            logger.debug(f"Closing session {sid}: message over {max_size} bytes.")
            return 1009
        if otel.enabled:
            otel.record_message_size(len(frame), "receive")
        try:
            event, data, channel_name, buffers = decode_channel_frame(frame)
        except ValueError:
            # A Reflex client never sends malformed frames; close instead of
            # logging per frame.
            logger.debug(f"Closing session {sid}: malformed binary frame.")
            return 1002
        await self._handle_channel_message(sid, channel_name, event, data, buffers)
        return None

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
        if otel.enabled:
            otel.record_message_size(utf8_size(text), "receive")
        try:
            message = json.loads(text)
        except (json.JSONDecodeError, RecursionError):
            # Deeply nested JSON exhausts the decoder's stack rather than
            # failing to parse; both are just a malformed frame here.
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
        if len(message) > 2:
            if not isinstance(message[2], str):
                logger.debug(f"Closing session {sid}: malformed channel frame.")
                return 1002
            await self._handle_channel_message(sid, message[2], event, data, [])
            return None
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
                    {
                        "ping_interval": ping_interval,
                        "ping_timeout": ping_timeout,
                        "protocol": PROTOCOL_VERSION,
                        # So a client can refuse an oversized frame itself
                        # rather than lose the connection to one.
                        "max_message_size": max_message_size,
                    },
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
                if text is not None:
                    close_code = await self._handle_frame(
                        sid, text, websocket.scope, max_message_size
                    )
                elif (
                    frame := received.get("bytes")
                ) is not None and self.app._channels:
                    close_code = await self._handle_binary_frame(
                        sid, frame, max_message_size
                    )
                else:
                    # Binary frame with no channel to carry it.
                    logger.debug(f"Closing session {sid}: received a binary frame.")
                    close_code = 1003
                if close_code is not None:
                    await websocket.close(code=close_code)
                    break
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat_task.cancel()
            self._sockets.pop(sid, None)
            # Start the token cleanup before any teardown await: a cancelled
            # shutdown must not leave the token linked to a dead session.
            cleanup_task = self.handle_disconnect(sid)
            await self._close_channel_sessions(sid)
            if cleanup_task is not None:
                # Await the token cleanup so an immediate reconnect is not
                # treated as a duplicate tab; shielded so cancellation (e.g.
                # server shutdown) cannot abort it. Errors are logged by the
                # task's done callback.
                with contextlib.suppress(Exception):
                    await asyncio.shield(cleanup_task)
