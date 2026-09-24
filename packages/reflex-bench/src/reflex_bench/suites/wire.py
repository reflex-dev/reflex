"""Wire sizes: the bytes a page load and each event move over the event websocket.

Timing and CPU benchmarks miss what a slow link pays for: the size of the
frames. One session connects to a production backend (``reflex run --env prod
--backend-only``, one granian worker, a fresh one per sample) and counts the
payload bytes of every websocket frame it sends and receives:

- ``wire.hydrate``: from the connect until the delta that sets ``is_hydrated``,
  the page load of the playground's index route.
- ``wire.event[shape=...]``: after that, one event of a playground shape
  (:data:`~reflex_bench.suites.events.SHAPES`): the request frame, and the
  reply until the delta that echoes its sequence number, every frame in
  between included (0.8.23 answers a background task with an empty update
  first).
- ``wire.delta[change=...]``: the same for one small change to a large
  collection, on a generated app (``wire_delta``) whose state holds 1000 ints
  in a list, 1000 keys in a dict and 200 dict rows: ``append_item``,
  ``set_one_item``, ``set_dict_key``, ``update_row_field``, and ``set_scalar``
  as the control that changes no collection. Every handler also sets
  ``last_seq``, so the deltas differ only by the collection they carry.

A byte count is a text frame's UTF-8 length; the HTTP handshake that opens the
websocket is not a frame. Sizes are deterministic for a given app and reflex
version, so every metric is exact and a sample is one run. The playground is
the fixture of ``hydrate`` and ``event``; the generated app's source hash keys
the ``delta`` series, so a change to it never compares against old numbers.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hashlib
import json
import shutil
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppProcess, run_cli
from reflex_bench.drivers.events import (
    CLOSE,
    CONNECT_ERROR_PREFIX,
    CONNECT_FRAME,
    DISCONNECT_FRAME,
    EVENT_PREFIX,
    HYDRATE_EVENT,
    HYDRATED_VAR,
    MAX_FRAME_BYTES,
    ON_LOAD_EVENT,
    OPEN_PREFIX,
    PING,
    PONG,
    ROOT_STATE,
    Endpoint,
    EventShape,
    ProtocolError,
    event_frame,
    event_loop,
    event_url,
    seq_payload,
)
from reflex_bench.registry import Metric, SampleResult, benchmark
from reflex_bench.suites.events import (
    COMPILE_TIMEOUT_S,
    SEQ_VAR,
    SHAPES,
    app_env,
    prepare_app,
    server_env,
)
from reflex_bench.suites.memory import START_TIMEOUT_S, _Started

WIRE_TIMEOUT_S = 30.0
HOOK_TIMEOUT_S = 300.0
SETUP_TIMEOUT_S = COMPILE_TIMEOUT_S + 60
CHEAP_SUITES = ("pr", "smoke", "daily")
WIRE_STATE = "reflex___state____state.wire_delta___state____wire_state"
CHANGES = (
    "set_scalar",
    "append_item",
    "set_one_item",
    "set_dict_key",
    "update_row_field",
)

_T = TypeVar("_T")


class Transport(Protocol):
    """What a session needs of a websocket."""

    async def send(self, message: str) -> None:
        """Send a text frame.

        Args:
            message: The frame.
        """

    async def recv(self) -> str | bytes:
        """Receive the next frame.

        Returns:
            The frame.
        """
        ...


def frame_bytes(message: str | bytes) -> int:
    """Measure a frame's payload.

    Args:
        message: The frame.

    Returns:
        Its bytes on the wire: the UTF-8 length of a text frame.
    """
    return len(message.encode()) if isinstance(message, str) else len(message)


@dataclass(frozen=True)
class Hydration:
    """What a page load moved, from the connect until ``is_hydrated``.

    Attributes:
        sent_bytes: Frame bytes sent: the namespace join, the hydration events
            and any pong.
        received_bytes: Frame bytes received: the engine.io open, the namespace
            ack, a ``new_token`` if any, and the deltas.
        sent_frames: The frames sent.
        received_frames: The frames received.
        largest_frame_bytes: The largest frame received.
        delta_bytes: Per substate, the bytes of its part of the deltas,
            re-serialized compactly.
    """

    sent_bytes: int
    received_bytes: int
    sent_frames: int
    received_frames: int
    largest_frame_bytes: int
    delta_bytes: dict[str, int]


@dataclass(frozen=True)
class Exchange:
    """What one event moved.

    Attributes:
        request_bytes: The event frame.
        response_bytes: Every frame received until the delta that echoes the
            sequence number, that delta included.
        response_frames: Their number.
        largest_frame_bytes: The largest of them.
        delta_bytes: Per substate, the bytes of its part of the deltas,
            re-serialized compactly.
        reply: The frame that echoed the sequence number.
    """

    request_bytes: int
    response_bytes: int
    response_frames: int
    largest_frame_bytes: int
    delta_bytes: dict[str, int]
    reply: str


class WireSession:
    """One browser tab on a metered websocket: it hydrates, then sends events one at a time."""

    def __init__(self, ws: Transport, token: str, pathname: str = "/") -> None:
        """Wrap a connected websocket; nothing is sent yet.

        Args:
            ws: The websocket, connected with ``token`` in its URL.
            token: The session's token.
            pathname: The page route the session loads.
        """
        self._ws = ws
        self.token = token
        self.pathname = pathname
        self.sent_bytes = 0
        self.sent_frames = 0
        self.received_bytes = 0
        self.received_frames = 0

    async def _send(self, frame: str) -> int:
        """Send a frame and count it.

        Args:
            frame: The frame.

        Returns:
            Its bytes.
        """
        size = frame_bytes(frame)
        self.sent_bytes += size
        self.sent_frames += 1
        await self._ws.send(frame)
        return size

    async def _receive(self) -> tuple[str | bytes, int, list[Any] | None]:
        """Receive a frame and count it; pings are answered, disconnects raise.

        Returns:
            The frame, its bytes and, for a socket.io event, its arguments.

        Raises:
            ProtocolError: When the server disconnects the session, refuses
                the namespace, asks the page to reload or sends a frame the
                session does not speak.
        """
        while True:
            message = await self._ws.recv()
            size = frame_bytes(message)
            self.received_bytes += size
            self.received_frames += 1
            if isinstance(message, str):
                if message.startswith(EVENT_PREFIX):
                    args = json.loads(message[len(EVENT_PREFIX) :])
                    if args[0] == "new_token":
                        # The token was in use; reflex hands out a new one.
                        self.token = args[1]
                    elif args[0] == "reload":
                        msg = "the server asked the page to reload"
                        raise ProtocolError(msg)
                    return message, size, args
                if message == PING:
                    await self._send(PONG)
                    continue
                if message in {DISCONNECT_FRAME, CLOSE}:
                    msg = f"the server disconnected the session ({message!r})"
                    raise ProtocolError(msg)
                if message.startswith(CONNECT_ERROR_PREFIX):
                    reason = message[len(CONNECT_ERROR_PREFIX) :]
                    msg = f"the server refused the namespace: {reason}"
                    raise ProtocolError(msg)
                if message.startswith((OPEN_PREFIX, CONNECT_FRAME)):
                    return message, size, None
            msg = f"unexpected frame: {message[:40]!r}"
            raise ProtocolError(msg)

    @staticmethod
    def _delta(args: list[Any] | None, sizes: dict[str, int]) -> dict[str, Any]:
        """Take the delta of an event frame, adding its substates' bytes.

        Args:
            args: The frame's arguments, or ``None`` for a control frame.
            sizes: Bytes per substate, added to.

        Returns:
            The delta, empty when the frame carries none.
        """
        if args is None or args[0] != "event":
            return {}
        delta = args[1].get("delta") or {}
        for substate, values in delta.items():
            sizes[substate] = sizes.get(substate, 0) + frame_bytes(
                json.dumps(values, separators=(",", ":"))
            )
        return delta

    async def hydrate(self) -> Hydration:
        """Join the namespace and hydrate like a page load.

        Returns:
            What the page load moved.

        Raises:
            ProtocolError: When the server does not open an engine.io session.
        """
        sent0, sent_frames0 = self.sent_bytes, self.sent_frames
        received0, received_frames0 = self.received_bytes, self.received_frames
        opened, largest, _ = await self._receive()
        if not (isinstance(opened, str) and opened.startswith(OPEN_PREFIX)):
            msg = f"the server did not open an engine.io session: {opened[:40]!r}"
            raise ProtocolError(msg)
        await self._send(CONNECT_FRAME)
        sizes: dict[str, int] = {}
        while True:
            message, size, args = await self._receive()
            largest = max(largest, size)
            if isinstance(message, str) and message.startswith(CONNECT_FRAME):
                # Joined; a new_token, when the server sends one, came before.
                for name in (HYDRATE_EVENT, ON_LOAD_EVENT):
                    await self._send(
                        event_frame(name, {}, token=self.token, pathname=self.pathname)
                    )
                continue
            delta = self._delta(args, sizes)
            if delta.get(ROOT_STATE, {}).get(HYDRATED_VAR) is True:
                break
        return Hydration(
            sent_bytes=self.sent_bytes - sent0,
            received_bytes=self.received_bytes - received0,
            sent_frames=self.sent_frames - sent_frames0,
            received_frames=self.received_frames - received_frames0,
            largest_frame_bytes=largest,
            delta_bytes=sizes,
        )

    async def exchange(self, shape: EventShape, seq: int) -> Exchange:
        """Send one event and read its reply.

        Args:
            shape: The event.
            seq: Its sequence number, which the reply echoes.

        Returns:
            What the event moved.
        """
        request = await self._send(
            event_frame(
                shape.name, shape.payload(seq), token=self.token, pathname=self.pathname
            )
        )
        received = self.received_bytes
        frames = self.received_frames
        largest = 0
        sizes: dict[str, int] = {}
        while True:
            message, size, args = await self._receive()
            largest = max(largest, size)
            delta = self._delta(args, sizes)
            if delta.get(shape.delta_key, {}).get(shape.seq_var) == seq:
                assert isinstance(message, str)
                return Exchange(
                    request_bytes=request,
                    response_bytes=self.received_bytes - received,
                    response_frames=self.received_frames - frames,
                    largest_frame_bytes=largest,
                    delta_bytes=sizes,
                    reply=message,
                )


def measure(endpoint: Endpoint, work: Callable[[WireSession], Awaitable[_T]]) -> _T:
    """Connect one session, run work on it, and leave the namespace.

    Args:
        endpoint: The backend and the page route.
        work: What the session does; it starts with :meth:`WireSession.hydrate`.

    Returns:
        What the work returns.

    Raises:
        TimeoutError: When the work does not finish within ``WIRE_TIMEOUT_S``.
    """

    async def run() -> _T:
        token = str(uuid.uuid4())
        async with connect(
            event_url(endpoint.backend_url, token),
            proxy=None,
            open_timeout=WIRE_TIMEOUT_S,
            max_size=MAX_FRAME_BYTES,
            ping_interval=None,
            close_timeout=1,
        ) as ws:
            session = WireSession(ws, token, endpoint.pathname)
            try:
                return await asyncio.wait_for(work(session), WIRE_TIMEOUT_S)
            except asyncio.TimeoutError:
                msg = f"the session did not finish within {WIRE_TIMEOUT_S:g} s"
                raise TimeoutError(msg) from None
            finally:
                with contextlib.suppress(ConnectionClosed):
                    await ws.send(DISCONNECT_FRAME)

    loop = event_loop()
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


RXCONFIG_SOURCE = '''"""Reflex configuration of the wire_delta app."""

import reflex as rx

plugins: list[rx.plugins.Plugin] = [rx.plugins.SitemapPlugin()]
# Reflex 0.9 moved Radix Themes into a plugin; older releases always load it.
if hasattr(rx.plugins, "RadixThemesPlugin"):
    plugins.append(rx.plugins.RadixThemesPlugin())

config = rx.Config(app_name="wire_delta", plugins=plugins)
'''

STATE_SOURCE = '''"""State of the wire_delta app: large collections and the small changes to them."""

import reflex as rx


class WireState(rx.State):
    """Large collections, and one handler per small change to them."""

    last_seq: int = 0
    scalar: int = 0
    items: list[int] = list(range(1000))
    table: dict[str, int] = {f"key_{i}": i for i in range(1000)}
    rows: list[dict[str, int]] = [
        {"id": i, "value": i * 3, "score": i % 7} for i in range(200)
    ]

    @rx.event
    def set_scalar(self, seq: int):
        """Change a scalar only: the control.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.scalar = seq
        self.last_seq = seq

    @rx.event
    def append_item(self, seq: int):
        """Append one int to the list.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.items.append(seq)
        self.last_seq = seq

    @rx.event
    def set_one_item(self, seq: int):
        """Replace one int in the middle of the list.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.items[500] = seq
        self.last_seq = seq

    @rx.event
    def set_dict_key(self, seq: int):
        """Set one existing key of the dict.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.table["key_500"] = seq
        self.last_seq = seq

    @rx.event
    def update_row_field(self, seq: int):
        """Change one field of one row.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.rows[100]["value"] = seq
        self.last_seq = seq
'''

APP_SOURCE = '''"""The wire_delta app: one page over the state the wire benchmarks drive."""

import reflex as rx

from wire_delta.state import WireState


def index() -> rx.Component:
    """Render the scalar and the sequence number.

    Returns:
        The page.
    """
    return rx.vstack(
        rx.heading("wire_delta"),
        rx.text(WireState.scalar),
        rx.text(WireState.last_seq),
    )


app = rx.App()
app.add_page(index, title="wire_delta")
'''


def delta_app_files() -> dict[str, str]:
    """List the generated app's files.

    Returns:
        Relative POSIX path to source.
    """
    return {
        "rxconfig.py": RXCONFIG_SOURCE,
        "wire_delta/__init__.py": '"""The wire_delta app."""\n',
        "wire_delta/state.py": STATE_SOURCE,
        "wire_delta/wire_delta.py": APP_SOURCE,
    }


def fixture_hash() -> str:
    """Hash the generated app, as ``scripts/hash_examples.py`` hashes the playground.

    Returns:
        ``sha256:<hex>`` over each file's relative path and bytes.
    """
    digest = hashlib.sha256()
    for path, source in sorted(delta_app_files().items()):
        data = source.encode()
        digest.update(f"{path}\0{len(data)}\0".encode())
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def write_app(target: Path) -> None:
    """Write the generated app.

    Args:
        target: The app directory; replaced.
    """
    shutil.rmtree(target, ignore_errors=True)
    for relative, source in delta_app_files().items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


def prepare_delta_app(ctx: Context) -> None:
    """Write the generated app into the cache directory and compile it once.

    Args:
        ctx: The benchmark context.
    """
    app = ctx.cache_dir / "app"
    write_app(app)
    run_cli(
        ctx.subject.python,
        ["compile"],
        cwd=app,
        env=app_env(ctx),
        timeout=COMPILE_TIMEOUT_S,
    ).check()


def delta_shape(change: str) -> EventShape:
    """Describe a ``WireState`` handler of the generated app.

    Args:
        change: The handler's name.

    Returns:
        The event shape: payload ``{"seq": n}``, echoed as ``last_seq``.
    """
    return EventShape(
        name=f"{WIRE_STATE}.{change}",
        payload=seq_payload,
        delta_key=WIRE_STATE,
        seq_var=SEQ_VAR,
    )


def _bytes(description: str) -> Metric:
    """Declare a byte count.

    Args:
        description: What it counts.

    Returns:
        An exact metric in bytes, lower is better.
    """
    return Metric(unit="B", direction="lower", assume="exact", description=description)


def _count(description: str) -> Metric:
    """Declare a frame count.

    Args:
        description: What it counts.

    Returns:
        An exact metric, lower is better.
    """
    return Metric(unit="1", direction="lower", assume="exact", description=description)


class _OneSession:
    """Hooks every wire benchmark shares: a fresh backend per sample, one session on it."""

    fixture = "playground"
    started: _Started | None = None

    def setup_cache(self, ctx: Context) -> None:
        """Copy the playground into the cache directory and compile it once.

        Args:
            ctx: The benchmark context.
        """
        prepare_app(ctx)

    def setup(self, ctx: Context) -> None:
        """Name the fixture in the dims.

        Args:
            ctx: The benchmark context.
        """
        ctx.dims["fixture"] = self.fixture

    def prepare(self, ctx: Context) -> None:
        """Get ready to stop what the sample starts.

        Args:
            ctx: The benchmark context.
        """
        self.started = _Started()

    def conclude(self, ctx: Context) -> None:
        """Stop the sample's backend, also after a failure or a timeout.

        Args:
            ctx: The benchmark context.
        """
        started, self.started = self.started, None
        if started is not None:
            started.stop()

    def backend(self, ctx: Context) -> Endpoint:
        """Start the compiled app as a production backend with the memory state manager.

        Args:
            ctx: The benchmark context.

        Returns:
            Where a session connects.
        """
        started = self.started
        assert started is not None
        app = AppProcess(
            ctx.subject.python,
            ctx.cache_dir / "app",
            mode="prod",
            backend_only=True,
            reflex_version=ctx.subject.reflex_version,
            env=server_env(app_env(ctx), "memory", ctx.workdir / "states"),
            start_timeout=START_TIMEOUT_S,
        )
        started.add(app.stop)
        app.start()
        app.wait_http_ready(timeout=START_TIMEOUT_S)
        return Endpoint(app.backend_url)

    def exchange(self, ctx: Context, shape: EventShape) -> SampleResult:
        """Hydrate a session on a fresh backend and send it one event.

        Args:
            ctx: The benchmark context.
            shape: The event.

        Returns:
            The request and reply sizes, with the exchange and the hydration as
            extra data.
        """

        async def work(session: WireSession) -> tuple[Hydration, Exchange]:
            return await session.hydrate(), await session.exchange(shape, 1)

        hydration, exchange = measure(self.backend(ctx), work)
        return SampleResult(
            {
                "request_bytes": exchange.request_bytes,
                "response_bytes": exchange.response_bytes,
                "response_frames": exchange.response_frames,
            },
            extra={
                **dataclasses.asdict(exchange),
                "hydration": dataclasses.asdict(hydration),
            },
        )


@benchmark(
    id="wire.hydrate",
    suites=CHEAP_SUITES,
    kind="track",
    metrics={
        "hydrate_sent_bytes": _bytes(
            "frame bytes sent from the connect until is_hydrated"
        ),
        "hydrate_received_bytes": _bytes("frame bytes received until is_hydrated"),
        "hydrate_frames": _count("frames received until is_hydrated"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=4,
)
class Hydrate(_OneSession):
    """Websocket bytes of a page load of the playground's index route, from the connect until ``is_hydrated``."""

    def sample(self, ctx: Context) -> SampleResult:
        """Hydrate one session on a fresh backend.

        Args:
            ctx: The benchmark context.

        Returns:
            The bytes and frames, with the largest frame and the bytes per
            substate as extra data.
        """
        hydration = measure(self.backend(ctx), WireSession.hydrate)
        return SampleResult(
            {
                "hydrate_sent_bytes": hydration.sent_bytes,
                "hydrate_received_bytes": hydration.received_bytes,
                "hydrate_frames": hydration.received_frames,
            },
            extra=dataclasses.asdict(hydration),
        )


@benchmark(
    id="wire.event",
    suites=CHEAP_SUITES,
    kind="track",
    params={"shape": tuple(SHAPES)},
    suite_params={"pr": {"shape": ("simple",)}, "smoke": {"shape": ("simple",)}},
    metrics={
        "request_bytes": _bytes("the event frame"),
        "response_bytes": _bytes("frames received until the delta echoing the event"),
        "response_frames": _count("frames received until the delta echoing the event"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=4,
)
class Event(_OneSession):
    """Websocket bytes of one playground event after hydration: the request frame and the reply."""

    def sample(self, ctx: Context) -> SampleResult:
        """Send one event of the shape.

        Args:
            ctx: The benchmark context.

        Returns:
            The request and reply sizes.
        """
        return self.exchange(ctx, SHAPES[ctx.params["shape"]])


@benchmark(
    id="wire.delta",
    suites=("daily",),
    kind="track",
    params={"change": CHANGES},
    metrics={
        "response_bytes": _bytes("frames received until the delta echoing the change"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=4,
)
class Delta(_OneSession):
    """Reply bytes of one small change to a large collection (1000 ints, 1000 keys, 200 rows) on the generated wire_delta app."""

    fixture = "wire_delta"

    def setup_cache(self, ctx: Context) -> None:
        """Generate the app into the cache directory and compile it once.

        Args:
            ctx: The benchmark context.
        """
        prepare_delta_app(ctx)

    def setup(self, ctx: Context) -> None:
        """Name the fixture and its content hash in the dims.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        ctx.dims["fixture_hash"] = fixture_hash()

    def sample(self, ctx: Context) -> SampleResult:
        """Send the change.

        Args:
            ctx: The benchmark context.

        Returns:
            The reply size, with the request size and the frames as extra data.
        """
        result = self.exchange(ctx, delta_shape(ctx.params["change"]))
        return SampleResult(
            {"response_bytes": result.values["response_bytes"]}, extra=result.extra
        )
