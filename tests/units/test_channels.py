"""Tests for the channel API in reflex/channels.py."""

from typing import Any

import pytest

from reflex.channels import (
    MAX_MESSAGE_BUFFERS,
    RESERVED_EVENTS,
    Channel,
    ChannelSession,
    validate_channel_name,
)


class CollectingChannel(Channel):
    """A channel that records every message its transport was asked to send."""

    name = "probe"

    def __init__(self):
        """Initialize the channel and its recorded sends."""
        super().__init__()
        self.sent: list[tuple[str, str, str, Any, list[bytes]]] = []

    async def on_message(
        self, session: ChannelSession, event: str, data: Any, buffers: list[bytes]
    ) -> None:
        """Ignore inbound messages; these tests drive the channel directly."""
        return

    async def _record(
        self,
        sid: str,
        channel: str,
        event: str,
        data: Any,
        buffers: Any,
    ) -> None:
        """Stand in for the transport's send callable."""
        self.sent.append((sid, channel, event, data, list(buffers)))

    def session(self, sid: str, client_token: str = "tok") -> ChannelSession:
        """Open a session wired to the recording sender.

        Args:
            sid: The session id.
            client_token: The client token.

        Returns:
            The open session.
        """
        return self.open_session(sid, client_token, self._record)


@pytest.mark.parametrize("name", ["xy", "_xy", "/_xy", "a.b-c:d/e", "x" * 64])
def test_valid_channel_names(name: str):
    """Names usable on the wire pass validation."""
    validate_channel_name(name)


@pytest.mark.parametrize("name", ["", "x" * 65, "has space", 'quote"', "new\nline"])
def test_invalid_channel_names(name: str):
    """Names that would need escaping on the wire are rejected."""
    with pytest.raises(ValueError, match="Invalid channel name"):
        validate_channel_name(name)


def test_channel_rejects_an_unusable_name():
    """A channel declaring an unusable name fails at construction."""

    class BadChannel(CollectingChannel):
        name = "not a name"

    with pytest.raises(ValueError, match="Invalid channel name"):
        BadChannel()


@pytest.mark.asyncio
async def test_session_send_reaches_the_transport():
    """A session's send is handed to the transport with its channel name."""
    channel = CollectingChannel()
    session = channel.session("sid1")

    await session.send("payload", {"fig": "f1"}, [b"\x00"])

    assert channel.sent == [("sid1", "probe", "payload", {"fig": "f1"}, [b"\x00"])]


@pytest.mark.asyncio
async def test_room_fan_out_reaches_members_only():
    """Sending to a room reaches its members and no one else."""
    channel = CollectingChannel()
    first = channel.session("sid1")
    second = channel.session("sid2")
    channel.session("sid3")
    first.join("fig:1")
    second.join("fig:1")

    await channel.send_to_room("fig:1", "push", {"n": 1})

    assert sorted(sent[0] for sent in channel.sent) == ["sid1", "sid2"]


@pytest.mark.asyncio
async def test_leaving_a_room_stops_delivery():
    """A session that left a room no longer receives its messages."""
    channel = CollectingChannel()
    session = channel.session("sid1")
    session.join("fig:1")
    session.leave("fig:1")

    await channel.send_to_room("fig:1", "push")

    assert channel.sent == []
    # The empty room is not kept around.
    assert channel._rooms == {}


@pytest.mark.asyncio
async def test_sending_to_an_unknown_room_is_a_noop():
    """Fan-out to a room nobody joined does nothing."""
    channel = CollectingChannel()

    await channel.send_to_room("fig:missing", "push")

    assert channel.sent == []


@pytest.mark.asyncio
async def test_send_to_token_reports_delivery():
    """Token-addressed sends reach that client's sessions, and report misses."""
    channel = CollectingChannel()
    channel.session("sid1", client_token="tok1")
    channel.session("sid2", client_token="tok2")

    assert await channel.send_to_token("tok1", "push", {"n": 1}) is True
    assert await channel.send_to_token("missing", "push") is False
    assert [sent[0] for sent in channel.sent] == ["sid1"]


@pytest.mark.asyncio
async def test_forgetting_a_session_clears_rooms_and_tokens():
    """A forgotten session leaves no room membership or token entry behind."""
    channel = CollectingChannel()
    session = channel.session("sid1", client_token="tok1")
    session.join("fig:1")

    channel.forget_session(session)

    assert channel._rooms == {}
    assert channel._sessions == {}
    assert await channel.send_to_token("tok1", "push") is False
    await channel.send_to_room("fig:1", "push")
    assert channel.sent == []


def test_sessions_of_one_token_are_tracked_together():
    """Two tabs sharing a token both stay reachable until each is forgotten."""
    channel = CollectingChannel()
    first = channel.session("sid1", client_token="tok1")
    second = channel.session("sid2", client_token="tok1")

    channel.forget_session(first)

    assert channel._sessions == {"tok1": {second}}


def test_forgotten_session_reports_itself_closed():
    """A session whose client went away reports it, for handlers mid-await."""
    channel = CollectingChannel()
    session = channel.session("sid1")
    assert session.open is True

    channel.forget_session(session)

    assert session.open is False


@pytest.mark.asyncio
async def test_send_rejects_more_attachments_than_a_frame_holds():
    """An oversized message raises instead of building an unsendable frame."""
    channel = CollectingChannel()
    session = channel.session("sid1")
    buffers = [b"\x00"] * (MAX_MESSAGE_BUFFERS + 1)

    with pytest.raises(ValueError, match="attachments"):
        await session.send("push", None, buffers)

    assert channel.sent == []


@pytest.mark.asyncio
async def test_room_fan_out_rejects_oversized_messages_before_delivering():
    """A fan-out that cannot be framed reaches nobody, rather than some."""
    channel = CollectingChannel()
    channel.session("sid1").join("all")
    channel.session("sid2").join("all")

    with pytest.raises(ValueError, match="attachments"):
        await channel.send_to_room(
            "all", "push", None, [b""] * (MAX_MESSAGE_BUFFERS + 1)
        )

    assert channel.sent == []


@pytest.mark.asyncio
async def test_send_accepts_the_full_attachment_budget():
    """The limit is inclusive, so a channel can use all of it."""
    channel = CollectingChannel()
    session = channel.session("sid1")

    await session.send("push", None, [b""] * MAX_MESSAGE_BUFFERS)

    assert len(channel.sent) == 1


@pytest.mark.parametrize("name", [42, b"bytes", None])
def test_channel_with_an_unusable_name_reports_it(name: Any):
    """A non-string name fails with the explicit error, not a TypeError."""

    class BadChannel(CollectingChannel):
        pass

    BadChannel.name = name  # pyright: ignore[reportAttributeAccessIssue]

    with pytest.raises(ValueError, match="Invalid channel name"):
        BadChannel()


def test_channel_without_a_name_reports_it():
    """A channel that never declared a name fails the same way."""

    class NamelessChannel(Channel):
        async def on_message(
            self, session: ChannelSession, event: str, data: Any, buffers: list[bytes]
        ) -> None:
            """Ignore inbound messages."""
            return

    with pytest.raises(ValueError, match="Invalid channel name"):
        NamelessChannel()


@pytest.mark.asyncio
@pytest.mark.parametrize("event", sorted(RESERVED_EVENTS))
async def test_send_rejects_reserved_message_names(event: str):
    """A message may not impersonate the client handle's lifecycle events."""
    channel = CollectingChannel()
    session = channel.session("sid1")

    with pytest.raises(ValueError, match="reserved"):
        await session.send(event, {"anything": True})

    assert channel.sent == []
