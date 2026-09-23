"""Tests for reflex_bench.drivers.events.

The generator runs against :class:`~reflex_bench.drivers.echo_server.EchoServer`
on a thread of the test process; subclasses script delays, dropped and reordered
answers, a new token, a missing hydration, a disconnect and a stall. Most tests
drive the sessions on the calling thread, as one generator process does; the
multi-process ones go through :class:`~reflex_bench.drivers.events.LoadRunner`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import multiprocessing
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import pytest
from reflex_bench.drivers import events
from reflex_bench.drivers.app_process import free_ports
from reflex_bench.drivers.echo_server import EchoServer
from reflex_bench.drivers.events import (
    EventShape,
    GeneratorSaturated,
    LoadError,
    LoadPlan,
    LoadResult,
    LoadRunner,
    decode,
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
# Captured from the playground: HEAD leaves empty fields out, 0.8.23 does not.
HEAD_REPLY = f'42/_event,["event",{{"delta":{{"{STATE}":{{"{SEQ_VAR}":7}}}}}}]'
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
        "backend_url": url,
        "reflex_version": "0.9.12",
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

    loop = events._event_loop()
    try:
        shard = loop.run_until_complete(
            events._run_sessions(load, range(load.sessions), start)
        )
    finally:
        loop.close()
    return events._merge(load, [shard])


class Scripted(EchoServer):
    """An echo server that records the seq events and asks a hook about each."""

    def __init__(self) -> None:
        """Record nothing yet."""
        super().__init__(delta_key=STATE, seq_var=SEQ_VAR)
        self.seqs: list[int] = []
        self.tokens: list[str] = []

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


def test_event_url():
    assert (
        events.event_url("http://localhost:8000", "tok")
        == "ws://localhost:8000/_event/?EIO=4&transport=websocket&token=tok"
    )
    assert events.event_url("https://app.example.com/", "tok").startswith(
        "wss://app.example.com/_event/?"
    )


def test_event_frames_always_carry_the_token():
    # 0.8.23 rejects an event without a token and HEAD ignores it, so every
    # frame carries it.
    frame = events.event_frame(f"{STATE}.set_seq", {"seq": 7}, token="tok")
    assert frame == (
        f'42/_event,["event",{{"name":"{STATE}.set_seq","payload":{{"seq":7}},'
        '"router_data":{"pathname":"/","asPath":"/","query":{}},"token":"tok"}]'
    )
    frames = events._Frames(SHAPE, "tok", "/")
    assert frames.event(7) == frame
    assert decode(frames.event(8)).data[1]["payload"] == {"seq": 8}


def test_decode_the_handshake():
    opened = decode(
        '0{"sid":"abc","upgrades":[],"pingTimeout":120000,"pingInterval":25000,"maxPayload":1000000}'
    )
    assert opened.kind == "open"
    assert opened.data["pingInterval"] == 25000
    assert decode(events.CONNECT_FRAME) == events.Packet("connect", "/_event")
    ack = decode('40/_event,{"sid":"xyz"}')
    assert ack == events.Packet("connect", "/_event", {"sid": "xyz"})
    refused = decode('44/_event,{"message":"Unable to connect"}')
    assert refused == events.Packet(
        "connect_error", "/_event", {"message": "Unable to connect"}
    )


def test_decode_pings_disconnects_and_events():
    assert decode("2").kind == "ping"
    assert decode(events.PONG).kind == "pong"
    assert decode("1").kind == "close"
    assert decode("6").kind == "noop"
    assert decode(events.DISCONNECT_FRAME) == events.Packet("disconnect", "/_event")
    assert decode('42/_event,["new_token","fresh"]') == events.Packet(
        "event", "/_event", ["new_token", "fresh"]
    )
    # The default namespace has no prefix.
    assert decode('42["event",{}]').namespace == "/"


def test_decode_rejects_binary_packets():
    with pytest.raises(events.ProtocolError, match="binary"):
        decode(b"\x00\x01")
    with pytest.raises(events.ProtocolError, match="binary"):
        decode('451-/_event,["event",{"_placeholder":true,"num":0}]')


def test_replies_of_both_versions_carry_the_same_delta():
    for reply in (HEAD_REPLY, OLD_REPLY):
        name, update = decode(reply).data
        assert name == "event"
        assert update["delta"] == {STATE: {SEQ_VAR: 7}}


def test_the_plan_checks_its_rate():
    with pytest.raises(ValueError, match="positive rate"):
        plan("http://localhost:8000", rate=None)
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


def test_every_event_is_answered():
    server = Scripted()
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


def test_a_reordered_pair_counts_out_of_order():
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

    with serving(Reordering()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0, warmup_s=0.0))
    # Seq 6 arrived while 5 was outstanding: 5 counts as unanswered, and its
    # late answer does not resolve it.
    assert result.out_of_order == 2
    assert result.unanswered == 2
    assert result.answered == result.sent - 2


def test_a_new_token_is_adopted():
    class Renaming(Scripted):
        """Hands every connection a new token, as reflex does for a duplicate tab."""

        async def on_connect(self, ws, sid):
            """Send the new token before the namespace ack, like python-socketio."""
            await ws.send(events.emit_frame("new_token", f"fresh-{sid}"))
            await super().on_connect(ws, sid)

    server = Renaming()
    with serving(server) as url:
        result = run_inline(plan(url, sessions=1, rate=20.0))
    assert result.unanswered == 0
    assert server.tokens
    assert all(token.startswith("fresh-") for token in server.tokens)


def test_a_session_that_never_hydrates_fails(monkeypatch: pytest.MonkeyPatch):
    class NeverHydrated(Scripted):
        """Ignores on_load_internal, so is_hydrated never becomes true."""

        async def on_event(self, ws, event):
            """Answer everything but on_load_internal."""
            if event["name"] != events.ON_LOAD_EVENT:
                await super().on_event(ws, event)

    monkeypatch.setattr(events, "PRIME_TIMEOUT_S", 0.5)
    with serving(NeverHydrated()) as url:
        result = run_inline(plan(url, sessions=1))
    assert result.sent == 0
    assert len(result.session_errors) == 1
    assert "not hydrated within 0.5 s" in result.session_errors[0]


def test_a_disconnect_mid_run_fails_the_session():
    class Disconnecting(Scripted):
        """Ends the namespace of the first connection instead of answering seq 5."""

        def __init__(self) -> None:
            """Know no connection yet."""
            super().__init__()
            self.first: ServerConnection | None = None

        async def seq_event(self, ws, event, seq):
            """Disconnect the first connection at seq 5.

            Returns:
                Whether to answer.
            """
            if self.first is None:
                self.first = ws
            if ws is self.first and seq == 5:
                await ws.send(events.DISCONNECT_FRAME)
                return False
            return True

    with serving(Disconnecting()) as url:
        result = run_inline(plan(url, sessions=2, rate=40.0, warmup_s=0.0))
    assert len(result.session_errors) == 1
    assert "disconnected" in result.session_errors[0]
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
    assert result.answered_rate == pytest.approx(result.answered / 0.5)
    assert result.histogram["of"] == "service_s"


def healthy(**overrides: Any) -> LoadResult:
    return make_load_result(reply_frame=HEAD_REPLY, **overrides)


SLOW = {"p50": 0.03, "p90": 0.05, "p99": 0.06, "p999": 0.07, "max": 0.08}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        # 1 ms is the floor of the lag limit...
        ({"lag_s": {"p50": 1e-4, "p99": 0.0015, "max": 0.002}}, "send lag p99"),
        # ...which grows to 10 % of the median response.
        (
            {"lag_s": {"p50": 1e-4, "p99": 0.004, "max": 0.005}, "response_s": SLOW},
            "send lag p99",
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
    assert healthy(lag_s=lag, response_s=SLOW).check() is None


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
