"""Tests for reflex_bench.drivers.events.

The generator runs against :class:`~reflex_bench.drivers.echo_server.EchoServer`
on a thread of the test process, on the plain protocol unless a test names
Socket.IO; subclasses script delays, dropped and reordered answers, a new token,
a missing hydration, a disconnect and a stall. Most tests drive the sessions on
the calling thread, as one generator process does; the multi-process ones go
through :class:`~reflex_bench.drivers.events.LoadRunner`.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import multiprocessing
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any, cast

import pytest
from reflex_bench.drivers import events
from reflex_bench.drivers.app_process import free_ports
from reflex_bench.drivers.echo_server import EchoServer
from reflex_bench.drivers.events import (
    CODECS,
    Endpoint,
    EventShape,
    GeneratorSaturated,
    LinkEvent,
    LoadError,
    LoadPlan,
    LoadResult,
    LoadRunner,
    WireProtocol,
    open_sessions,
    run_load,
)
from websockets.asyncio.server import ServerConnection

from tests.units.reflex_bench.factories import make_load_result

STATE = "reflex___state____state.playground___state____bench_state"
SEQ_VAR = "last_seq_rx_state_"
SHAPE = EventShape(
    name=f"{STATE}.set_seq",
    payload=events.seq_payload,
    delta_key=STATE,
    seq_var=SEQ_VAR,
)
WEBSOCKET = CODECS["websocket"]
SOCKETIO = CODECS["socketio"]
PROTOCOLS = pytest.mark.parametrize("protocol", ["websocket", "socketio"])
# The hydration events of a session, by protocol.
HYDRATION = {
    "websocket": [events.HYDRATE_AND_LOAD_EVENT],
    "socketio": [events.HYDRATE_EVENT, events.ON_LOAD_EVENT],
}
# The events whose answer sets is_hydrated.
HYDRATING = {events.ON_LOAD_EVENT, events.HYDRATE_AND_LOAD_EVENT}
# Captured from the playground: HEAD leaves empty fields out, 0.8.23 does not.
HEAD_REPLY = f'["event",{{"delta":{{"{STATE}":{{"{SEQ_VAR}":7}}}}}}]'
SOCKETIO_REPLY = f'42/_event,["event",{{"delta":{{"{STATE}":{{"{SEQ_VAR}":7}}}}}}]'
OLD_REPLY = (
    f'42/_event,["event",{{"delta":{{"{STATE}":{{"{SEQ_VAR}":7}}}},'
    '"events":[],"final":true}]'
)


@contextlib.contextmanager
def serving(server: EchoServer) -> Iterator[str]:
    """Run an echo server on a thread with its own event loop.

    Args:
        server: The server.

    Yields:
        Its base URL, like the backend URL of a started app.
    """
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    port: list[int] = []
    done: list[asyncio.Future[None]] = []

    async def main() -> None:
        done.append(loop.create_future())
        async with server.serve("127.0.0.1", 0) as bound:
            port.append(bound)
            ready.set()
            await done[0]

    thread = threading.Thread(target=loop.run_until_complete, args=(main(),))
    thread.start()
    assert ready.wait(10)
    try:
        yield f"http://127.0.0.1:{port[0]}"
    finally:
        loop.call_soon_threadsafe(done[0].set_result, None)
        thread.join(10)
        loop.close()


def plan(url: str, **overrides: Any) -> LoadPlan:
    values: dict[str, Any] = {
        "endpoint": Endpoint(url),
        "shape": SHAPE,
        "sessions": 2,
        "mode": "open",
        "rate": 100.0,
        "warmup_s": 0.1,
        "duration_s": 0.5,
        "drain_s": 1.0,
    }
    return LoadPlan(**{**values, **overrides})


def run_inline(
    load: LoadPlan, on_start: Callable[[asyncio.AbstractEventLoop], None] | None = None
) -> LoadResult:
    """Drive a plan's sessions on this thread, as one generator process does.

    Args:
        load: The plan.
        on_start: Called on the generator's event loop once the sessions are primed.

    Returns:
        The merged result.
    """

    def start(errors: list[str]) -> Awaitable[int | None]:
        if errors:
            return asyncio.sleep(0, None)
        if on_start is not None:
            on_start(asyncio.get_running_loop())
        return asyncio.sleep(0, time.perf_counter_ns() + 20_000_000)

    loop = events.event_loop()
    try:
        shard = loop.run_until_complete(
            events._run_sessions(load, range(load.sessions), start)
        )
    finally:
        loop.close()
    return events._merge(load, [shard])


class Scripted(EchoServer):
    """An echo server that records the seq events and asks a hook about each."""

    def __init__(self, protocol: WireProtocol = "websocket") -> None:
        """Record nothing yet.

        Args:
            protocol: The protocol to speak.
        """
        super().__init__(delta_key=STATE, seq_var=SEQ_VAR, protocol=protocol)
        self.seqs: list[int] = []
        self.tokens: list[str] = []

    async def end(self, ws: ServerConnection) -> None:
        """End a session as reflex does: Socket.IO leaves the namespace, the plain protocol closes with a code.

        Args:
            ws: The connection.
        """
        if self.codec.protocol == "socketio":
            await ws.send(events.SIO_DISCONNECT_FRAME)
        else:
            await ws.close(1008)

    async def on_event(self, ws: ServerConnection, event: dict[str, Any]) -> None:
        """Record a seq event, then answer it unless the hook says otherwise.

        Args:
            ws: The connection.
            event: The event.
        """
        if event["name"] == SHAPE.name:
            seq = event["payload"]["seq"]
            self.seqs.append(seq)
            self.tokens.append(event["token"])
            if not await self.seq_event(ws, event, seq):
                return
        await super().on_event(ws, event)

    async def seq_event(
        self, ws: ServerConnection, event: dict[str, Any], seq: int
    ) -> bool:
        """Decide what happens to a seq event before it is answered.

        Args:
            ws: The connection.
            event: The event.
            seq: Its sequence number.

        Returns:
            Whether to answer it now.
        """
        return True


def test_event_urls():
    assert (
        WEBSOCKET.url("http://localhost:8000", "tok")
        == "ws://localhost:8000/_event?token=tok"
    )
    assert (
        SOCKETIO.url("http://localhost:8000", "tok")
        == "ws://localhost:8000/_event/?EIO=4&transport=websocket&token=tok"
    )
    assert (
        WEBSOCKET.url("https://app.example.com/", "tok")
        == "wss://app.example.com/_event?token=tok"
    )
    assert SOCKETIO.url("https://app.example.com/base/", "tok").startswith(
        "wss://app.example.com/base/_event/?"
    )


def test_event_frames_always_carry_the_token():
    # 0.8.23 rejects an event without a token and later releases ignore it,
    # so every frame carries it.
    frame = WEBSOCKET.event_frame(f"{STATE}.set_seq", {"seq": 7}, token="tok")
    assert frame == (
        f'["event",{{"name":"{STATE}.set_seq","payload":{{"seq":7}},'
        '"router_data":{"pathname":"/","asPath":"/","query":{}},"token":"tok"}]'
    )
    socketio = SOCKETIO.event_frame(f"{STATE}.set_seq", {"seq": 7}, token="tok")
    assert socketio == f"42/_event,{frame}"
    for codec in (WEBSOCKET, SOCKETIO):
        frames = events._Frames(codec, SHAPE, "tok", "/", index=3)
        assert frames.event(7) == codec.event_frame(
            f"{STATE}.set_seq", {"seq": 7}, token="tok"
        )
        message = codec.parse(frames.event(8))
        assert message is not None
        name, event = message
        assert (name, event["payload"]) == ("event", {"seq": 8})
        # A shape with a client var sends the session's index along.
        contended = events._Frames(codec, CONTENDED_SHAPE, "tok", "/", index=3)
        message = codec.parse(contended.event(8))
        assert message is not None
        assert message[1]["payload"] == {"seq": 8, "client": 3}


def test_the_plain_connect_frame_carries_the_hydration_as_its_boot_event():
    frame = WEBSOCKET.connect_frame(
        token="tok", pathname="/item/42", query={"item_id": "42"}
    )
    assert frame == (
        '["_connect",{"event":{"name":"reflex___state____state.hydrate_and_load",'
        '"payload":{},"router_data":{"pathname":"/item/42","asPath":"/item/42",'
        '"query":{"item_id":"42"}},"token":"tok"}}]'
    )
    assert WEBSOCKET.load_events == ()
    assert not WEBSOCKET.greets
    # Socket.IO joins the namespace and hydrates once acknowledged, as 0.8.23 needs.
    assert SOCKETIO.connect_frame(token="tok", pathname="/") == "40/_event,"
    assert SOCKETIO.load_events == (events.HYDRATE_EVENT, events.ON_LOAD_EVENT)
    assert SOCKETIO.greets


def test_both_codecs_decode_to_the_plain_protocols_messages():
    assert WEBSOCKET.parse('["_ping"]') == SOCKETIO.parse("2") == [events.PING]
    assert WEBSOCKET.parse('["_handshake",{"protocol":2}]') == [
        events.HANDSHAKE,
        {"protocol": 2},
    ]
    assert SOCKETIO.parse('40/_event,{"sid":"a"}') == [events.HANDSHAKE, '{"sid":"a"}']
    assert SOCKETIO.parse('0{"sid":"a"}') == [events.OPENED, '{"sid":"a"}']
    assert SOCKETIO.parse('44/_event,{"message":"no"}') == [
        events.REFUSED,
        '{"message":"no"}',
    ]
    assert SOCKETIO.parse("41/_event,") == SOCKETIO.parse("1") == [events.DISCONNECTED]
    for codec in (WEBSOCKET, SOCKETIO):
        assert codec.parse(codec.emit("new_token", "t")) == ["new_token", "t"]
        assert codec.parse(b'["event",{}]') is None
    for frame in ("{}", "[1]", "[]", "nope"):
        assert WEBSOCKET.parse(frame) is None
    assert SOCKETIO.parse("6") is None
    assert SOCKETIO.parse("42/_event,nope") is None
    assert (WEBSOCKET.pong, SOCKETIO.pong) == ('["_pong"]', "3")
    assert (WEBSOCKET.leave, SOCKETIO.leave) == (None, "41/_event,")


@pytest.mark.parametrize(
    ("reply", "codec"),
    [(HEAD_REPLY, WEBSOCKET), (SOCKETIO_REPLY, SOCKETIO), (OLD_REPLY, SOCKETIO)],
)
def test_replies_of_every_version_carry_the_same_delta(reply: str, codec: Any):
    message = codec.parse(reply)
    assert message is not None
    name, update = message
    assert name == "event"
    assert update["delta"] == {STATE: {SEQ_VAR: 7}}


@PROTOCOLS
def test_the_protocol_is_detected(protocol: WireProtocol):
    # Each server refuses the websocket on the other protocol's path.
    with serving(Scripted(protocol)) as url:
        assert asyncio.run(events.detect_protocol(url)) == protocol
        codec = asyncio.run(events.resolve_codec(Endpoint(url)))
    assert codec is CODECS[protocol]


def test_a_named_protocol_is_not_detected():
    port = free_ports()[0]
    endpoint = Endpoint(f"http://127.0.0.1:{port}", protocol="socketio")
    assert asyncio.run(events.resolve_codec(endpoint)) is SOCKETIO
    with pytest.raises(OSError):
        asyncio.run(events.detect_protocol(endpoint.backend_url))


def test_a_refused_namespace_fails_the_session():
    class Refusing(Scripted):
        """Refuses the namespace, as python-socketio does when on_connect rejects."""

        async def on_connect(self, ws, sid):
            """Send a connect_error instead of the ack."""
            await ws.send('44/_event,{"message":"Unable to connect"}')

    with serving(Refusing("socketio")) as url:
        result = run_inline(plan(url, sessions=1))
    assert result.sent == 0
    (error,) = result.session_errors
    assert "refused /_event" in error
    assert "Unable to connect" in error


def test_a_session_closed_in_the_handshake_fails():
    class Closing(Scripted):
        """Closes the connect with a policy violation, as reflex does without a token."""

        async def on_connect(self, ws, sid):
            """Close instead of the handshake."""
            await ws.close(1008)

    with serving(Closing()) as url:
        result = run_inline(plan(url, sessions=1))
    assert result.sent == 0
    (error,) = result.session_errors
    assert "could not connect: ConnectionClosedError" in error
    assert "1008" in error


def test_an_unexpected_frame_fails_the_session():
    # reflex never sends binary attachments; anything the generator does not
    # speak ends the session with a reason instead of being ignored.
    class Binary(Scripted):
        """Sends a binary frame instead of answering seq 3."""

        async def seq_event(self, ws, event, seq):
            """Send bytes once.

            Returns:
                Whether to answer.
            """
            if seq == 3:
                await ws.send(b"\x00\x01")
                return False
            return True

    with serving(Binary()) as url:
        result = run_inline(plan(url, sessions=1, rate=20.0, warmup_s=0.0))
    (error,) = result.session_errors
    assert "unexpected frame" in error


def test_the_plan_checks_its_rate():
    with pytest.raises(ValueError, match="positive rate"):
        plan("http://localhost:8000", rate=None)
    with pytest.raises(ValueError, match="finite positive rate"):
        plan("http://localhost:8000", rate=float("inf"))
    with pytest.raises(ValueError, match="closed loop"):
        plan("http://localhost:8000", mode="closed", rate=10.0)
    with pytest.raises(ValueError, match="at least one session per process"):
        plan("http://localhost:8000", sessions=2, processes=3)


def test_schedule_spreads_sessions_evenly():
    # 3 sessions sharing 30 ev/s: 10 ev/s each, offset by 1/30 s.
    second = 1_000_000_000
    schedules = [list(events.schedule_ns(index, 3, 30.0, second)) for index in range(3)]
    assert [len(times) for times in schedules] == [10, 10, 10]
    assert schedules[0] == [i * 100_000_000 for i in range(10)]
    assert schedules[1][:2] == [33_333_333, 133_333_333]
    merged = sorted(t for times in schedules for t in times)
    assert merged == [int(k * second / 30) for k in range(30)]


@PROTOCOLS
def test_every_event_is_answered(protocol: WireProtocol):
    server = Scripted(protocol)
    with serving(server) as url:
        result = run_inline(plan(url, sessions=3, rate=150.0))
    # 150 ev/s over the 0.5 s window, as planned.
    assert result.sent == 75
    assert result.answered == result.sent
    assert result.unanswered == 0
    assert result.out_of_order == 0
    assert result.session_errors == []
    assert result.offered_rate == pytest.approx(150.0)
    assert result.achieved_send_rate == pytest.approx(150.0)
    assert result.answered_rate == pytest.approx(150.0)
    assert result.response_s is not None
    assert result.service_s is not None
    assert result.lag_s is not None
    assert result.response_s["p50"] >= result.service_s["p50"] > 0
    assert result.lag_s["p50"] >= 0
    assert result.prime_s is not None
    assert result.prime_s["max"] > 0
    assert result.histogram["of"] == "response_s"
    assert sum(result.histogram["counts"]) == result.answered
    # The 15 warmup events were sent and answered, but not measured.
    assert len(server.seqs) == 90
    assert result.reply_frame is not None
    assert f'"{SEQ_VAR}":' in result.reply_frame
    json.dumps(result.to_dict(), allow_nan=False)


def test_answers_after_the_window_do_not_count_in_the_rates():
    # The drain collects late answers so they are not unanswered, but the
    # throughput is what the server answered within the window.
    class LateAtTheEnd(Scripted):
        """Stalls 0.6 s at seq 20, so it and the later events answer past the window."""

        async def seq_event(self, ws, event, seq):
            """Stall once.

            Returns:
                True.
            """
            if seq == 20:
                await asyncio.sleep(0.6)
            return True

    with serving(LateAtTheEnd()) as url:
        result = run_inline(plan(url, sessions=1, rate=50.0, warmup_s=0.0))
    assert result.sent == result.answered == 25
    assert result.unanswered == 0
    assert result.achieved_send_rate == pytest.approx(50.0)
    # 19 answers arrived before the 0.5 s window ended.
    assert result.answered_per_second == [19]
    assert result.answered_rate == pytest.approx(38.0)
    # The late answers still count in the response tail.
    assert result.response_s is not None
    assert result.response_s["max"] >= 0.6


def test_answers_are_counted_per_second_of_the_window():
    with serving(Scripted()) as url:
        result = run_inline(
            plan(url, sessions=2, rate=50.0, warmup_s=0.0, duration_s=1.5)
        )
    assert result.sent == 75
    assert len(result.answered_per_second) == 2
    assert sum(result.answered_per_second) <= result.answered
    assert result.answered_rate == pytest.approx(sum(result.answered_per_second) / 1.5)
    assert result.answered_per_second[0] == pytest.approx(50, abs=2)


def test_a_slow_server_shows_in_service_and_response():
    class Slow(Scripted):
        """Answers every seq event 20 ms late, one at a time per connection."""

        async def seq_event(self, ws, event, seq):
            """Wait before answering.

            Returns:
                True.
            """
            await asyncio.sleep(0.02)
            return True

    with serving(Slow()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0))
    assert result.unanswered == 0
    assert result.service_s is not None
    assert result.response_s is not None
    assert result.service_s["p50"] >= 0.02
    assert result.response_s["p50"] >= result.service_s["p50"]


def test_dropped_seqs_are_unanswered_not_dropped():
    class Dropping(Scripted):
        """Never answers seq 5 and 9."""

        async def seq_event(self, ws, event, seq):
            """Drop two seqs.

            Returns:
                Whether to answer.
            """
            return seq not in {5, 9}

    with serving(Dropping()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0, warmup_s=0.0))
    assert result.sent == 20
    assert result.unanswered == 4
    assert result.answered == 16
    # A missing answer shows when the next one overtakes it.
    assert result.out_of_order == 4


class Reordering(Scripted):
    """Answers seq 5 only after seq 6."""

    def __init__(self) -> None:
        """Hold nothing yet."""
        super().__init__()
        self.held: dict[ServerConnection, dict[str, Any]] = {}

    async def seq_event(self, ws, event, seq):
        """Swap the answers of seq 5 and 6.

        Returns:
            Whether to answer now.
        """
        if seq == 5:
            self.held[ws] = event
            return False
        if seq == 6:
            await ws.send(self.reply(event))
            await ws.send(self.reply(self.held.pop(ws)))
            return False
        return True


def test_a_reordered_pair_counts_out_of_order():
    with serving(Reordering()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0, warmup_s=0.0))
    # Seq 6 arrived while 5 was outstanding: 5 counts as unanswered, and its
    # late answer does not resolve it.
    assert result.out_of_order == 2
    assert result.unanswered == 2
    assert result.answered == result.sent - 2


def test_an_unordered_shape_takes_answers_in_any_order():
    # Background tasks may finish in any order, so a late answer still counts.
    unordered = dataclasses.replace(SHAPE, ordered=False)
    with serving(Reordering()) as url:
        result = run_inline(
            plan(url, sessions=2, rate=40.0, warmup_s=0.0, shape=unordered)
        )
    assert result.out_of_order == 2
    assert result.unanswered == 0
    assert result.answered == result.sent


@PROTOCOLS
def test_a_new_token_is_adopted(protocol: WireProtocol):
    class Renaming(Scripted):
        """Hands every connection a new token, as reflex does for a duplicate tab."""

        async def on_connect(self, ws, sid):
            """Send the new token before the handshake, as reflex does."""
            await ws.send(self.codec.emit("new_token", f"fresh-{sid}"))
            await super().on_connect(ws, sid)

    server = Renaming(protocol)
    with serving(server) as url:
        result = run_inline(plan(url, sessions=1, rate=20.0))
    assert result.unanswered == 0
    assert server.tokens
    assert all(token.startswith("fresh-") for token in server.tokens)


@PROTOCOLS
def test_a_session_that_never_hydrates_fails(
    monkeypatch: pytest.MonkeyPatch, protocol: WireProtocol
):
    monkeypatch.setattr(events, "PRIME_TIMEOUT_S", 0.5)
    with serving(NeverHydrated(protocol)) as url:
        result = run_inline(plan(url, sessions=1))
    assert result.sent == 0
    assert len(result.session_errors) == 1
    assert "not hydrated within 0.5 s" in result.session_errors[0]


@pytest.mark.parametrize(
    ("protocol", "reason"),
    [
        ("websocket", "the websocket closed: received 1008"),
        ("socketio", "the server disconnected the session"),
    ],
)
def test_a_disconnect_mid_run_fails_the_session(protocol: WireProtocol, reason: str):
    class Disconnecting(Scripted):
        """Ends the session of the first connection instead of answering seq 5."""

        def __init__(self) -> None:
            """Know no connection yet."""
            super().__init__(protocol)
            self.first: ServerConnection | None = None

        async def seq_event(self, ws, event, seq):
            """Disconnect the first connection at seq 5.

            Returns:
                Whether to answer.
            """
            if self.first is None:
                self.first = ws
            if ws is self.first and seq == 5:
                await self.end(ws)
                return False
            return True

    with serving(Disconnecting()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0, warmup_s=0.0))
    assert len(result.session_errors) == 1
    assert reason in result.session_errors[0]
    # One session stopped after seq 5, which stays unanswered; the other ran on.
    assert result.sent == 15
    assert result.unanswered == 1


def test_a_server_stall_shows_in_the_tail():
    # The open loop keeps sending while the server stalls, so every event
    # planned during the stall waits: a closed loop would sample only one.
    class Stalling(Scripted):
        """Stops answering for 200 ms at seq 10."""

        async def seq_event(self, ws, event, seq):
            """Stall once.

            Returns:
                True.
            """
            if seq == 10:
                await asyncio.sleep(0.2)
            return True

    with serving(Stalling()) as url:
        result = run_inline(
            plan(url, sessions=1, rate=50.0, warmup_s=0.0, duration_s=1.0)
        )
    assert result.sent == 50
    assert result.unanswered == 0
    assert result.response_s is not None
    assert result.service_s is not None
    # Fewer than 100 events: p99 is the slowest one, the event that hit the stall.
    assert result.response_s["p99"] >= 0.2
    # The next nine events waited 180 ms down to 20 ms.
    assert result.response_s["p90"] >= 0.08
    assert result.service_s["p50"] < 0.05


def test_late_sends_are_never_skipped_and_count_from_the_plan():
    # A generator that falls 200 ms behind sends every late event at once; the
    # response time still counts from the planned send time.
    def block(loop: asyncio.AbstractEventLoop) -> None:
        loop.call_later(0.3, time.sleep, 0.2)

    with serving(Scripted()) as url:
        result = run_inline(
            plan(url, sessions=1, rate=50.0, warmup_s=0.0, duration_s=1.0), block
        )
    assert result.sent == 50
    assert result.answered == 50
    assert result.lag_s is not None
    assert result.response_s is not None
    assert result.service_s is not None
    assert result.lag_s["max"] >= 0.19
    assert result.response_s["max"] >= 0.19
    assert result.service_s["max"] < 0.1
    check = result.check()
    assert check is not None
    assert check.startswith("generator saturated: send lag p99")


def test_closed_loop_reports_service_time_only():
    with serving(Scripted()) as url:
        result = run_inline(plan(url, mode="closed", rate=None, sessions=2))
    assert result.mode == "closed"
    assert result.offered_rate is None
    assert result.response_s is None
    assert result.lag_s is None
    assert result.service_s is not None
    assert result.answered > 0
    assert result.unanswered == 0
    # Each session's event in flight at the end of the window is answered in
    # the drain: it is not unanswered, but it is not throughput either.
    in_window = sum(result.answered_per_second)
    assert 0 <= result.answered - in_window <= 2
    assert result.answered_rate == pytest.approx(in_window / 0.5)
    assert result.answered_rate <= result.achieved_send_rate
    assert result.histogram["of"] == "service_s"


BOARD = "reflex___state____state.playground___state____board_state"
CLIENT_VAR = "last_client_rx_state_"
LINK = LinkEvent(name=f"{BOARD}.join", payload={"token": "board-1"}, delta_key=BOARD)
BOARD_SHAPE = EventShape(
    name=f"{BOARD}.set_seq_shared",
    payload=events.seq_payload,
    delta_key=BOARD,
    seq_var=SEQ_VAR,
)
CONTENDED_SHAPE = dataclasses.replace(BOARD_SHAPE, client_var=CLIENT_VAR)


class Board(EchoServer):
    """Answers like the playground's shared board: a join links a connection to a token, and a seq event reaches every linked connection."""

    def __init__(self, protocol: WireProtocol = "websocket") -> None:
        """Link nothing yet.

        Args:
            protocol: The protocol to speak.
        """
        super().__init__(delta_key=BOARD, seq_var=SEQ_VAR, protocol=protocol)
        self.linked: dict[str, list[ServerConnection]] = {}
        self.names: dict[ServerConnection, list[str]] = {}
        self.payloads: list[dict[str, Any]] = []

    async def on_event(self, ws: ServerConnection, event: dict[str, Any]) -> None:
        """Record the event, then answer it: a join acknowledges, a seq event fans out.

        Args:
            ws: The connection.
            event: The event.
        """
        self.names.setdefault(ws, []).append(event["name"])
        if event["name"] == LINK.name:
            self.linked.setdefault(event["payload"]["token"], []).append(ws)
            await ws.send(self.codec.emit("event", {"delta": {BOARD: {SEQ_VAR: 0}}}))
        elif event["name"] == BOARD_SHAPE.name:
            self.payloads.append(event["payload"])
            delta = {
                BOARD: {
                    SEQ_VAR: event["payload"]["seq"],
                    CLIENT_VAR: event["payload"].get("client", 0),
                }
            }
            for index, linked in enumerate(self.linked_to(ws)):
                await self.deliver(
                    linked, index, self.codec.emit("event", {"delta": delta})
                )
        else:
            await super().on_event(ws, event)

    def linked_to(self, ws: ServerConnection) -> list[ServerConnection]:
        """List the connections that share a token with one.

        Args:
            ws: The connection.

        Returns:
            The linked connections, the sender first.
        """
        for linked in self.linked.values():
            if ws in linked:
                return [ws, *(other for other in linked if other is not ws)]
        return [ws]

    async def deliver(self, ws: ServerConnection, index: int, frame: str) -> None:
        """Send a fan-out delta to one linked connection.

        Args:
            ws: The connection.
            index: Its place among the linked connections, the sender at 0.
            frame: The delta.
        """
        await ws.send(frame)


def board_plan(url: str, **overrides: Any) -> LoadPlan:
    return plan(url, **{"shape": BOARD_SHAPE, "link": LINK, **overrides})


@PROTOCOLS
def test_linked_sessions_join_after_hydrating_and_before_the_load(
    protocol: WireProtocol,
):
    server = Board(protocol)
    with serving(server) as url:
        result = run_inline(board_plan(url, mode="closed", rate=None, sessions=3))
    assert result.session_errors == []
    assert result.answered > 0
    assert len(server.linked["board-1"]) == 3
    primed = [*HYDRATION[protocol], LINK.name]
    for names in server.names.values():
        assert names[: len(primed)] == primed
        assert set(names[len(primed) :]) == {BOARD_SHAPE.name}


def test_a_session_whose_join_is_not_acknowledged_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    class Deaf(Board):
        """Links but never acknowledges."""

        async def on_event(self, ws, event):
            if event["name"] == LINK.name:
                return
            await super().on_event(ws, event)

    monkeypatch.setattr(events, "PRIME_TIMEOUT_S", 0.5)
    with serving(Deaf()) as url:
        result = run_inline(board_plan(url, sessions=1))
    assert result.sent == 0
    assert result.session_errors == ["session 0: not linked within 0.5 s"]


def test_a_fan_out_event_is_answered_once_every_linked_session_has_it():
    class Trailing(Board):
        """Delivers to the last linked session 50 ms after the others."""

        async def deliver(self, ws, index, frame):
            if index == 2:
                await asyncio.sleep(0.05)
            await ws.send(frame)

    server = Trailing()
    with serving(server) as url:
        result = run_inline(board_plan(url, mode="fanout", rate=None, sessions=3))
    assert result.session_errors == []
    assert result.mode == "fanout"
    assert result.sessions == 3
    # Only the first session sends, and its payload names no client.
    assert result.sent > 0
    assert all(
        payload == {"seq": seq} for seq, payload in enumerate(server.payloads, 1)
    )
    assert result.answered == result.sent
    assert result.unanswered == 0
    # An event completes when the trailing session has it, not when the sender does.
    assert result.service_s is not None
    assert result.service_s["p50"] >= 0.05
    assert result.spread_s is not None
    assert 0.05 <= result.spread_s["p50"] < result.service_s["p50"]
    assert result.response_s is None
    assert result.histogram["of"] == "service_s"
    assert result.answered_rate < 20
    assert result.check() is None


def test_a_fan_out_event_missing_a_session_stays_unanswered():
    class Skipping(Board):
        """Never delivers to the second linked session."""

        async def deliver(self, ws, index, frame):
            if index != 1:
                await ws.send(frame)

    with serving(Skipping()) as url:
        result = run_inline(
            board_plan(url, mode="fanout", rate=None, sessions=3, warmup_s=0.0)
        )
    assert result.session_errors == []
    # The sender and one listener had the first event, which stalls the loop.
    assert result.sent == 1
    assert result.answered == 0
    assert result.unanswered == 1
    assert result.spread_s is None


def test_a_fan_out_runs_in_one_process():
    with pytest.raises(ValueError, match="one process"):
        board_plan("http://x", mode="fanout", rate=None, sessions=4, processes=2)
    with pytest.raises(ValueError, match="takes no rate"):
        board_plan("http://x", mode="fanout", rate=10.0, sessions=4)


def test_contending_sessions_are_answered_by_their_own_echo_only():
    server = Board()
    with serving(server) as url:
        result = run_inline(
            board_plan(url, shape=CONTENDED_SHAPE, sessions=3, rate=150.0)
        )
    assert result.session_errors == []
    # Every session saw the other sessions' deltas, yet each event has one answer.
    assert result.sent == 75
    assert result.answered == result.sent
    assert result.out_of_order == 0
    assert sorted({payload["client"] for payload in server.payloads}) == [0, 1, 2]
    assert result.reply_frame is not None
    assert f'"{CLIENT_VAR}":' in result.reply_frame


def healthy(**overrides: Any) -> LoadResult:
    return make_load_result(reply_frame=HEAD_REPLY, **overrides)


SLOW = {"p50": 0.03, "p90": 0.05, "p99": 0.06, "p999": 0.07, "max": 0.08}
QUICK_SERVICE = {"p50": 0.001, "p99": 0.002, "max": 0.004}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        # 1 ms is the floor of the lag limit...
        (
            {
                "lag_s": {"p50": 1e-4, "p99": 0.0015, "max": 0.002},
                "service_s": QUICK_SERVICE,
            },
            "send lag p99 1.50 ms exceeds 1.00 ms",
        ),
        # ...which grows to 10 % of the median response...
        (
            {
                "lag_s": {"p50": 1e-4, "p99": 0.004, "max": 0.005},
                "response_s": SLOW,
                "service_s": QUICK_SERVICE,
            },
            "send lag p99 4.00 ms exceeds 3.00 ms",
        ),
        (
            {"lag_s": {"p50": 1e-4, "p99": 0.007, "max": 0.009}},
            "send lag p99 7.00 ms exceeds 1.00 ms",
        ),
        ({"generator_cpu_fraction": 0.8}, "80 % of a core"),
        ({"achieved_send_rate": 390.0}, "sent 390 ev/s"),
    ],
)
def test_the_self_check_trips(overrides: dict[str, Any], reason: str):
    check = healthy(**overrides).check()
    assert check is not None
    assert check.startswith("generator saturated: ")
    assert reason in check


def test_the_self_check_passes_a_healthy_result():
    assert healthy().check() is None
    # A lag under 10 % of a slow median response is fine.
    lag = {"p50": 1e-4, "p99": 0.0025, "max": 0.005}
    assert healthy(lag_s=lag, response_s=SLOW, service_s=QUICK_SERVICE).check() is None


def test_the_self_check_judges_the_generator_alone():
    # A host stall delayed both the generator (2 % CPU) and the server on a VM
    # with steal time. The lag is the generator's own, whatever the server's
    # service tail did, and it inflates the response tail, so the load fails.
    stalled = healthy(
        offered_rate=50.0,
        achieved_send_rate=50.0,
        response_s={
            "p50": 0.00164,
            "p90": 0.00224,
            "p99": 0.02534,
            "p999": 0.08976,
            "max": 0.10979,
        },
        service_s={"p50": 0.00142, "p99": 0.02097, "max": 0.08425},
        lag_s={"p50": 0.00022, "p99": 0.00645, "max": 0.02773},
        generator_cpu_fraction=0.02,
    )
    check = stalled.check()
    assert check is not None
    assert "send lag p99 6.45 ms exceeds 1.00 ms" in check


def test_the_closed_loop_self_check_only_watches_cpu():
    closed = {
        "mode": "closed",
        "offered_rate": None,
        "achieved_send_rate": 100.0,
        "response_s": None,
        "lag_s": None,
    }
    assert healthy(**closed).check() is None
    assert healthy(**closed, generator_cpu_fraction=0.9).check() is not None


def test_the_summary_leaves_the_arrays_out():
    result = healthy()
    summary = result.summary()
    assert "histogram" not in summary
    assert "answered_per_second" not in summary
    assert summary["answered"] == result.answered
    assert set(result.to_dict()) - set(summary) == {"histogram", "answered_per_second"}


def test_generator_saturated_carries_the_result():
    result = healthy(generator_cpu_fraction=0.8)
    reason = result.check()
    assert reason is not None
    error = GeneratorSaturated(reason, result)
    assert str(error).startswith("generator saturated: ")
    assert '"generator_cpu_fraction": 0.8' in str(error)
    assert error.result is result


def test_run_load_merges_spawned_processes(monkeypatch: pytest.MonkeyPatch):
    contexts: list[str | None] = []
    get_context = multiprocessing.get_context

    def spy(method: str | None = None) -> Any:
        contexts.append(method)
        return get_context(method)

    monkeypatch.setattr(events.multiprocessing, "get_context", spy)
    server = Scripted()
    windows: list[tuple[str, int]] = []
    with serving(server) as url:
        load = plan(url, sessions=4, processes=2, rate=200.0, warmup_s=0.0)
        result = LoadRunner(load).run(
            on_window=lambda edge: windows.append((edge, time.perf_counter_ns()))
        )
    assert contexts == ["spawn"]
    assert result.processes == 2
    assert result.sessions == 4
    # Without warmup, the server saw exactly the measured events of both processes.
    assert result.sent == len(server.seqs) == 100
    assert result.answered == result.sent
    assert result.unanswered == 0
    assert [edge for edge, _ in windows] == ["start", "end"]
    assert (windows[1][1] - windows[0][1]) / 1e9 == pytest.approx(0.5, abs=0.1)
    assert multiprocessing.active_children() == []


def test_run_load_raises_when_sessions_cannot_connect():
    port = free_ports()[0]
    with pytest.raises(LoadError, match="could not start"):
        run_load(plan(f"http://127.0.0.1:{port}", sessions=1))
    assert multiprocessing.active_children() == []


def test_stop_kills_the_generator_processes():
    errors: list[BaseException] = []
    with serving(Scripted()) as url:
        runner = LoadRunner(plan(url, sessions=2, rate=20.0, duration_s=60.0))

        def run() -> None:
            try:
                runner.run()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(3)
        stopped = time.monotonic()
        runner.stop()
        thread.join(15)
        assert not thread.is_alive()
        assert time.monotonic() - stopped < 10
    assert len(errors) == 1
    assert isinstance(errors[0], LoadError)
    assert "stopped" in str(errors[0])
    assert multiprocessing.active_children() == []


def test_a_generator_process_ends_when_its_parent_goes_away():
    # However the harness exits, the closed pipe ends the generator's run.
    with serving(Scripted()) as url:
        context = multiprocessing.get_context("spawn")
        conn, child = context.Pipe()
        load = plan(url, sessions=1, rate=20.0, duration_s=60.0)
        proc = context.Process(
            target=events._worker, args=(load, range(1), child), daemon=True
        )
        proc.start()
        child.close()
        assert conn.poll(30)
        assert conn.recv() == ("ready", [])
        conn.send(("go", time.perf_counter_ns()))
        time.sleep(0.5)
        conn.close()
        proc.join(10)
        assert proc.exitcode is not None


class NeverHydrated(Scripted):
    """Ignores the events that complete the hydration, so is_hydrated never becomes true."""

    async def on_event(self, ws, event):
        """Answer everything but those."""
        if event["name"] not in HYDRATING:
            await super().on_event(ws, event)


class Counting(Scripted):
    """Counts the hydrations and the sessions that ended; the protocol's probe is no session."""

    def __init__(self, protocol: WireProtocol = "websocket") -> None:
        """Count nothing yet.

        Args:
            protocol: The protocol to speak.
        """
        super().__init__(protocol)
        self.hydrated = 0
        self.left = 0
        self._sessions: set[ServerConnection] = set()

    async def on_connect(self, ws, sid):
        """Count a session."""
        self._sessions.add(ws)
        await super().on_connect(ws, sid)

    async def on_event(self, ws, event):
        """Count the event that completes a hydration, then answer."""
        if event["name"] in HYDRATING:
            self.hydrated += 1
        await super().on_event(ws, event)

    async def handle(self, ws):
        """Count a session that ends."""
        try:
            await super().handle(ws)
        finally:
            self.left += ws in self._sessions


def test_open_sessions_primes_and_closes_them():
    server = Counting()
    with serving(server) as url:
        loop = events.event_loop()

        async def hold() -> list[str]:
            async with open_sessions(Endpoint(url), 3) as pool:
                assert server.hydrated == 3
                assert server.left == 0
                return pool.errors

        try:
            errors = loop.run_until_complete(hold())
        finally:
            loop.close()
    assert errors == []
    assert server.left == 3


def test_open_sessions_reports_the_sessions_that_fail(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(events, "PRIME_TIMEOUT_S", 0.5)
    with serving(NeverHydrated()) as url:
        loop = events.event_loop()

        async def hold() -> list[str]:
            async with open_sessions(Endpoint(url), 2) as pool:
                return pool.errors

        try:
            errors = loop.run_until_complete(hold())
        finally:
            loop.close()
    assert len(errors) == 2
    assert all("not hydrated within 0.5 s" in error for error in errors)


class Holding(Counting):
    """Pings often and records each session's frames and close code."""

    def __init__(self, protocol: WireProtocol = "websocket") -> None:
        """Record nothing yet.

        Args:
            protocol: The protocol to speak.
        """
        super().__init__(protocol)
        self.ping_interval_s = 0.2
        self.frames: list[list[str | bytes]] = []
        self.close_codes: list[int | None] = []

    async def handle(self, ws):
        """Serve a connection, recording a session's frames and how it closed."""
        frames: list[str | bytes] = []
        recording = cast(ServerConnection, _Recording(ws, frames))
        await super().handle(recording)
        if recording in self._sessions:
            self.frames.append(frames)
            self.close_codes.append(ws.close_code)


class _Recording:
    """A server connection that records every frame the client sends."""

    def __init__(self, ws: ServerConnection, frames: list[str | bytes]) -> None:
        """Wrap a connection.

        Args:
            ws: The connection.
            frames: Receives the client's frames.
        """
        self._ws = ws
        self._frames = frames

    def __getattr__(self, name: str) -> Any:
        """Delegate to the connection.

        Args:
            name: The attribute.

        Returns:
            The connection's attribute.
        """
        return getattr(self._ws, name)

    async def __aiter__(self) -> AsyncIterator[str | bytes]:
        """Receive frames, recording them.

        Yields:
            Each frame.
        """
        async for message in self._ws:
            self._frames.append(message)
            yield message


def wait_for(condition: Callable[[], bool], timeout: float = 10.0) -> bool:
    """Poll a condition.

    Args:
        condition: The condition.
        timeout: Seconds to wait.

    Returns:
        Whether it held in time.
    """
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


@PROTOCOLS
def test_a_hold_keeps_hydrated_sessions_until_closed(protocol: WireProtocol):
    server = Holding(protocol)
    codec = CODECS[protocol]
    with serving(server) as url:
        hold = events.hold_sessions(Endpoint(url), 3)
        try:
            hold.ready()
            assert server.hydrated == 3
            time.sleep(1.0)
            assert server.left == 0
            assert hold.close() == []
        finally:
            hold.kill()
        assert wait_for(lambda: server.left == 3)
    for frames in server.frames:
        # The sessions answered the pings while held, then left.
        assert codec.pong in frames
        if codec.leave is not None:
            assert frames[-1] == codec.leave
    if codec.leave is None:
        # The plain protocol leaves with a normal close.
        assert server.close_codes == [1000] * 3
    assert multiprocessing.active_children() == []


def test_a_hold_raises_when_sessions_cannot_connect():
    port = free_ports()[0]
    hold = events.hold_sessions(Endpoint(f"http://127.0.0.1:{port}"), 3)
    try:
        with pytest.raises(LoadError, match="3 of 3 sessions could not start"):
            hold.ready()
    finally:
        hold.kill()
    assert multiprocessing.active_children() == []


def test_close_reports_sessions_lost_while_held():
    class Dropping(Holding):
        """Closes the first hydrated connection half a second later."""

        async def on_event(self, ws, event):
            """Answer, then schedule the end of the first connection."""
            await super().on_event(ws, event)
            if event["name"] in HYDRATING and self.hydrated == 1:
                loop = asyncio.get_running_loop()
                loop.call_later(0.5, lambda: loop.create_task(self.end(ws)))

    with serving(Dropping()) as url:
        hold = events.hold_sessions(Endpoint(url), 2)
        try:
            hold.ready()
            time.sleep(1.0)
            errors = hold.close()
        finally:
            hold.kill()
    assert len(errors) == 1
    assert "the websocket closed: received 1008" in errors[0]
    assert multiprocessing.active_children() == []


def test_kill_ends_a_hold_that_is_still_priming():
    class NeverPrimed(Holding):
        """Ignores the events that complete the hydration, so no session finishes priming."""

        async def on_event(self, ws, event):
            """Answer everything but those."""
            if event["name"] not in HYDRATING:
                await super().on_event(ws, event)

    with serving(NeverPrimed()) as url:
        hold = events.hold_sessions(Endpoint(url), 2)
        killer = threading.Timer(1.0, hold.kill)
        killer.start()
        started = time.monotonic()
        with pytest.raises(LoadError, match="stopped"):
            hold.ready()
        killer.join()
        assert time.monotonic() - started < 10
        # Killing again, or closing after the kill, does nothing more.
        hold.kill()
        with pytest.raises(LoadError, match="stopped"):
            hold.close()
    assert multiprocessing.active_children() == []
