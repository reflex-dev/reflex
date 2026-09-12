"""Multiplexed side channels on the Reflex event websocket.

A channel carries an application-defined message stream -- including binary
payloads -- over the connection that already delivers state deltas, so a
package needing its own data plane inherits the app's origin checks, client
token, reconnect handling and proxy configuration instead of reimplementing
them on a second socket.

Register a channel on the app and messages from the matching client-side
channel are dispatched to it::

    class Ticks(rx.channels.Channel):
        name = "ticks"

        async def on_message(self, session, event, data, buffers):
            if event == "subscribe":
                session.join(data["symbol"])

    app.register_channel(Ticks())
"""

from __future__ import annotations

import dataclasses
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar

# Channel names ride in every frame and name a client-side channel handle;
# keep them short and free of JSON or URL escaping.
_NAME_PATTERN = re.compile(r"[A-Za-z0-9_./:-]{1,64}")

# Maximum binary attachments one channel message may carry, in either
# direction. Bounds the work a single inbound frame can ask for.
MAX_MESSAGE_BUFFERS = 64

# Sends one channel message to a connected session: (sid, channel, event,
# data, buffers). Supplied by the transport when the session opens.
ChannelSender = Callable[[str, str, str, Any, Sequence[bytes]], Awaitable[None]]


def validate_channel_name(name: str) -> None:
    """Check a channel name against the wire format.

    Args:
        name: The channel name.

    Raises:
        ValueError: If the name is unusable on the wire.
    """
    if not _NAME_PATTERN.fullmatch(name):
        msg = (
            f"Invalid channel name {name!r}: expected 1-64 characters from "
            "[A-Za-z0-9_./:-]."
        )
        raise ValueError(msg)


@dataclasses.dataclass(eq=False, slots=True)
class ChannelSession:
    """One client connection's participation in a channel."""

    # The transport session id, shared with the app's event session.
    sid: str

    # The Reflex client token (tab) the connection authenticated with.
    client_token: str

    # The channel this session belongs to.
    channel: Channel

    # Per-connection scratch space owned by the channel implementation.
    data: dict[str, Any]

    _send: ChannelSender

    _rooms: set[str]

    async def send(
        self, event: str, data: Any = None, buffers: Sequence[bytes] = ()
    ) -> None:
        """Send one message to this client.

        Args:
            event: The message name.
            data: The JSON-serializable metadata.
            buffers: Binary attachments delivered alongside the metadata.
        """
        await self._send(self.sid, self.channel.name, event, data, buffers)

    def join(self, room: str) -> None:
        """Add this session to a room for fan-out.

        Args:
            room: The room name.
        """
        self._rooms.add(room)
        self.channel._rooms.setdefault(room, set()).add(self)

    def leave(self, room: str) -> None:
        """Remove this session from a room.

        Args:
            room: The room name.
        """
        self._rooms.discard(room)
        members = self.channel._rooms.get(room)
        if members is not None:
            members.discard(self)
            if not members:
                del self.channel._rooms[room]


class Channel(ABC):
    """A named message stream multiplexed onto the event websocket.

    Rooms and sessions are local to the worker holding the connection, which
    is what a socket-bound side channel can offer: a client reconnecting to
    another worker opens its session there. State that must outlive a
    connection belongs in Reflex state, not in the channel.
    """

    # The channel name, matching the name the client opens.
    name: ClassVar[str]

    # Whether inbound messages from this channel may carry binary
    # attachments. Off by default: a channel that never expects binary
    # should not accept the allocation.
    accepts_binary: ClassVar[bool] = False

    def __init__(self):
        """Initialize the channel's session and room bookkeeping."""
        validate_channel_name(type(self).name)
        # Sessions by client token, for token-addressed sends.
        self._sessions: dict[str, set[ChannelSession]] = {}
        # Room name to member sessions.
        self._rooms: dict[str, set[ChannelSession]] = {}

    async def on_open(self, session: ChannelSession) -> None:
        """Handle a client opening the channel.

        Args:
            session: The opening session.
        """
        return

    @abstractmethod
    async def on_message(
        self,
        session: ChannelSession,
        event: str,
        data: Any,
        buffers: list[bytes],
    ) -> None:
        """Handle one message from a client.

        Every field is client-controlled and unvalidated.

        Args:
            session: The sending session.
            event: The message name.
            data: The JSON metadata, as decoded from the frame.
            buffers: Binary attachments, empty unless ``accepts_binary``.
        """

    async def on_close(self, session: ChannelSession) -> None:
        """Handle a session going away.

        Args:
            session: The closing session.
        """
        return

    async def send_to_room(
        self,
        room: str,
        event: str,
        data: Any = None,
        buffers: Sequence[bytes] = (),
    ) -> None:
        """Send one message to every session in a room.

        Args:
            room: The room name.
            event: The message name.
            data: The JSON-serializable metadata.
            buffers: Binary attachments delivered alongside the metadata.
        """
        members = self._rooms.get(room)
        if not members:
            return
        # A send can close a session and mutate the room, so iterate a copy.
        for session in tuple(members):
            await session.send(event, data, buffers)

    async def send_to_token(
        self,
        client_token: str,
        event: str,
        data: Any = None,
        buffers: Sequence[bytes] = (),
    ) -> bool:
        """Send one message to every session of a client token on this worker.

        Args:
            client_token: The Reflex client token (tab).
            event: The message name.
            data: The JSON-serializable metadata.
            buffers: Binary attachments delivered alongside the metadata.

        Returns:
            Whether a session received the message.
        """
        sessions = self._sessions.get(client_token)
        if not sessions:
            return False
        for session in tuple(sessions):
            await session.send(event, data, buffers)
        return True

    def open_session(
        self, sid: str, client_token: str, send: ChannelSender
    ) -> ChannelSession:
        """Create and track a session for a connection. Called by the transport.

        Args:
            sid: The transport session id.
            client_token: The client token the connection authenticated with.
            send: The transport's send callable.

        Returns:
            The new session.
        """
        session = ChannelSession(
            sid=sid,
            client_token=client_token,
            channel=self,
            data={},
            _send=send,
            _rooms=set(),
        )
        self._sessions.setdefault(client_token, set()).add(session)
        return session

    def forget_session(self, session: ChannelSession) -> None:
        """Drop a session's rooms and tracking. Called by the transport.

        Args:
            session: The session going away.
        """
        for room in tuple(session._rooms):
            session.leave(room)
        sessions = self._sessions.get(session.client_token)
        if sessions is not None:
            sessions.discard(session)
            if not sessions:
                del self._sessions[session.client_token]
