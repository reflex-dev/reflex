"""Event namespaces bridging client sessions to the Reflex event loop."""

from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import json
import logging
import time
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

from reflex_base import constants, otel
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.event import _EVENT_FIELDS, Event
from starlette.websockets import WebSocket, WebSocketDisconnect
from typing_extensions import Buffer

from reflex.channels import MAX_MESSAGE_BUFFERS, ChannelSession, is_reserved_event
from reflex.istate.data import SessionData
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
CONNECT_MESSAGE = "_connect"
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

# Application-level socket event names, resolved once for the hot paths.
_EVENT = str(constants.SocketEvent.EVENT)
_PING = str(constants.SocketEvent.PING)
_CLIENT_ERROR = str(constants.SocketEvent.CLIENT_ERROR)

# Frames carry no separator whitespace: it is pure overhead on the wire.
_COMPACT = (",", ":")

# The heartbeat frame is static; serialize it once.
_PING_FRAME = json.dumps([PING_MESSAGE], separators=_COMPACT)

# ASGI scope key holding the connection-scoped router_data.
_STATIC_ROUTER_DATA = "_reflex_static_router_data"


def _decode_asgi_headers(headers: Iterable[tuple[bytes, bytes]]) -> dict[str, str]:
    """Decode raw ASGI scope header pairs into a str-keyed dict.

    Args:
        headers: Raw (name, value) byte pairs from the ASGI scope.

    Returns:
        A dict mapping decoded header names to decoded values.
    """
    return {k.decode("utf-8"): v.decode("utf-8") for (k, v) in headers}


def build_static_router_data(sid: str, asgi_scope: Mapping[str, Any]) -> dict[str, Any]:
    """Build the router_data entries that are constant for a connection.

    Args:
        sid: The session id.
        asgi_scope: The ASGI scope of the client connection.

    Returns:
        The connection-scoped router_data entries.
    """
    headers = _decode_asgi_headers(asgi_scope["headers"])

    # Get the client IP.
    if client := asgi_scope.get("client"):
        client_ip = client[0]
        headers["asgi-scope-client"] = client_ip
    else:
        client_ip = "0.0.0.0"

    # Unroll reverse proxy forwarded headers.
    client_ip = headers.get("x-forwarded-for", client_ip).partition(",")[0].strip()
    return {
        constants.RouteVar.SESSION_ID: sid,
        constants.RouteVar.HEADERS: headers,
        constants.RouteVar.CLIENT_IP: client_ip,
    }


def connect_boot_event(auth: Any) -> Any:
    """Get the boot event a session's connect carries.

    The frontend sends its hydrate event with the connect, so the backend
    processes it without waiting for the connect acknowledgement round trip.

    Args:
        auth: The connect payload.

    Returns:
        The boot event, or None if the connect carries none.
    """
    return (
        auth.get(constants.CompileVars.CONNECT_AUTH_EVENT)
        if isinstance(auth, dict)
        else None
    )


def _dumps(obj: Any) -> str:
    """Serialize a frame compactly, as text that is valid UTF-8.

    Args:
        obj: The frame to serialize.

    Returns:
        The JSON text.
    """
    text = format.json_dumps(obj, separators=_COMPACT)
    if not text.isascii():
        try:
            text.encode()
        except UnicodeEncodeError:
            # An unpaired surrogate (a non-UTF-8 file name decodes to one)
            # cannot travel as text; escape it, as ensure_ascii would.
            return text.encode(errors="backslashreplace").decode()
    return text


def _parse_frame(text: str) -> Any:
    """Parse a text frame.

    Args:
        text: The raw frame text.

    Returns:
        The decoded JSON, or None if the text is not JSON.
    """
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        # Besides a JSONDecodeError, the decoder raises a plain ValueError for
        # an integer past the digit limit and exhausts its stack on deeply
        # nested JSON; all are just a malformed frame here.
        return None


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


def exceeds_message_limit(data: str | bytes, max_size: int) -> bool:
    """Whether a received message is over the policy limit.

    The limit counts UTF-8 bytes, and UTF-8 encodes 1-4 bytes per character:
    more characters than the limit is certainly over, a quarter or fewer
    certainly under, so only the range between is measured exactly -- and an
    ASCII payload, which is most of them, is measured without a copy. Mirrors
    ``exceedsMessageLimit`` in .templates/web/utils/helpers/websocket.js.

    Args:
        data: The received message, text or binary.
        max_size: The limit in bytes.

    Returns:
        Whether the message exceeds it.
    """
    if isinstance(data, bytes):
        return len(data) > max_size
    length = len(data)
    return length > max_size or (length * 4 > max_size and utf8_size(data) > max_size)


def encode_channel_frame(
    event: str, data: Any, channel: str, buffers: Sequence[Buffer]
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
    # In bytes: len() counts items, which is not the size of a typed array.
    sizes = [memoryview(buffer).nbytes for buffer in buffers]
    header = _dumps([event, data, channel, sizes]).encode()
    parts: list[Buffer] = [len(header).to_bytes(4, "little"), header]
    offset = 4 + len(header)
    for buffer, size in zip(buffers, sizes, strict=True):
        padding = -offset % _FRAME_ALIGNMENT
        if padding:
            parts.append(bytes(padding))
        parts.append(buffer)
        offset += padding + size
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
    if 4 + header_size > len(frame):
        # The frame is the only bound the header needs: the transport rejects
        # one over the size limit before decoding it.
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


# Size of the frames one connection may have waiting behind the one being
# written. Past it the client has stopped reading, and is dropped: it would
# otherwise buffer without bound until its heartbeat times out.
_MAX_SEND_BACKLOG = 16 * 1024 * 1024


class _Connection:
    """One client websocket, as the transport sends to and closes it.

    Sending only queues a frame for the connection's own writer task, so a
    client that stops reading cannot stall the coroutines emitting to it.
    Closing ends the session's receive loop, which closes the socket itself:
    a server may not complete a close sent while a receive is pending on it.
    """

    def __init__(self, websocket: WebSocket):
        """Start the connection's writer.

        Args:
            websocket: The client websocket connection.
        """
        self.websocket = websocket
        # When a frame last arrived, for the heartbeat's liveness check.
        self.last_received = time.monotonic()
        # The code to close with, once the connection is ending.
        self.close_code: int | None = None
        self._frames: collections.deque[str | bytes] = collections.deque()
        # Size of the frames waiting behind the one being written.
        self._backlog = 0
        self._ready = asyncio.Event()
        self._lifetime: asyncio.Timeout | None = None
        self._writer = asyncio.create_task(self._write())

    def send(self, frame: str | bytes) -> None:
        """Queue a frame for the client, closing a connection that stopped reading.

        Args:
            frame: The serialized text or binary frame.
        """
        if self.close_code is not None:
            return
        frames = self._frames
        frames.append(frame)
        self._backlog += len(frame)
        # One frame may exceed the bound; frames piling up behind it may not.
        if self._backlog > _MAX_SEND_BACKLOG and len(frames) > 1:
            logger.debug("Closing a session whose client stopped reading.")
            self.close(1008)
            return
        self._ready.set()

    async def _write(self) -> None:
        """Write the queued frames in order until the connection ends."""
        websocket = self.websocket
        frames = self._frames
        try:
            while True:
                await self._ready.wait()
                self._ready.clear()
                while frames:
                    frame = frames.popleft()
                    self._backlog -= len(frame)
                    if isinstance(frame, str):
                        await websocket.send_text(frame)
                    else:
                        await websocket.send_bytes(frame)
        except Exception:
            # The connection went away mid-write; its receive loop cleans up.
            logger.debug("Failed to write to a client websocket.", exc_info=True)

    def attach(self, lifetime: asyncio.Timeout) -> None:
        """Let close() end the receive loop running under a lifetime.

        Args:
            lifetime: The timeout the session's receive loop runs under.
        """
        self._lifetime = lifetime
        if self.close_code is not None:
            lifetime.reschedule(0)

    def close(self, code: int) -> None:
        """End the session with a close code, dropping further sends.

        Args:
            code: The websocket close code.
        """
        if self.close_code is not None:
            return
        self.close_code = code
        lifetime = self._lifetime
        if lifetime is not None and not lifetime.expired():
            # Fires at the receive loop's next await, which ends it.
            lifetime.reschedule(0)

    def stop(self) -> None:
        """Stop writing, dropping the frames not written yet."""
        self._lifetime = None
        self._writer.cancel()


@dataclasses.dataclass
class _ErrorBudget:
    """Bounds error-level logging driven by one kind of client traffic.

    Per session, because one client must not fill the log; and per time
    window, because per-session budgets reset on reconnect and so do not stop
    scripted reconnect loops.
    """

    # What the budget covers, for the message that announces suppression.
    label: str

    max_per_session: int
    max_per_window: int
    window_seconds: float

    counts: dict[str, int] = dataclasses.field(default_factory=dict)
    window_start: float = 0.0
    window_count: int = 0

    def allows(self, sid: str) -> bool:
        """Whether another record for this session fits the budget.

        Args:
            sid: The session id.

        Returns:
            Whether the record may be written.
        """
        session_count = self.counts.get(sid, 0)
        if session_count >= self.max_per_session:
            return False
        now = time.monotonic()
        if now - self.window_start > self.window_seconds:
            self.window_start = now
            self.window_count = 0
        if self.window_count >= self.max_per_window:
            if self.window_count == self.max_per_window:
                # Warn once per window so suppression is visible in the logs
                # and a flooding client cannot silently starve reports from
                # other sessions.
                self.window_count += 1
                logger.warning(
                    f"More than {self.max_per_window} {self.label} in "
                    f"{self.window_seconds:.0f}s; suppressing further reports "
                    "for this window."
                )
            return False
        self.window_count += 1
        self.counts[sid] = session_count + 1
        return True

    def forget(self, sid: str) -> None:
        """Drop a disconnected session's counter.

        Args:
            sid: The session id.
        """
        self.counts.pop(sid, None)


class BaseEventNamespace(ABC):
    """Transport-agnostic handler for client event sessions."""

    # The application object.
    app: App

    # Maximum error-level log entries a single session may produce, per kind
    # of client-triggered error, before further ones from it are dropped.
    _MAX_CLIENT_ERRORS_PER_SID = 5

    # Process-wide bound on those entries per time window; per-SID budgets
    # alone reset on reconnect, so scripted reconnects could otherwise flood
    # the logs.
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

        # Client-reported errors and server-side handler failures are both
        # driven by client traffic, but a client chooses how many reports it
        # sends while a handler traceback means a real bug, so one cannot be
        # allowed to suppress the other.
        self._client_error_budget = self._error_budget("client_error reports")
        self._handler_error_budget = self._error_budget("handler errors")

    @classmethod
    def _error_budget(cls, label: str) -> _ErrorBudget:
        """Build a budget for one kind of client-triggered error logging.

        Args:
            label: What the budget covers, for the suppression message.

        Returns:
            The budget.
        """
        return _ErrorBudget(
            label=label,
            max_per_session=cls._MAX_CLIENT_ERRORS_PER_SID,
            max_per_window=cls._MAX_CLIENT_ERRORS_PER_WINDOW,
            window_seconds=cls._CLIENT_ERROR_WINDOW_SECONDS,
        )

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
        """Emit an event to a connected client session, or to all of them.

        Args:
            event: The event name.
            data: The event payload.
            to: The session id to emit to; every connected session if None.
        """

    async def handle_connect(
        self,
        sid: str,
        query_string: str,
        subprotocol: str | None,
        *,
        update_state: bool = True,
    ) -> None:
        """Handle a new client session connecting.

        Args:
            sid: The session id.
            query_string: The raw query string of the connection request.
            subprotocol: The websocket subprotocol offered by the client.
            update_state: Whether to record the new sid and token on the state;
                see link_token_to_sid.
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
        await self.link_token_to_sid(sid, token_list[0], update_state=update_state)
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
        self._client_error_budget.forget(sid)
        self._handler_error_budget.forget(sid)
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
            # The mapping is dropped when a token moves to another socket or
            # its record goes stale, so a live connection can reach this and
            # keep sending. Log it per frame at debug, without the
            # client-controlled payload: at warning level it would be a log
            # flood and an injection vector both.
            logger.debug(f"Ignoring event from session {sid} with no linked token.")
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

        # Headers, client IP, and session id cannot change for the lifetime of
        # the connection; derive them once and cache them on its ASGI scope,
        # which is per-connection state, instead of on every event.
        static_router_data = asgi_scope.get(_STATIC_ROUTER_DATA)
        if static_router_data is None:
            static_router_data = asgi_scope[_STATIC_ROUTER_DATA] = (
                build_static_router_data(sid, asgi_scope)
            )

        router_data = event.router_data
        try:
            router_data.update(static_router_data)
            # The cached headers reach the event, and from there
            # `state.router_data`, a plain mutable dict: sharing the mapping
            # would let a handler mutating `self.router_data["headers"]`
            # corrupt the connection cache for every later event on this
            # socket. The shallow copy is far cheaper than the per-event
            # header decode it replaced, so the cache still pays off.
            router_data[constants.RouteVar.HEADERS] = static_router_data[
                constants.RouteVar.HEADERS
            ].copy()
            # The nested values are still client-controlled.
            router_data.update({
                constants.RouteVar.QUERY: format.format_query_params(event.router_data),
                constants.RouteVar.CLIENT_TOKEN: token,
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

    def _log_handler_failure(
        self, sid: str, message: str, error: BaseException
    ) -> None:
        """Report a handler that raised, within the session's error budget.

        A client can keep sending whatever made the handler raise, so the
        traceback is budgeted like any other client-triggered error.

        Args:
            sid: The session id.
            message: What failed.
            error: The exception to attach.
        """
        if self._handler_error_budget.allows(sid):
            logger.error(message, exc_info=error)
        else:
            logger.debug(f"Suppressed a repeated handler error for session {sid}.")

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

        if not self._client_error_budget.allows(sid):
            return

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

    async def link_token_to_sid(
        self, sid: str, token: str, *, update_state: bool = True
    ):
        """Link a token to a session id.

        Args:
            sid: The session id.
            token: The client token.
            update_state: Whether to record the new sid and token on the state
                now. A connect that carries the boot event skips it: processed
                as the session's first event, that records them without an
                extra load and save of the whole state tree.
        """
        # Use TokenManager for duplicate detection and Redis support
        new_token = await self._token_manager.link_token_to_sid(token, sid)

        if new_token:
            # Duplicate detected, emit new token to client
            await self.emit("new_token", new_token, to=sid)

        # Update client state to apply new sid/token for running background tasks.
        if update_state and self.app._state is not None:
            async with self.app.state_manager.modify_state(
                BaseStateToken(ident=new_token or token, cls=self.app._state)
            ) as state:
                state.router_data[constants.RouteVar.SESSION_ID] = sid
                # Record the identity the state was loaded under; duplicate-token
                # handling can hand back a fresh one here.
                state.router_data[constants.RouteVar.CLIENT_TOKEN] = new_token or token
                # Rebuild from router_data to keep the session var in step with it.
                if (
                    session := SessionData.from_router_data(state.router_data)
                ) != state.rx_router_session:
                    state.rx_router_session = session


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
        self._connections: dict[str, _Connection] = {}
        # Open channel sessions per connection, by session id and channel name.
        self._channel_sessions: dict[str, dict[str, ChannelSession]] = {}

    def _deliver(self, to: str | None, payload: str | bytes, label: str) -> None:
        """Queue one serialized frame for a connected client session.

        Args:
            to: The session id to send to.
            payload: The serialized text or binary frame.
            label: The message name, for diagnostics.
        """
        connection = self._connections.get(to) if to is not None else None
        if connection is None:
            # Routine race: the client disconnected while an event was still
            # being processed, so its remaining updates have nowhere to go.
            logger.debug(f"Attempted to emit {label!r} to unknown session {to!r}.")
            return
        if otel.enabled:
            otel.record_message_size(utf8_size(payload), "transmit")
        connection.send(payload)

    async def emit(self, event: str, data: Any = None, to: str | None = None) -> None:
        """Emit an event to a connected client session, or to all of them.

        Args:
            event: The event name.
            data: The event payload.
            to: The session id to emit to; every connected session if None.
        """
        payload = _dumps([event, data])
        if to is not None:
            self._deliver(to, payload, event)
            return
        # Like Socket.IO's emit without a recipient: a broadcast.
        for sid in self._connections:
            self._deliver(sid, payload, event)

    async def _send_channel_message(
        self,
        sids: Sequence[str],
        channel: str,
        event: str,
        data: Any,
        buffers: Sequence[Buffer],
    ) -> None:
        """Send one channel message to connected client sessions.

        The frame is serialized once for every recipient: a room broadcast
        costs one encode and one buffer, not one per member.

        Args:
            sids: The session ids to send to.
            channel: The channel name.
            event: The message name.
            data: The JSON-serializable metadata.
            buffers: The binary attachments.
        """
        payload = (
            encode_channel_frame(event, data, channel, buffers)
            if buffers
            else _dumps([event, data, channel])
        )
        for sid in sids:
            self._deliver(sid, payload, event)

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
            (sid,),
            channel,
            CHANNEL_ERROR_MESSAGE,
            {"code": code, "message": message},
            (),
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
                (sid,), channel_name, OPENED_MESSAGE, None, ()
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
        except Exception as exc:
            self._drop_channel_session(sid, channel_name)
            self._log_handler_failure(
                sid, f"Error opening channel {channel_name!r} for session {sid}.", exc
            )
            await self._send_channel_error(
                sid, channel_name, "open_failed", "The channel failed to open."
            )
            return
        await self._send_channel_message((sid,), channel_name, OPENED_MESSAGE, None, ())

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

    async def _notify_channel_close(
        self, sid: str, channel_name: str, session: ChannelSession
    ) -> None:
        """Run a channel's close hook, logging a failure instead of raising.

        Args:
            sid: The session id.
            channel_name: The channel being closed.
            session: The session being closed.
        """
        try:
            await session.channel.on_close(session)
        except Exception as exc:
            self._log_handler_failure(
                sid, f"Error closing channel {channel_name!r} for session {sid}.", exc
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
            if is_reserved_event(event):
                # The reservation holds in both directions, so a handler that
                # relays what it receives cannot be made to attempt a send the
                # channel API refuses.
                await self._send_channel_error(
                    sid,
                    channel_name,
                    "reserved_event",
                    f"Channel message name {event!r} is reserved.",
                )
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
        except Exception as exc:
            self._log_handler_failure(
                sid,
                f"Error handling {event!r} on channel {channel_name!r} "
                f"for session {sid}.",
                exc,
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
        if (close_code := self._accept_inbound(sid, frame, max_size)) is not None:
            return close_code
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
    async def _close_quietly(websocket: WebSocket, code: int) -> None:
        """Close a connection, tolerating one that is already closed.

        The client can close its side while the server decides to close, and
        starlette refuses a close after the connection has ended.

        Args:
            websocket: The client websocket connection.
            code: The close code.
        """
        try:
            await websocket.close(code=code)
        except RuntimeError:
            logger.debug("Connection was already closed.", exc_info=True)

    @staticmethod
    def _accept_inbound(sid: str, payload: str | bytes, max_size: int) -> int | None:
        """Apply the message size policy to a received frame, and account for it.

        ASGI delivers complete messages, so the server has already buffered
        the frame; its protocol-level caps (enforced during frame reassembly)
        bound that allocation. This applies the Reflex policy limit on top.

        Args:
            sid: The session id.
            payload: The received frame, text or binary.
            max_size: The message size limit in bytes.

        Returns:
            The close code the session must end with, or None to dispatch it.
        """
        if exceeds_message_limit(payload, max_size):
            logger.debug(f"Closing session {sid}: message over {max_size} bytes.")
            return 1009
        if otel.enabled:
            otel.record_message_size(utf8_size(payload), "receive")
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
        if (close_code := self._accept_inbound(sid, text, max_size)) is not None:
            return close_code
        message = _parse_frame(text)
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
        except Exception as exc:
            # A failing handler is a server-side bug: log it loudly; the
            # connection survives.
            self._log_handler_failure(
                sid, f"Error handling socket event {event!r} for session {sid}.", exc
            )
        return None

    async def _receive_connect(
        self, sid: str, websocket: WebSocket, timeout: float, max_size: int
    ) -> list[Any] | None:
        """Read the frame that opens a session, closing the socket on anything else.

        Args:
            sid: The session id.
            websocket: The client websocket connection.
            timeout: Seconds to wait for the frame.
            max_size: The message size limit in bytes.

        Returns:
            The connect frame, or None once the socket is closed.
        """
        try:
            received = await asyncio.wait_for(websocket.receive(), timeout)
        except TimeoutError:
            logger.debug(f"Closing session {sid}: no connect frame.")
            await self._close_quietly(websocket, 1008)
            return None
        if received["type"] == "websocket.disconnect":
            return None
        if (text := received.get("text")) is not None:
            if (close_code := self._accept_inbound(sid, text, max_size)) is not None:
                await self._close_quietly(websocket, close_code)
                return None
            message = _parse_frame(text)
            if isinstance(message, list) and message and message[0] == CONNECT_MESSAGE:
                return message
        # A Reflex client opens every session with a connect frame.
        logger.debug(f"Closing session {sid}: expected a connect frame.")
        await self._close_quietly(websocket, 1002)
        return None

    async def _handle_boot_event(
        self, sid: str, boot_event: Any, scope: MutableMapping[str, Any]
    ) -> int | None:
        """Dispatch the boot event of a connect frame as the session's first event.

        Args:
            sid: The session id.
            boot_event: The boot event.
            scope: The ASGI scope of the client connection.

        Returns:
            The websocket close code the session must end with, or None to
            keep serving it.
        """
        try:
            await self.handle_event(sid, boot_event, scope)
        except exceptions.EventDeserializationError:
            logger.debug(f"Closing session {sid}: undeserializable boot event.")
            return 1002
        except Exception as exc:
            self._log_handler_failure(
                sid, f"Error handling the boot event for session {sid}.", exc
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
        if b"EIO" in urllib.parse.parse_qs(websocket.scope.get("query_string", b"")):
            # A Socket.IO client -- a tab or bundle from before this transport
            # -- cannot speak it; refuse it at once rather than leave it
            # waiting for an engine.io handshake.
            await websocket.close(code=1008)
            return
        subprotocols = websocket.scope.get("subprotocols") or []
        # Echo the client's offered subprotocol (the Reflex version); browsers
        # abort the connection if the server selects none.
        await websocket.accept(subprotocol=subprotocols[0] if subprotocols else None)

        sid = str(uuid.uuid4())
        ping_interval = environment.REFLEX_SOCKET_INTERVAL.get().total_seconds()
        ping_timeout = environment.REFLEX_SOCKET_TIMEOUT.get().total_seconds()
        max_message_size = environment.REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE.get()
        # The client sends its connect frame on open, without waiting for the
        # handshake, so the boot event it carries saves that round trip. A
        # socket that never sends one ends within the heartbeat window.
        connect_frame = await self._receive_connect(
            sid, websocket, ping_interval + ping_timeout, max_message_size
        )
        if connect_frame is None:
            return
        boot_event = connect_boot_event(
            connect_frame[1] if len(connect_frame) > 1 else None
        )
        connection = _Connection(websocket)
        self._connections[sid] = connection
        heartbeat_task = asyncio.create_task(
            self._heartbeat(connection, ping_interval, ping_timeout),
            name=f"reflex_heartbeat|{sid}",
        )
        lifetime = asyncio.timeout(None)
        try:
            async with lifetime:
                connection.attach(lifetime)
                await self._serve_session(
                    sid,
                    connection,
                    boot_event,
                    subprotocols[0] if subprotocols else None,
                    ping_interval,
                    ping_timeout,
                    max_message_size,
                )
        except TimeoutError:
            # The lifetime firing is how connection.close() ends the loop.
            if not lifetime.expired():
                raise
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat_task.cancel()
            connection.stop()
            self._connections.pop(sid, None)
            # Start the token cleanup before any teardown await: a cancelled
            # shutdown must not leave the token linked to a dead session.
            cleanup_task = self.handle_disconnect(sid)
            await self._close_channel_sessions(sid)
            # A close hook that raised logged through the handler budget,
            # which recreated the counter handle_disconnect had just dropped.
            self._handler_error_budget.forget(sid)
            if cleanup_task is not None:
                # Await the token cleanup so the client's reconnect after the
                # close is not treated as a duplicate tab; shielded so
                # cancellation (e.g. server shutdown) cannot abort it. Errors
                # are logged by the task's done callback.
                with contextlib.suppress(Exception):
                    await asyncio.shield(cleanup_task)
            if connection.close_code is not None:
                await self._close_quietly(websocket, connection.close_code)

    @staticmethod
    async def _heartbeat(
        connection: _Connection, ping_interval: float, ping_timeout: float
    ) -> None:
        """Ping a session's client, closing the session once it stops answering.

        Args:
            connection: The client connection.
            ping_interval: Seconds between pings.
            ping_timeout: Seconds past the interval a client may stay silent.
        """
        while True:
            await asyncio.sleep(ping_interval)
            if (
                time.monotonic() - connection.last_received
                > ping_interval + ping_timeout
            ):
                connection.close(1001)
                return
            connection.send(_PING_FRAME)

    async def _serve_session(
        self,
        sid: str,
        connection: _Connection,
        boot_event: Any,
        subprotocol: str | None,
        ping_interval: float,
        ping_timeout: float,
        max_message_size: int,
    ) -> None:
        """Open a session and dispatch its frames until it ends.

        Args:
            sid: The session id.
            connection: The client connection.
            boot_event: The boot event its connect frame carried, if any.
            subprotocol: The websocket subprotocol offered by the client.
            ping_interval: Seconds between heartbeat pings.
            ping_timeout: Seconds past the interval a client may stay silent.
            max_message_size: The message size limit in bytes.
        """
        websocket = connection.websocket
        await self.handle_connect(
            sid,
            websocket.scope.get("query_string", b"").decode(),
            subprotocol,
            update_state=boot_event is None,
        )
        if sid not in self._token_manager.sid_to_token:
            # No token was linked; not a Reflex client.
            connection.close(1008)
            return
        # The handshake acknowledges the connect and carries the heartbeat
        # settings for the client's connection watchdog.
        connection.send(
            _dumps([
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
        if (
            boot_event is not None
            and (
                close_code := await self._handle_boot_event(
                    sid, boot_event, websocket.scope
                )
            )
            is not None
        ):
            connection.close(close_code)
            return
        while connection.close_code is None:
            received = await websocket.receive()
            if received["type"] == "websocket.disconnect":
                return
            connection.last_received = time.monotonic()
            if sid not in self._token_manager.sid_to_token:
                # The token moved to another socket or its record went stale.
                # Nothing this session sends can be served -- not events, not
                # channel messages, which would otherwise keep invoking
                # handlers under a token that has moved on -- and a reconnect
                # is how it gets a working session back.
                logger.debug(f"Closing session {sid}: its token is gone.")
                connection.close(1008)
                return
            text = received.get("text")
            if text is not None:
                close_code = await self._handle_frame(
                    sid, text, websocket.scope, max_message_size
                )
            elif (frame := received.get("bytes")) is not None and self.app._channels:
                close_code = await self._handle_binary_frame(
                    sid, frame, max_message_size
                )
            else:
                # Binary frame with no channel to carry it.
                logger.debug(f"Closing session {sid}: received a binary frame.")
                close_code = 1003
            if close_code is not None:
                connection.close(close_code)
