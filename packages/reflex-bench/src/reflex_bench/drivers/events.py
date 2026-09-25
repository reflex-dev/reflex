"""An open-loop event generator that speaks reflex's socket.io protocol over ``websockets``.

It measures what a user of a reflex app waits for: the time from the moment an
event *should* have been sent until the state delta that answers it arrives.

**Protocol.** reflex mounts python-socketio at ``/_event`` with the websocket
transport only (engine.io 4, socket.io 5), from 0.8.23 to HEAD. One session is
one websocket, one token and one state::

    client  GET /_event/?EIO=4&transport=websocket&token=<uuid4>
    server  0{"sid":...,"upgrades":[],"pingInterval":25000,"pingTimeout":...}
    client  40/_event,                            join the namespace
    server  40/_event,{"sid":...}                 (a "new_token" event may come first)
    client  42/_event,["event",{"name":...,"payload":...,"router_data":...,"token":...}]
    server  42/_event,["event",{"delta":{...}}]   (0.8.23 adds "events" and "final")
    server  2   client  3                         engine.io ping and pong
    client  41/_event,                            leave the namespace

A session is primed like a page load, with ``hydrate`` and ``on_load_internal``,
until a delta sets ``is_hydrated``. Every event carries the token: 0.8.23
requires it, HEAD ignores it.

**Open and closed loop.** In the open loop each session sends on a fixed
schedule whatever the server does, late events are sent at once (never
skipped), and latency counts from the *planned* send time, so a stall shows in
every event it delays: there is no coordinated omission. The closed loop sends
the next event when the previous one is answered; it measures capacity and
service time, never user latency.

**Correlation.** Each event carries a sequence number that the answering delta
echoes (:class:`EventShape`); per session the numbers increase. A delta for
``N`` while a lower number is outstanding counts as out of order, and the lower
numbers count as unanswered. Events without an answer by the end of the drain
count as unanswered; none is dropped.

**Processes.** :class:`LoadRunner` shards the sessions round-robin over spawned
processes with one event loop each, starts their schedules together once every
session is primed, and merges what they measured into a :class:`LoadResult`.
:func:`open_sessions` primes sessions on the caller's loop without a load, for
measurements of idle sessions; :func:`hold_sessions` does the same in a spawned
process and keeps them open until told to close.
"""

from __future__ import annotations

import array
import asyncio
import collections
import contextlib
import dataclasses
import json
import math
import multiprocessing
import multiprocessing.connection
import os
import select
import selectors
import signal
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any, Literal

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from reflex_bench import stats

if sys.platform != "win32":
    import resource

Mode = Literal["open", "closed"]

NAMESPACE = "/_event"
ROOT_STATE = "reflex___state____state"
HYDRATE_EVENT = f"{ROOT_STATE}.hydrate"
ON_LOAD_EVENT = (
    f"{ROOT_STATE}.reflex___state____on_load_internal_state.on_load_internal"
)
HYDRATED_VAR = "is_hydrated_rx_state_"
OPEN_PREFIX = "0"
CLOSE = "1"
PING = "2"
PONG = "3"
CONNECT_FRAME = f"40{NAMESPACE},"
DISCONNECT_FRAME = f"41{NAMESPACE},"
EVENT_PREFIX = f"42{NAMESPACE},"
CONNECT_ERROR_PREFIX = f"44{NAMESPACE},"

PRIME_TIMEOUT_S = 30.0
PRIME_CONCURRENCY = 64
MAX_FRAME_BYTES = 2**24
# Between the start signal and the first planned send, so every process gets it.
START_DELAY_S = 0.05
READY_MARGIN_S = 60.0
RESULT_MARGIN_S = 30.0
KILL_GRACE_S = 5.0

CPU_LIMIT = 0.75
LAG_FLOOR_S = 1e-3
LAG_SHARE = 0.1
SEND_RATE_SHARE = 0.98

HISTOGRAM_LO_S = 1e-5
HISTOGRAM_HI_S = 100.0
HISTOGRAM_BUCKETS = 120
RESPONSE_PERCENTILES = {"p50": 50, "p90": 90, "p99": 99, "p999": 99.9, "max": 100}
SERVICE_PERCENTILES = {"p50": 50, "p99": 99, "max": 100}
PRIME_PERCENTILES = {"p50": 50, "max": 100}


class ProtocolError(Exception):
    """The server sent a frame the generator does not speak."""


class LoadError(RuntimeError):
    """The load did not run: sessions could not start, a generator process failed, or it was stopped."""


def emit_frame(*args: Any) -> str:
    """Encode a socket.io event on reflex's namespace.

    Args:
        *args: The event name and its arguments.

    Returns:
        ``42/_event,[name, ...]``.
    """
    return EVENT_PREFIX + json.dumps(list(args), separators=(",", ":"))


def event_frame(
    name: str, payload: Mapping[str, Any] | None, *, token: str, pathname: str = "/"
) -> str:
    """Encode an event as the reflex frontend sends it.

    Args:
        name: The full event handler name.
        payload: The handler's arguments.
        token: The session's token.
        pathname: The page route the event comes from.

    Returns:
        The frame.
    """
    router_data = {"pathname": pathname, "asPath": pathname, "query": {}}
    return emit_frame(
        "event",
        {"name": name, "payload": payload, "router_data": router_data, "token": token},
    )


def event_url(backend_url: str, token: str) -> str:
    """Build the websocket URL of a session.

    Args:
        backend_url: The backend's URL, e.g. ``http://localhost:8000``.
        token: The session's token.

    Returns:
        E.g. ``ws://localhost:8000/_event/?EIO=4&transport=websocket&token=<token>``.
    """
    parts = urllib.parse.urlsplit(backend_url)
    query = urllib.parse.urlencode({"EIO": 4, "transport": "websocket", "token": token})
    return urllib.parse.urlunsplit((
        "wss" if parts.scheme == "https" else "ws",
        parts.netloc,
        f"{parts.path.rstrip('/')}{NAMESPACE}/",
        query,
        "",
    ))


def seq_payload(seq: int) -> dict[str, int]:
    """Build the payload of the playground's ``set_seq*`` handlers.

    Args:
        seq: The sequence number.

    Returns:
        ``{"seq": seq}``.
    """
    return {"seq": seq}


def schedule_ns(index: int, sessions: int, rate: float, span_ns: int) -> Iterator[int]:
    """Yield the planned send times of one session of an open loop.

    Sessions share the rate evenly and are offset by ``1 / rate``, so the
    events of all sessions together are evenly spaced.

    Args:
        index: The session's index.
        sessions: The number of sessions.
        rate: The total offered rate, in events per second.
        span_ns: The length of the schedule.

    Yields:
        Nanoseconds after the start, below ``span_ns``.
    """
    interval = sessions * 1e9 / rate
    offset = index * 1e9 / rate
    step = 0
    while (at := int(offset + step * interval)) < span_ns:
        yield at
        step += 1


def raise_fd_limit(connections: int) -> None:
    """Let this process, and the processes it starts, hold a socket per connection.

    Args:
        connections: How many sockets are needed, besides a margin.
    """
    if sys.platform == "win32":
        return
    wanted = connections + 256
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft != resource.RLIM_INFINITY and soft < wanted:
        limit = wanted if hard == resource.RLIM_INFINITY else min(wanted, hard)
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))


@dataclass(frozen=True)
class EventShape:
    """What one benchmark event looks like on the wire.

    Attributes:
        name: The full event handler name, e.g.
            ``reflex___state____state.playground___state____bench_state.set_seq``.
        payload: Builds the payload from the sequence number. Plans are pickled
            into the generator processes, so it must be a module-level function,
            such as :func:`seq_payload`.
        delta_key: The state whose delta echoes the sequence number.
        seq_var: The var that echoes it, e.g. ``last_seq_rx_state_``.
        ordered: Whether the server answers a session's events in the order
            they were sent. Then an answer that overtakes an outstanding event
            means that event's answer was lost; background tasks, which may
            finish in any order, set it to ``False``.
    """

    name: str
    payload: Callable[[int], dict[str, Any]]
    delta_key: str
    seq_var: str
    ordered: bool = True


@dataclass(frozen=True)
class Endpoint:
    """Where sessions connect: a reflex backend and the page they load.

    The protocol is the same from 0.8.23 to HEAD (every event carries the
    token), so nothing here depends on the reflex version.

    Attributes:
        backend_url: The backend's URL, e.g. ``http://localhost:8000``.
        pathname: The page route the sessions hydrate and send events from.
    """

    backend_url: str
    pathname: str = "/"


@dataclass(frozen=True, kw_only=True)
class LoadPlan:
    """One load run.

    Attributes:
        endpoint: The backend and page the sessions connect to.
        shape: The event every session sends.
        sessions: The number of sessions (browser tabs).
        mode: ``open`` sends on a schedule, ``closed`` after each answer.
        rate: The total offered rate of the open loop, in events per second;
            ``None`` for the closed loop.
        warmup_s: Seconds of load before the measured window; not measured.
        duration_s: The measured window.
        drain_s: Seconds after the window to wait for outstanding answers.
        processes: The number of generator processes.
        cpus: The CPUs of the generator processes (Linux), or ``None``.
    """

    endpoint: Endpoint
    shape: EventShape
    sessions: int
    mode: Mode
    rate: float | None
    warmup_s: float
    duration_s: float
    drain_s: float = 5.0
    processes: int = 1
    cpus: Sequence[int] | None = None

    def __post_init__(self) -> None:
        """Check the plan.

        Raises:
            ValueError: On a rate that does not fit the mode, more processes than
                sessions, or negative times.
        """
        if self.mode == "open" and not (self.rate and self.rate > 0):
            msg = "an open loop needs a positive rate"
            raise ValueError(msg)
        if self.mode == "closed" and self.rate is not None:
            msg = "a closed loop sends as fast as it is answered and takes no rate"
            raise ValueError(msg)
        if not 1 <= self.processes <= self.sessions:
            msg = f"{self.processes} processes for {self.sessions} sessions: need at least one session per process"
            raise ValueError(msg)
        if self.duration_s <= 0 or self.warmup_s < 0 or self.drain_s < 0:
            msg = "duration must be positive, warmup and drain not negative"
            raise ValueError(msg)


@dataclass(frozen=True)
class LoadResult:
    """What one load run measured; JSON-ready, without per-event data.

    Latencies are in seconds, as percentile maps (``p50``, ``p99``, ``max``, ...).
    Only events planned (open loop) or sent (closed loop) in the measured window
    count. The rates count what happened within the window; the drain after it
    only decides which events are ``unanswered``.

    Attributes:
        sessions: The number of sessions.
        mode: ``open`` or ``closed``.
        processes: The number of generator processes.
        cpus: The CPUs of the generator processes, or ``None``.
        warmup_s: The warmup before the window.
        duration_s: The length of the window.
        offered_rate: The planned rate (open loop), or ``None``.
        achieved_send_rate: Events sent within the window per second.
        answered_rate: Answers that arrived within the window per second: the
            throughput, ``sum(answered_per_second) / duration_s``.
        sent: The events sent.
        answered: The events answered by the end of the drain.
        answered_per_second: Answers that arrived in each second of the window:
            entry ``i`` counts those ``i`` to ``i + 1`` seconds after it
            started, merged over processes.
        unanswered: The events sent but not answered by the end of the drain.
        out_of_order: The answers that arrived while a lower sequence number
            was outstanding.
        session_errors: Why sessions failed, one entry per failed session.
        response_s: Answer time minus planned send time: the latency a user
            sees. Open loop only.
        service_s: Answer time minus actual send time.
        lag_s: Actual minus planned send time: how late the generator was.
            Open loop only.
        generator_cpu_fraction: The busiest generator process's CPU seconds per
            second of the window.
        prime_s: The time sessions took to connect and hydrate.
        histogram: Counts of the latencies in ``of`` (``response_s`` or
            ``service_s``) in log-spaced buckets from ``lo_s`` to ``hi_s``, so
            runs can be pooled for display.
        reply_frame: One raw frame that answered an event, for inspection.
    """

    sessions: int
    mode: Mode
    processes: int
    cpus: list[int] | None
    warmup_s: float
    duration_s: float
    offered_rate: float | None
    achieved_send_rate: float
    answered_rate: float
    sent: int
    answered: int
    answered_per_second: list[int]
    unanswered: int
    out_of_order: int
    session_errors: list[str]
    response_s: dict[str, float] | None
    service_s: dict[str, float] | None
    lag_s: dict[str, float] | None
    generator_cpu_fraction: float
    prime_s: dict[str, float] | None
    histogram: dict[str, Any]
    reply_frame: str | None

    def check(self) -> str | None:
        """Check that the generator kept up, so the result measures the server.

        The rules judge the generator alone: the send lag is actual minus
        planned send time, whatever the server did, and a lag tail inflates the
        response tail by as much.

        Returns:
            ``None``, or why the generator was saturated: a process used more
            than 75 % of a core, or, in the open loop, the send lag p99
            exceeded the larger of 1 ms and 10 % of the median response, or
            fewer than 98 % of the offered events went out in the window.
        """
        if self.generator_cpu_fraction > CPU_LIMIT:
            return (
                f"generator saturated: a generator process used"
                f" {100 * self.generator_cpu_fraction:.0f} % of a core"
                f" (limit {100 * CPU_LIMIT:.0f} %)"
            )
        if self.mode != "open":
            return None
        if self.lag_s is not None and self.response_s is not None:
            limit = max(LAG_FLOOR_S, LAG_SHARE * self.response_s["p50"])
            if self.lag_s["p99"] > limit:
                return (
                    f"generator saturated: send lag p99 {1e3 * self.lag_s['p99']:.2f} ms"
                    f" exceeds {1e3 * limit:.2f} ms (the larger of 1 ms and 10 % of"
                    " the median response)"
                )
        if (
            self.offered_rate is not None
            and self.achieved_send_rate < SEND_RATE_SHARE * self.offered_rate
        ):
            return (
                f"generator saturated: sent {self.achieved_send_rate:.0f} ev/s of the"
                f" {self.offered_rate:.0f} ev/s offered (under {100 * SEND_RATE_SHARE:.0f} %)"
            )
        return None

    def to_dict(self) -> dict[str, Any]:
        """Describe the result for a sample's extra data.

        Returns:
            Every field.
        """
        return dataclasses.asdict(self)

    def summary(self) -> dict[str, Any]:
        """Describe the result without its arrays.

        Returns:
            Every field but the histogram and the per-second counts.
        """
        return {
            name: value
            for name, value in self.to_dict().items()
            if name not in {"histogram", "answered_per_second"}
        }


class GeneratorSaturated(RuntimeError):  # noqa: N818 - the name states the verdict
    """The generator fell behind, so its result would measure the generator, not the server."""

    def __init__(self, reason: str, result: LoadResult) -> None:
        """Describe the failure with the result attached.

        Args:
            reason: What :meth:`LoadResult.check` found.
            result: The result.
        """
        super().__init__(f"{reason}; result: {json.dumps(result.summary())}")
        self.result = result


class _Frames:
    """Encodes a session's events; only the payload changes between them."""

    def __init__(self, shape: EventShape, token: str, pathname: str) -> None:
        """Split the event frame around its payload.

        Args:
            shape: The event.
            token: The session's token.
            pathname: The page route.
        """
        self._payload = shape.payload
        template = event_frame(shape.name, None, token=token, pathname=pathname)
        head, marker, self._tail = template.partition('"payload":null')
        self._head = head + marker.removesuffix("null")

    def event(self, seq: int) -> str:
        """Encode one event.

        Args:
            seq: Its sequence number.

        Returns:
            The frame.
        """
        payload = json.dumps(self._payload(seq), separators=(",", ":"))
        return f"{self._head}{payload}{self._tail}"


class _Session:
    """One simulated browser tab: a websocket, a token and the events it sent.

    The arrays hold one entry per sent event, indexed by sequence number - 1;
    ``answered`` is 0 until the answering delta arrives.
    """

    def __init__(
        self, index: int, endpoint: Endpoint, shape: EventShape | None
    ) -> None:
        """Prepare the session; :meth:`prime` connects it.

        Args:
            index: The session's index among all sessions.
            endpoint: Where to connect.
            shape: The event it sends, or ``None`` for a session that only
                hydrates and stays open.
        """
        self.index = index
        self.endpoint = endpoint
        self.shape = shape
        self.token = str(uuid.uuid4())
        self.frames = self._frames()
        self.ws: ClientConnection | None = None
        self.error: str | None = None
        self.prime_ns: int | None = None
        self.reply_frame: str | None = None
        self.planned = array.array("q")
        self.sent = array.array("q")
        self.answered = array.array("q")
        self.outstanding: collections.deque[int] = collections.deque()
        self.first_measured = sys.maxsize
        self.out_of_order = 0
        self._hydrated = asyncio.Event()
        self._idle = asyncio.Event()
        self._reader: asyncio.Task[None] | None = None
        self._closing = False

    def _frames(self) -> _Frames | None:
        """Encode the session's events with its current token.

        Returns:
            The encoder, or ``None`` for a session without events.
        """
        if self.shape is None:
            return None
        return _Frames(self.shape, self.token, self.endpoint.pathname)

    def _fail(self, reason: str) -> None:
        """Mark the session failed and wake whatever waits on it.

        Args:
            reason: Why; only the first reason is kept.
        """
        if self.error is None:
            self.error = reason
        self._hydrated.set()
        self._idle.set()

    async def prime(self, gate: asyncio.Semaphore) -> None:
        """Connect, join the namespace and hydrate like a page load; failures are recorded.

        Args:
            gate: Limits how many sessions connect at once.
        """
        async with gate:
            try:
                await asyncio.wait_for(self._open(), PRIME_TIMEOUT_S)
            except asyncio.TimeoutError:
                self._fail(f"not hydrated within {PRIME_TIMEOUT_S:g} s")
            except Exception as exc:
                self._fail(f"could not connect: {type(exc).__name__}: {exc}")

    async def _open(self) -> None:
        """Run the handshake and the hydration events.

        Raises:
            ProtocolError: When the server does not open or refuses the namespace.
            ConnectionError: When the session failed while hydrating.
        """
        started = time.perf_counter_ns()
        ws = self.ws = await connect(
            event_url(self.endpoint.backend_url, self.token),
            proxy=None,
            open_timeout=None,
            max_size=MAX_FRAME_BYTES,
            ping_interval=None,
            close_timeout=1,
        )
        opened = await ws.recv()
        if not (isinstance(opened, str) and opened.startswith(OPEN_PREFIX)):
            msg = f"the server did not open an engine.io session: {opened[:40]!r}"
            raise ProtocolError(msg)
        await ws.send(CONNECT_FRAME)
        while True:
            message = await ws.recv()
            if isinstance(message, str):
                if message.startswith(EVENT_PREFIX):
                    # python-socketio sends events of the connect handler first.
                    self._on_emit(json.loads(message[len(EVENT_PREFIX) :]), message, 0)
                    continue
                if message.startswith(CONNECT_FRAME):
                    break
                if message.startswith(CONNECT_ERROR_PREFIX):
                    reason = message[len(CONNECT_ERROR_PREFIX) :]
                    msg = f"the server refused {NAMESPACE}: {reason}"
                    raise ProtocolError(msg)
                if message == PING:
                    await ws.send(PONG)
                    continue
            msg = f"unexpected frame in the handshake: {message[:40]!r}"
            raise ProtocolError(msg)
        self._reader = asyncio.create_task(self._read())
        pathname = self.endpoint.pathname
        await ws.send(
            event_frame(HYDRATE_EVENT, {}, token=self.token, pathname=pathname)
        )
        await ws.send(
            event_frame(ON_LOAD_EVENT, {}, token=self.token, pathname=pathname)
        )
        await self._hydrated.wait()
        if self.error is not None:
            raise ConnectionError(self.error)
        self.prime_ns = time.perf_counter_ns() - started

    async def _read(self) -> None:
        """Receive frames until the websocket closes: answers, pings, tokens and disconnects."""
        ws = self.ws
        assert ws is not None
        start = len(EVENT_PREFIX)
        try:
            async for message in ws:
                now = time.perf_counter_ns()
                if isinstance(message, str) and message.startswith(EVENT_PREFIX):
                    self._on_emit(json.loads(message[start:]), message, now)
                elif message == PING:
                    await ws.send(PONG)
                elif message in {DISCONNECT_FRAME, CLOSE}:
                    self._fail(f"the server disconnected the session ({message!r})")
                    return
                else:
                    self._fail(f"unexpected frame: {message[:40]!r}")
                    return
        except ConnectionClosed as exc:
            if not self._closing:
                self._fail(f"the websocket closed: {exc}")
        except ValueError as exc:
            self._fail(f"{type(exc).__name__}: {exc}")
        else:
            if not self._closing:
                self._fail("the websocket closed")

    def _on_emit(self, args: list[Any], frame: str, now: int) -> None:
        """Handle a socket.io event from the server.

        Args:
            args: The event name and arguments.
            frame: The raw frame.
            now: When it arrived.
        """
        name = args[0]
        if name == "event":
            delta = args[1].get("delta")
            if not delta:
                return
            shape = self.shape
            if (
                shape is not None
                and (state := delta.get(shape.delta_key)) is not None
                and (seq := state.get(shape.seq_var))
            ):
                if self.reply_frame is None:
                    self.reply_frame = frame
                self._answer(seq, now)
            if (
                not self._hydrated.is_set()
                and (root := delta.get(ROOT_STATE))
                and root.get(HYDRATED_VAR) is True
            ):
                self._hydrated.set()
        elif name == "new_token":
            # The token was in use by another session; reflex hands out a new one.
            self.token = args[1]
            self.frames = self._frames()
        elif name == "reload":
            # 0.8.23: the server lost the session's state and dropped the event.
            self._fail("the server asked the page to reload")

    def _answer(self, seq: int, now: int) -> None:
        """Match an answer to the outstanding event with its sequence number.

        Args:
            seq: The echoed sequence number.
            now: When the answer arrived.
        """
        outstanding = self.outstanding
        if not outstanding or seq < outstanding[0] or seq > len(self.sent):
            # A late answer to an event already counted as unanswered, or a repeat.
            return
        if seq == outstanding[0]:
            outstanding.popleft()
        else:
            assert self.shape is not None
            if self.shape.ordered:
                # The events before it lost their answers.
                while outstanding[0] != seq:
                    outstanding.popleft()
                outstanding.popleft()
            elif seq in outstanding:
                # It finished before an earlier event, which stays outstanding.
                outstanding.remove(seq)
            else:
                return
            if seq >= self.first_measured:
                self.out_of_order += 1
        self.answered[seq - 1] = now
        if not outstanding:
            self._idle.set()

    def _record(self, seq: int, planned: int, sent: int, measure_from: int) -> None:
        """Record an event about to be sent.

        Args:
            seq: Its sequence number.
            planned: When it was planned.
            sent: When it is sent.
            measure_from: The start of the measured window.
        """
        if planned >= measure_from and seq < self.first_measured:
            self.first_measured = seq
        self.planned.append(planned)
        self.sent.append(sent)
        self.answered.append(0)
        self.outstanding.append(seq)

    async def run(
        self, plan: LoadPlan, t0: int, measure_from: int, end: int, drain_until: int
    ) -> None:
        """Send the events of the plan's loop, then wait for the outstanding answers.

        Args:
            plan: The load plan.
            t0: The start of the schedule.
            measure_from: The start of the measured window.
            end: The end of the window, when sending stops.
            drain_until: When to stop waiting for answers.
        """
        try:
            if plan.mode == "open":
                await self._send_open(plan, t0, measure_from, end)
            else:
                timeout = (drain_until - time.perf_counter_ns()) / 1e9
                await asyncio.wait_for(
                    self._send_closed(t0, measure_from, end), timeout
                )
            await self._drain(drain_until)
        except asyncio.TimeoutError:
            # The closed loop's last event stays unanswered.
            pass
        except ConnectionClosed as exc:
            self._fail(f"the websocket closed: {exc}")

    async def _send_open(
        self, plan: LoadPlan, t0: int, measure_from: int, end: int
    ) -> None:
        """Send on the session's schedule; late events go out at once.

        Args:
            plan: The load plan.
            t0: The start of the schedule.
            measure_from: The start of the measured window.
            end: The end of the window.
        """
        assert plan.rate is not None
        ws = self.ws
        frames = self.frames
        assert ws is not None
        assert frames is not None
        clock = time.perf_counter_ns
        schedule = schedule_ns(self.index, plan.sessions, plan.rate, end - t0)
        for seq, offset in enumerate(schedule, start=1):
            planned = t0 + offset
            now = clock()
            while now < planned:
                await asyncio.sleep((planned - now) / 1e9)
                now = clock()
            if self.error is not None:
                return
            self._record(seq, planned, now, measure_from)
            await ws.send(frames.event(seq))

    async def _send_closed(self, t0: int, measure_from: int, end: int) -> None:
        """Send the next event once the previous one is answered, until the window ends.

        Args:
            t0: The start.
            measure_from: The start of the measured window.
            end: The end of the window.
        """
        ws = self.ws
        frames = self.frames
        assert ws is not None
        assert frames is not None
        idle = self._idle
        clock = time.perf_counter_ns
        await asyncio.sleep(max(0, t0 - clock()) / 1e9)
        seq = 0
        while self.error is None and (now := clock()) < end:
            seq += 1
            self._record(seq, now, now, measure_from)
            idle.clear()
            await ws.send(frames.event(seq))
            await idle.wait()

    async def _drain(self, until: int) -> None:
        """Wait until every sent event is answered, the session fails or time is up.

        Args:
            until: When to give up.
        """
        while self.outstanding and self.error is None:
            remaining = (until - time.perf_counter_ns()) / 1e9
            if remaining <= 0:
                return
            self._idle.clear()
            if not self.outstanding:
                return
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._idle.wait(), remaining)

    async def close(self) -> None:
        """Leave the namespace and close the websocket."""
        self._closing = True
        ws = self.ws
        if ws is not None:
            if self.error is None:
                with contextlib.suppress(ConnectionClosed):
                    await ws.send(DISCONNECT_FRAME)
            await ws.close()
        if self._reader is not None:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader


class SessionPool:
    """Sessions on the running event loop, primed together and closed together.

    Priming connects each session and hydrates it like a page load; a session
    that fails records why instead of raising. Between :meth:`prime` and
    :meth:`close` the sessions stay open and answer the server's pings.
    """

    def __init__(
        self,
        endpoint: Endpoint,
        indices: Iterable[int],
        shape: EventShape | None = None,
    ) -> None:
        """Prepare the sessions; nothing connects yet.

        Args:
            endpoint: Where they connect.
            indices: Their indices among all sessions of a load.
            shape: The event they send, or ``None`` for idle sessions.
        """
        self.sessions = [_Session(index, endpoint, shape) for index in indices]

    @property
    def errors(self) -> list[str]:
        """Describe the sessions that failed.

        Returns:
            ``session <index>: <reason>`` per failed session, so far.
        """
        return [f"session {s.index}: {s.error}" for s in self.sessions if s.error]

    async def prime(self) -> None:
        """Connect and hydrate every session, up to ``PRIME_CONCURRENCY`` at a time."""
        gate = asyncio.Semaphore(PRIME_CONCURRENCY)
        await asyncio.gather(*(session.prime(gate) for session in self.sessions))

    async def close(self) -> None:
        """Leave the namespace and close every websocket."""
        await asyncio.gather(*(session.close() for session in self.sessions))


@contextlib.asynccontextmanager
async def open_sessions(
    endpoint: Endpoint, count: int, shape: EventShape | None = None
) -> AsyncIterator[SessionPool]:
    """Prime sessions on the running loop and close them when the context ends.

    Args:
        endpoint: Where they connect.
        count: How many.
        shape: The event they send, or ``None`` for idle sessions.

    Yields:
        The primed pool; check its ``errors``.
    """
    pool = SessionPool(endpoint, range(count), shape)
    try:
        await pool.prime()
        yield pool
    finally:
        await pool.close()


@dataclass
class _Shard:
    """What one generator process measured, sent back to the parent.

    Attributes:
        sessions: The number of sessions.
        errors: Why sessions failed.
        prime_ns: The priming times of the primed sessions.
        sent: The measured events sent.
        sent_in_window: Those sent before the window ended.
        answered: Those answered.
        answered_per_second: Those answered before the window ended, per second
            of the window.
        out_of_order: Answers that overtook an outstanding event.
        response_ns: Answer minus planned send time, per answered event.
        service_ns: Answer minus actual send time, per answered event.
        lag_ns: Actual minus planned send time, per sent event.
        cpu_fraction: The process's CPU seconds per second of the window.
        reply_frame: One frame that answered an event.
    """

    sessions: int
    errors: list[str]
    prime_ns: list[int]
    sent: int = 0
    sent_in_window: int = 0
    answered: int = 0
    answered_per_second: list[int] = dataclasses.field(default_factory=list)
    out_of_order: int = 0
    response_ns: array.array = dataclasses.field(
        default_factory=lambda: array.array("q")
    )
    service_ns: array.array = dataclasses.field(
        default_factory=lambda: array.array("q")
    )
    lag_ns: array.array = dataclasses.field(default_factory=lambda: array.array("q"))
    cpu_fraction: float = 0.0
    reply_frame: str | None = None

    def add(self, session: _Session, measure_from: int, end: int) -> None:
        """Add a session's measured events.

        Args:
            session: The session.
            measure_from: The start of the measured window.
            end: Its end.
        """
        self.out_of_order += session.out_of_order
        if self.reply_frame is None:
            self.reply_frame = session.reply_frame
        planned, sent, answered = session.planned, session.sent, session.answered
        per_second = self.answered_per_second
        for index in range(session.first_measured - 1, len(sent)):
            sent_at = sent[index]
            self.sent += 1
            self.sent_in_window += sent_at < end
            self.lag_ns.append(sent_at - planned[index])
            if received := answered[index]:
                self.answered += 1
                self.service_ns.append(received - sent_at)
                self.response_ns.append(received - planned[index])
                if received < end:
                    per_second[(received - measure_from) // 1_000_000_000] += 1


async def _run_sessions(
    plan: LoadPlan,
    indices: Iterable[int],
    start: Callable[[list[str]], Awaitable[int | None]],
) -> _Shard:
    """Prime some sessions, run them from a common start, and measure them.

    Args:
        plan: The load plan.
        indices: The sessions of this process.
        start: Given the priming errors, returns the start of the schedule
            (a ``perf_counter_ns`` time), or ``None`` to stop.

    Returns:
        The measurements.
    """
    pool = SessionPool(plan.endpoint, indices, plan.shape)
    await pool.prime()
    sessions = pool.sessions
    shard = _Shard(
        sessions=len(sessions),
        errors=[],
        prime_ns=[s.prime_ns for s in sessions if s.prime_ns is not None],
        answered_per_second=[0] * math.ceil(plan.duration_s),
    )
    try:
        t0 = await start(pool.errors)
        if t0 is not None:
            measure_from = t0 + int(plan.warmup_s * 1e9)
            end = measure_from + int(plan.duration_s * 1e9)
            drain_until = end + int(plan.drain_s * 1e9)
            shard.cpu_fraction = await _measure_cpu(
                asyncio.gather(
                    *(s.run(plan, t0, measure_from, end, drain_until) for s in sessions)
                ),
                measure_from,
                end,
            )
            for session in sessions:
                shard.add(session, measure_from, end)
    finally:
        await pool.close()
    shard.errors = pool.errors
    return shard


async def _measure_cpu(work: Awaitable[Any], start: int, end: int) -> float:
    """Run work and measure this process's CPU use between two times.

    Args:
        work: The work.
        start: The start of the measured window.
        end: Its end.

    Returns:
        CPU seconds per second of the window (or of the part that ran).
    """
    loop = asyncio.get_running_loop()
    marks: list[tuple[int, float]] = []

    def mark() -> None:
        marks.append((time.perf_counter_ns(), time.process_time()))

    now = time.perf_counter_ns()
    handles = [loop.call_later(max(0, at - now) / 1e9, mark) for at in (start, end)]
    try:
        await work
    finally:
        for handle in handles:
            handle.cancel()
    if not marks:
        return 0.0
    if len(marks) == 1:
        mark()
    (wall0, cpu0), (wall1, cpu1) = marks
    return (cpu1 - cpu0) / ((wall1 - wall0) / 1e9) if wall1 > wall0 else 0.0


if sys.platform == "linux":

    class _PreciseEpollSelector(selectors.EpollSelector):
        """An epoll selector whose timeouts have microsecond precision.

        ``epoll_wait`` counts whole milliseconds, so asyncio timers would fire
        up to a millisecond late; ``select`` on the epoll descriptor counts
        microseconds and wakes on the same readiness.
        """

        def select(
            self, timeout: float | None = None
        ) -> list[tuple[selectors.SelectorKey, int]]:
            """Wait for readiness or the timeout.

            Args:
                timeout: Seconds to wait; ``None`` waits forever.

            Returns:
                The ready keys and events.
            """
            if timeout is not None and timeout > 0:
                select.select([self.fileno()], [], [], timeout)
                timeout = 0
            return super().select(timeout)


def event_loop() -> asyncio.AbstractEventLoop:
    """Create an event loop for sessions.

    Returns:
        On Linux, a loop whose timers keep microsecond precision; elsewhere the
        default loop (kqueue's timeouts are already precise).
    """
    if sys.platform == "linux":
        return asyncio.SelectorEventLoop(_PreciseEpollSelector())
    return asyncio.new_event_loop()


def _merge(plan: LoadPlan, shards: Sequence[_Shard]) -> LoadResult:
    """Merge what the generator processes measured.

    Args:
        plan: The load plan.
        shards: One measurement per process.

    Returns:
        The result.
    """
    open_loop = plan.mode == "open"
    response = [v for shard in shards for v in shard.response_ns]
    service = [v for shard in shards for v in shard.service_ns]
    latencies = response if open_loop else service
    sent = sum(shard.sent for shard in shards)
    answered = sum(shard.answered for shard in shards)
    answered_per_second = [
        sum(counts)
        for counts in zip(*(s.answered_per_second for s in shards), strict=True)
    ]
    return LoadResult(
        sessions=sum(shard.sessions for shard in shards),
        mode=plan.mode,
        processes=len(shards),
        cpus=None if plan.cpus is None else list(plan.cpus),
        warmup_s=plan.warmup_s,
        duration_s=plan.duration_s,
        offered_rate=plan.rate,
        achieved_send_rate=sum(s.sent_in_window for s in shards) / plan.duration_s,
        answered_rate=sum(answered_per_second) / plan.duration_s,
        sent=sent,
        answered=answered,
        answered_per_second=answered_per_second,
        unanswered=sent - answered,
        out_of_order=sum(shard.out_of_order for shard in shards),
        session_errors=[error for shard in shards for error in shard.errors],
        response_s=_summary(response, RESPONSE_PERCENTILES) if open_loop else None,
        service_s=_summary(service, SERVICE_PERCENTILES),
        lag_s=(
            _summary([v for s in shards for v in s.lag_ns], SERVICE_PERCENTILES)
            if open_loop
            else None
        ),
        generator_cpu_fraction=max(shard.cpu_fraction for shard in shards),
        prime_s=_summary([v for s in shards for v in s.prime_ns], PRIME_PERCENTILES),
        histogram={
            "of": "response_s" if open_loop else "service_s",
            "lo_s": HISTOGRAM_LO_S,
            "hi_s": HISTOGRAM_HI_S,
            "counts": stats.log_histogram(
                (v / 1e9 for v in latencies),
                lo=HISTOGRAM_LO_S,
                hi=HISTOGRAM_HI_S,
                buckets=HISTOGRAM_BUCKETS,
            ),
        },
        reply_frame=next((s.reply_frame for s in shards if s.reply_frame), None),
    )


def _summary(
    values_ns: Sequence[int], spec: Mapping[str, float]
) -> dict[str, float] | None:
    """Summarize nanosecond values as percentiles in seconds.

    Args:
        values_ns: The values.
        spec: Name to percentile.

    Returns:
        Name to seconds, or ``None`` without values.
    """
    if not values_ns:
        return None
    found = stats.percentiles(values_ns, list(spec.values()))
    return {name: value / 1e9 for name, value in zip(spec, found, strict=True)}


async def wait_readable(conn: Connection) -> None:
    """Wait until a pipe has a message, or its other end closed.

    Args:
        conn: The pipe.
    """
    loop = asyncio.get_running_loop()
    readable = loop.create_future()
    fd = conn.fileno()
    loop.add_reader(fd, lambda: readable.done() or readable.set_result(None))
    try:
        await readable
    finally:
        loop.remove_reader(fd)


async def _handshake(conn: Connection, errors: list[str]) -> int | None:
    """Report the primed sessions to the parent and wait for the start.

    From the start on, the pipe is watched: when the parent exits, however it
    exits, the run is cancelled and the process ends.

    Args:
        conn: The pipe to the parent.
        errors: Why sessions failed to prime.

    Returns:
        The start of the schedule, or ``None`` when the parent aborts.
    """
    conn.send(("ready", errors))
    await wait_readable(conn)
    kind, value = conn.recv()
    if kind != "go":
        return None
    # Anything more on the pipe means the parent stopped the run or died.
    loop = asyncio.get_running_loop()
    fd = conn.fileno()
    task = asyncio.current_task()
    assert task is not None

    def abort() -> None:
        loop.remove_reader(fd)
        task.cancel()

    loop.add_reader(fd, abort)
    return value


def _worker(plan: LoadPlan, indices: Sequence[int], conn: Connection) -> None:
    """Run one generator process: its sessions, on its CPUs, reporting over a pipe.

    Args:
        plan: The load plan.
        indices: The sessions of this process.
        conn: The pipe to the parent.
    """
    # The parent decides when to stop, also on Ctrl-C.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        if plan.cpus is not None and hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, plan.cpus)
        raise_fd_limit(len(indices))
        loop = event_loop()
        shard = loop.run_until_complete(
            _run_sessions(plan, indices, lambda errors: _handshake(conn, errors))
        )
        conn.send(("result", shard))
    except BaseException:
        with contextlib.suppress(OSError):
            conn.send(("error", traceback.format_exc()))


class LoadRunner:
    """Runs a load plan in spawned generator processes.

    :meth:`run` blocks until the result is in; :meth:`stop` kills the processes
    from any thread (a benchmark's ``conclude`` after a timed-out ``sample``),
    after which :meth:`run` raises. A runner runs once.
    """

    def __init__(self, plan: LoadPlan) -> None:
        """Plan the run; nothing starts yet.

        Args:
            plan: The load plan.
        """
        self.plan = plan
        self._lock = threading.Lock()
        self._procs: list[BaseProcess] = []
        self._conns: list[Connection] = []
        self._stopped = False

    def run(self, on_window: Callable[[str], None] | None = None) -> LoadResult:
        """Start the processes, prime every session, run the schedule and merge the results.

        Processes are spawned, not forked: the harness runs hooks on threads.

        Args:
            on_window: Called with ``"start"`` and ``"end"`` on this thread when
                the measured window starts and ends, e.g. to read the server's
                CPU counters.

        Returns:
            The merged result.

        Raises:
            LoadError: When sessions could not start, a process failed or timed
                out, or the runner was stopped.
        """
        plan = self.plan
        context = multiprocessing.get_context("spawn")
        try:
            with self._lock:
                if self._stopped:
                    msg = "the load was stopped before it started"
                    raise LoadError(msg)
                for index in range(plan.processes):
                    conn, child = context.Pipe()
                    self._conns.append(conn)
                    proc = context.Process(
                        target=_worker,
                        args=(plan, range(index, plan.sessions, plan.processes), child),
                        name=f"reflex-bench-load-{index}",
                        daemon=True,
                    )
                    proc.start()
                    child.close()
                    self._procs.append(proc)
            per_process = -(-plan.sessions // plan.processes)
            batches = -(-per_process // PRIME_CONCURRENCY)
            ready = self._collect("ready", READY_MARGIN_S + batches * PRIME_TIMEOUT_S)
            if errors := [error for errors in ready for error in errors]:
                msg = f"{len(errors)} of {plan.sessions} sessions could not start; {errors[0]}"
                raise LoadError(msg)
            t0 = time.perf_counter_ns() + int(START_DELAY_S * 1e9)
            for conn in self._conns:
                conn.send(("go", t0))
            measure_from = t0 + int(plan.warmup_s * 1e9)
            if on_window is not None:
                self._sleep_until(measure_from)
                on_window("start")
                self._sleep_until(measure_from + int(plan.duration_s * 1e9))
                on_window("end")
            shards = self._collect(
                "result",
                plan.warmup_s + plan.duration_s + plan.drain_s + RESULT_MARGIN_S,
            )
        finally:
            self.stop()
            for conn in self._conns:
                conn.close()
        return _merge(plan, shards)

    def _watched(self) -> list[Any]:
        """List what signals a message or a process exit.

        Returns:
            The pipes and the process sentinels.
        """
        return [*self._conns, *(proc.sentinel for proc in self._procs)]

    def _sleep_until(self, deadline: int) -> None:
        """Sleep until a time, or until a process reports or exits early.

        Args:
            deadline: A ``perf_counter_ns`` time.
        """
        while (remaining := deadline - time.perf_counter_ns()) > 0:
            if multiprocessing.connection.wait(self._watched(), remaining / 1e9):
                return

    def _collect(self, kind: str, timeout: float) -> list[Any]:
        """Receive one message of a kind from every process.

        Args:
            kind: ``ready`` or ``result``.
            timeout: Seconds to wait for all of them.

        Returns:
            The values, in process order.

        Raises:
            LoadError: When a process fails, exits, times out or is stopped.
        """
        deadline = time.monotonic() + timeout
        values: dict[int, Any] = {}
        while len(values) < len(self._conns):
            pending = [
                (index, conn)
                for index, conn in enumerate(self._conns)
                if index not in values
            ]
            remaining = deadline - time.monotonic()
            ready = multiprocessing.connection.wait(
                [conn for _, conn in pending]
                + [self._procs[index].sentinel for index, _ in pending],
                max(0.0, remaining),
            )
            if self._stopped:
                msg = "the load was stopped"
                raise LoadError(msg)
            if not ready:
                msg = f"generator processes sent no {kind} within {timeout:g} s"
                raise LoadError(msg)
            for index, conn in pending:
                if conn not in ready and self._procs[index].sentinel not in ready:
                    continue
                try:
                    got, value = conn.recv()
                except (EOFError, OSError):
                    code = self._procs[index].exitcode
                    msg = f"generator process {index} exited with code {code}"
                    raise LoadError(msg) from None
                if got == "error":
                    msg = f"generator process {index} failed:\n{value}"
                    raise LoadError(msg)
                values[index] = value
        return [values[index] for index in range(len(self._conns))]

    def stop(self) -> None:
        """Terminate the generator processes, killing those that do not exit.

        Safe to call from any thread and more than once.
        """
        with self._lock:
            self._stopped = True
            for proc in self._procs:
                if proc.is_alive():
                    proc.terminate()
            for proc in self._procs:
                proc.join(KILL_GRACE_S)
                if proc.is_alive():
                    proc.kill()
                    proc.join(KILL_GRACE_S)


def run_load(
    plan: LoadPlan, on_window: Callable[[str], None] | None = None
) -> LoadResult:
    """Run a load plan in spawned generator processes.

    Args:
        plan: The load plan.
        on_window: Called with ``"start"`` and ``"end"`` at the edges of the
            measured window.

    Returns:
        The result; call :meth:`LoadResult.check` before trusting it.
    """
    return LoadRunner(plan).run(on_window)


async def _hold(endpoint: Endpoint, count: int, conn: Connection) -> None:
    """Prime idle sessions and keep them open until the parent closes them.

    Args:
        endpoint: Where they connect.
        count: How many.
        conn: The pipe to the parent.
    """
    async with open_sessions(endpoint, count) as pool:
        conn.send(("ready", pool.errors))
        # The parent asks to close, or its end of the pipe closes when it exits.
        await wait_readable(conn)
    conn.send(("closed", pool.errors))


def _hold_worker(endpoint: Endpoint, count: int, conn: Connection) -> None:
    """Run the process of a hold, reporting over a pipe.

    Args:
        endpoint: Where the sessions connect.
        count: How many.
        conn: The pipe to the parent.
    """
    # The parent decides when to stop, also on Ctrl-C.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        raise_fd_limit(count)
        event_loop().run_until_complete(_hold(endpoint, count, conn))
    except BaseException:
        with contextlib.suppress(OSError):
            conn.send(("error", traceback.format_exc()))


class SessionHold:
    """Idle sessions in a spawned process: connected, hydrated and answering pings.

    The sessions send no events after priming, like browser tabs left open.
    :meth:`ready` waits until every session is primed, :meth:`close` leaves the
    namespace and closes each websocket, and :meth:`kill` ends the process from
    any thread (a benchmark's ``conclude`` after a timed-out ``sample``). A hold
    whose parent exits closes its sessions and ends.
    """

    def __init__(self, endpoint: Endpoint, count: int) -> None:
        """Plan the hold; nothing starts yet.

        Args:
            endpoint: Where the sessions connect.
            count: The number of sessions.
        """
        self.endpoint = endpoint
        self.count = count
        self._lock = threading.Lock()
        self._proc: BaseProcess | None = None
        self._conn: Connection | None = None
        self._stopped = False

    def start(self) -> SessionHold:
        """Spawn the process, which connects and primes the sessions.

        Returns:
            The hold.

        Raises:
            LoadError: When the hold was killed before it started.
        """
        context = multiprocessing.get_context("spawn")
        with self._lock:
            if self._stopped:
                msg = "the hold was stopped before it started"
                raise LoadError(msg)
            conn, child = context.Pipe()
            self._conn = conn
            proc = self._proc = context.Process(
                target=_hold_worker,
                args=(self.endpoint, self.count, child),
                name="reflex-bench-hold",
                daemon=True,
            )
            proc.start()
            child.close()
        return self

    def ready(self) -> None:
        """Wait until every session is connected and hydrated.

        Raises:
            LoadError: When sessions could not start, with how many, or the
                process failed, timed out or was killed.
        """
        batches = -(-self.count // PRIME_CONCURRENCY)
        errors = self._receive("ready", READY_MARGIN_S + batches * PRIME_TIMEOUT_S)
        if errors:
            msg = f"{len(errors)} of {self.count} sessions could not start; {errors[0]}"
            raise LoadError(msg)

    def close(self) -> list[str]:
        """Leave the namespace and close every websocket, then end the process.

        Returns:
            Why sessions failed while they were held, e.g. because the server
            disconnected them.

        Raises:
            LoadError: When the process failed, did not answer or was killed.
        """
        try:
            with self._lock:
                if self._stopped or self._conn is None:
                    msg = "the hold was stopped"
                    raise LoadError(msg)
                self._conn.send(("close", None))
            return self._receive("closed", RESULT_MARGIN_S)
        finally:
            self.kill()
            if self._conn is not None:
                self._conn.close()

    def _receive(self, kind: str, timeout: float) -> list[str]:
        """Receive the process's next report.

        Args:
            kind: The report expected, ``ready`` or ``closed``.
            timeout: Seconds to wait.

        Returns:
            The session errors it carries.

        Raises:
            LoadError: When the process failed, exited, timed out or was killed.
        """
        conn, proc = self._conn, self._proc
        if conn is None or proc is None:
            msg = "the hold was not started"
            raise LoadError(msg)
        ready = multiprocessing.connection.wait([conn, proc.sentinel], timeout)
        if self._stopped:
            msg = "the hold was stopped"
            raise LoadError(msg)
        if not ready:
            msg = f"the hold sent no {kind} report within {timeout:g} s"
            raise LoadError(msg)
        try:
            got, value = conn.recv()
        except (EOFError, OSError):
            msg = f"the hold's process exited with code {proc.exitcode}"
            raise LoadError(msg) from None
        if got == "error":
            msg = f"the hold's process failed:\n{value}"
            raise LoadError(msg)
        return value

    def kill(self) -> None:
        """Terminate the process, killing it if it does not exit.

        Safe to call from any thread and more than once.
        """
        with self._lock:
            self._stopped = True
            proc = self._proc
        if proc is None:
            return
        if proc.is_alive():
            proc.terminate()
        proc.join(KILL_GRACE_S)
        if proc.is_alive():
            proc.kill()
            proc.join(KILL_GRACE_S)


def hold_sessions(endpoint: Endpoint, count: int) -> SessionHold:
    """Connect and hydrate idle sessions in a spawned process, and hold them open.

    Call :meth:`SessionHold.ready` to wait for them, then :meth:`SessionHold.close`;
    :meth:`SessionHold.kill` must follow in any case.

    Args:
        endpoint: Where the sessions connect.
        count: The number of sessions.

    Returns:
        The started hold.
    """
    return SessionHold(endpoint, count).start()
