"""Tests for reflex_bench.suites.wire.

Nothing here starts reflex: the sessions run against scripted transports (or
the echo server on a loopback socket), and the benchmarks run through the
scheduler with the app and the websocket replaced by fakes.
"""

from __future__ import annotations

import ast
import asyncio
import collections
import contextlib
import dataclasses
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import fixtures, registry
from reflex_bench.drivers.app_process import CliResult
from reflex_bench.drivers.echo_server import EchoServer
from reflex_bench.drivers.events import (
    CONNECT_FRAME,
    DISCONNECT_FRAME,
    HYDRATE_EVENT,
    HYDRATED_VAR,
    ON_LOAD_EVENT,
    PING,
    PONG,
    ROOT_STATE,
    Endpoint,
    ProtocolError,
    emit_frame,
    event_frame,
)
from reflex_bench.scheduler import Planned, Policy, Scheduler, plan
from reflex_bench.suites import events as events_suite
from reflex_bench.suites import wire
from reflex_bench.suites.events import SEQ_VAR

from tests.units.reflex_bench.drivers.test_events import serving
from tests.units.reflex_bench.factories import make_subject
from tests.units.reflex_bench.suites.test_events import STATES

BENCH_STATE = STATES.bench
SHAPES = {name: shape_of(STATES) for name, shape_of in events_suite.SHAPES.items()}
PLAYGROUND_STATE = "reflex___state____state.playground___state____playground_state"
OPEN = '0{"sid":"abc","upgrades":[],"pingInterval":25000,"pingTimeout":20000}'
ACK = '40/_event,{"sid":"abc"}'
CHANGES = (
    "set_scalar",
    "append_item",
    "set_one_item",
    "set_dict_key",
    "update_row_field",
)


def size(*frames: str) -> int:
    return sum(len(frame.encode()) for frame in frames)


def delta_frame(delta: dict[str, Any], **more: Any) -> str:
    return emit_frame("event", {"delta": delta, **more})


class FakeTransport:
    """A scripted server: every sent frame queues the replies a script gives."""

    def __init__(
        self, script: Callable[[str], list[str]], greeting: list[str] | None = None
    ) -> None:
        """Queue the server's greeting.

        Args:
            script: Maps a sent frame to the frames it triggers.
            greeting: The frames waiting before anything is sent; the engine.io
                open by default.
        """
        self.script = script
        self.sent: list[str] = []
        self.inbox: collections.deque[str | bytes] = collections.deque(
            greeting or [OPEN]
        )

    async def send(self, message: str) -> None:
        """Record a frame and queue what the script answers.

        Args:
            message: The frame.
        """
        self.sent.append(message)
        self.inbox.extend(self.script(message))

    async def recv(self) -> str | bytes:
        """Take the next queued frame.

        Returns:
            The frame.

        Raises:
            AssertionError: When the script queued nothing more.
        """
        if not self.inbox:
            msg = "the session waits for a frame the script never sends"
            raise AssertionError(msg)
        return self.inbox.popleft()


def playground_script(
    *, new_token: str | None = None, replies: dict[str, list[str]] | None = None
) -> Callable[[str], list[str]]:
    """Script the playground's answers: a hydration in two deltas, then echoes.

    Args:
        new_token: A token handed out before the namespace ack.
        replies: The frames answering an event, by handler name; other events
            get one echo of their sequence number, and ``on_load_internal``
            the ``is_hydrated`` delta, with the router's page away from ``/``.

    Returns:
        The script.
    """

    def script(message: str) -> list[str]:
        if message == CONNECT_FRAME:
            handed = [emit_frame("new_token", new_token)] if new_token else []
            return [*handed, ACK]
        if message in {PONG, DISCONNECT_FRAME}:
            return []
        event = json.loads(message.partition(",")[2])[1]
        name = event["name"]
        if replies and name in replies:
            return replies[name]
        if name == HYDRATE_EVENT:
            return [
                delta_frame({
                    ROOT_STATE: {HYDRATED_VAR: False, "router_rx_state_": {"a": 1}},
                    BENCH_STATE: {SEQ_VAR: 0, "part_a_rx_state_": 0},
                    PLAYGROUND_STATE: {
                        "count_rx_state_": 0,
                        "items_rx_state_": ["alpha"],
                    },
                })
            ]
        if name == ON_LOAD_EVENT:
            return [navigation_reply(event["router_data"])]
        state, _, _handler = name.rpartition(".")
        return [delta_frame({state: {SEQ_VAR: event["payload"]["seq"]}})]

    return script


def navigation_reply(router_data: dict[str, Any]) -> str:
    """Build the delta that completes an ``on_load_internal``.

    Args:
        router_data: The event's router data.

    Returns:
        ``is_hydrated`` set; away from ``/`` the root state's router too.
    """
    root: dict[str, Any] = {HYDRATED_VAR: True}
    if router_data["pathname"] != "/":
        root["router_rx_state_"] = {
            "page": {"path": router_data["pathname"], "params": router_data["query"]}
        }
    return delta_frame({ROOT_STATE: root})


def run(work: Any) -> Any:
    return asyncio.run(work)


def test_frame_bytes_counts_utf8_text_and_binary():
    assert wire.frame_bytes("abc") == 3
    assert wire.frame_bytes("é") == 2
    assert wire.frame_bytes(b"\x00\x01") == 2


def test_hydration_counts_every_frame_until_hydrated():
    ws = FakeTransport(playground_script(new_token="tok-2"))
    session = wire.WireSession(ws, "tok-1")
    hydration = run(session.hydrate())
    hydrate = event_frame(HYDRATE_EVENT, {}, token="tok-2", pathname="/")
    on_load = event_frame(ON_LOAD_EVENT, {}, token="tok-2", pathname="/")
    # The new token is adopted before the hydration events go out.
    assert ws.sent == [CONNECT_FRAME, hydrate, on_load]
    assert hydration.sent_bytes == size(CONNECT_FRAME, hydrate, on_load)
    assert hydration.sent_frames == 3
    first, second = playground_script()(hydrate)[0], playground_script()(on_load)[0]
    token_frame = emit_frame("new_token", "tok-2")
    assert hydration.received_bytes == size(OPEN, token_frame, ACK, first, second)
    assert hydration.received_frames == 5
    assert hydration.largest_frame_bytes == size(first)
    assert hydration.delta_bytes == {
        ROOT_STATE: size(json.dumps({HYDRATED_VAR: False, "router_rx_state_": {"a": 1}}, separators=(",", ":")))
        + size(json.dumps({HYDRATED_VAR: True}, separators=(",", ":"))),
        BENCH_STATE: size('{"last_seq_rx_state_":0,"part_a_rx_state_":0}'),
        PLAYGROUND_STATE: size('{"count_rx_state_":0,"items_rx_state_":["alpha"]}'),
    }  # fmt: skip
    assert session.token == "tok-2"


def test_a_ping_during_hydration_is_answered_and_not_counted():
    ws = FakeTransport(playground_script(), greeting=[OPEN, PING])
    hydration = run(wire.WireSession(ws, "tok").hydrate())
    assert ws.sent[:2] == [CONNECT_FRAME, PONG]
    # Keepalives are timing, not payload: neither the ping nor the pong counts.
    assert hydration.sent_frames == 3
    assert hydration.received_frames == 4
    assert hydration.sent_bytes == size(CONNECT_FRAME, *ws.sent[2:])


@pytest.mark.parametrize(
    ("frames", "match"),
    [
        (['44/_event,{"message":"nope"}'], "refused"),
        ([DISCONNECT_FRAME], "disconnected"),
        (["1"], "disconnected"),
        (["6"], "unexpected frame"),
        ([emit_frame("reload", "/")], "reload"),
    ],
)
def test_a_frame_that_ends_the_session_fails_the_hydration(
    frames: list[str], match: str
):
    ws = FakeTransport(lambda message: frames if message == CONNECT_FRAME else [])
    with pytest.raises(ProtocolError, match=match):
        run(wire.WireSession(ws, "tok").hydrate())


@pytest.mark.parametrize(
    ("first", "match"), [(ACK, "did not open"), ("3", "unexpected frame")]
)
def test_a_server_that_does_not_open_fails_the_hydration(first: str, match: str):
    ws = FakeTransport(lambda message: [], greeting=[first])
    with pytest.raises(ProtocolError, match=match):
        run(wire.WireSession(ws, "tok").hydrate())


async def hydrated_exchange(
    ws: FakeTransport, shape_name: str, seq: int = 1
) -> wire.Exchange:
    session = wire.WireSession(ws, "tok")
    await session.hydrate()
    return await session.exchange(SHAPES[shape_name], seq)


def test_an_exchange_counts_the_request_and_its_reply():
    ws = FakeTransport(playground_script())
    exchange = run(hydrated_exchange(ws, "simple", seq=7))
    request = event_frame(SHAPES["simple"].name, {"seq": 7}, token="tok", pathname="/")
    reply = delta_frame({BENCH_STATE: {SEQ_VAR: 7}})
    assert ws.sent[-1] == request
    assert exchange.request_bytes == size(request)
    assert exchange.response_bytes == size(reply)
    assert exchange.response_frames == 1
    assert exchange.largest_frame_bytes == size(reply)
    assert exchange.delta_bytes == {BENCH_STATE: size('{"last_seq_rx_state_":7}')}
    assert exchange.reply == reply


def test_a_reply_spanning_frames_is_summed_until_the_echo():
    # 0.8.23 answers a background task with an empty update first.
    empty = delta_frame({}, events=[], final=True)
    echo = delta_frame({BENCH_STATE: {SEQ_VAR: 1}}, events=[], final=None)
    background = SHAPES["background"].name
    ws = FakeTransport(playground_script(replies={background: [empty, echo]}))
    exchange = run(hydrated_exchange(ws, "background"))
    assert exchange.response_bytes == size(empty, echo)
    assert exchange.response_frames == 2
    assert exchange.reply == echo
    # Nothing beyond the echo is read.
    assert not ws.inbox


def test_a_reply_touching_two_states_splits_its_bytes():
    cross = SHAPES["cross"].name
    reply = delta_frame({
        PLAYGROUND_STATE: {"count_rx_state_": 1},
        BENCH_STATE: {SEQ_VAR: 1},
    })
    ws = FakeTransport(playground_script(replies={cross: [reply]}))
    exchange = run(hydrated_exchange(ws, "cross"))
    assert exchange.delta_bytes == {
        PLAYGROUND_STATE: size('{"count_rx_state_":1}'),
        BENCH_STATE: size('{"last_seq_rx_state_":1}'),
    }
    assert exchange.response_bytes == size(reply)


def test_an_unrelated_delta_before_the_echo_counts_in_the_reply():
    simple = SHAPES["simple"].name
    other = delta_frame({BENCH_STATE: {SEQ_VAR: 0}})
    echo = delta_frame({BENCH_STATE: {SEQ_VAR: 1}})
    ws = FakeTransport(playground_script(replies={simple: [other, echo]}))
    exchange = run(hydrated_exchange(ws, "simple"))
    assert (exchange.response_bytes, exchange.response_frames) == (size(other, echo), 2)


def test_a_navigation_sends_on_load_from_the_new_route_until_hydrated_again():
    ws = FakeTransport(playground_script())
    session = wire.WireSession(ws, "tok")
    run(session.hydrate())
    exchange = run(session.navigate("/item/42", {"item_id": "42"}))
    request = event_frame(
        ON_LOAD_EVENT, {}, token="tok", pathname="/item/42", query={"item_id": "42"}
    )
    reply = navigation_reply({"pathname": "/item/42", "query": {"item_id": "42"}})
    assert ws.sent[-1] == request
    assert '"router_rx_state_":{"page":{"path":"/item/42"' in reply
    assert exchange == wire.Exchange(
        request_bytes=size(request),
        response_bytes=size(reply),
        response_frames=1,
        largest_frame_bytes=size(reply),
        delta_bytes={
            ROOT_STATE: size(
                '{"is_hydrated_rx_state_":true,"router_rx_state_":{"page":{"path":"/item/42","params":{"item_id":"42"}}}}'
            )
        },
        reply=reply,
    )
    # Later events come from the new route.
    run(session.exchange(SHAPES["simple"], 2))
    assert ws.sent[-1] == event_frame(
        SHAPES["simple"].name,
        {"seq": 2},
        token="tok",
        pathname="/item/42",
        query={"item_id": "42"},
    )


def test_a_navigation_with_on_load_events_is_summed_until_hydrated():
    # A page with on_load handlers: is_hydrated goes false, the handlers'
    # deltas follow, and the chain ends by setting it true again.
    unhydrated = delta_frame({ROOT_STATE: {HYDRATED_VAR: False}})
    loaded = delta_frame({PLAYGROUND_STATE: {"count_rx_state_": 3}})
    hydrated = delta_frame({ROOT_STATE: {HYDRATED_VAR: True}})
    ws = FakeTransport(
        playground_script(replies={ON_LOAD_EVENT: [unhydrated, loaded, hydrated]})
    )
    session = wire.WireSession(ws, "tok")
    run(session.hydrate())
    exchange = run(session.navigate("/counter", {}))
    assert exchange.response_bytes == size(unhydrated, loaded, hydrated)
    assert exchange.response_frames == 3
    assert exchange.reply == hydrated
    assert set(exchange.delta_bytes) == {ROOT_STATE, PLAYGROUND_STATE}
    assert not ws.inbox


def test_a_disconnect_while_waiting_for_the_reply_fails():
    simple = SHAPES["simple"].name
    ws = FakeTransport(playground_script(replies={simple: [DISCONNECT_FRAME]}))
    with pytest.raises(ProtocolError, match="disconnected"):
        run(hydrated_exchange(ws, "simple"))


def test_measure_connects_hydrates_and_leaves_the_namespace(
    monkeypatch: pytest.MonkeyPatch,
):
    transports: list[FakeTransport] = []
    urls: list[str] = []
    headers: list[dict[str, str]] = []

    @contextlib.asynccontextmanager
    async def connect(url: str, **kwargs: Any) -> AsyncIterator[FakeTransport]:
        urls.append(url)
        headers.append(kwargs["additional_headers"])
        transports.append(ws := FakeTransport(playground_script()))
        yield ws

    monkeypatch.setattr(wire, "connect", connect)
    hydration = wire.measure(
        Endpoint("http://localhost:8000", "/page"), wire.WireSession.hydrate
    )
    (ws,) = transports
    assert urls[0].startswith(
        "ws://localhost:8000/_event/?EIO=4&transport=websocket&token="
    )
    # A browser sends the page's origin; the router's page host comes from it.
    assert headers == [{"Origin": "http://localhost:8000"}]
    assert hydration.received_frames == 4
    assert ws.sent[-1] == DISCONNECT_FRAME
    assert '"pathname":"/page"' in ws.sent[1]


def test_measure_against_the_echo_server_counts_real_frames():
    with serving(EchoServer(delta_key=BENCH_STATE, seq_var=SEQ_VAR)) as url:

        async def work(
            session: wire.WireSession,
        ) -> tuple[wire.Hydration, wire.Exchange, wire.Exchange]:
            return (
                await session.hydrate(),
                await session.exchange(SHAPES["simple"], 3),
                await session.navigate("/counter", {}),
            )

        hydration, exchange, navigation = wire.measure(Endpoint(url), work)
    reply = emit_frame("event", {"delta": {BENCH_STATE: {SEQ_VAR: 3}}, "events": []})
    assert exchange.response_bytes == size(reply)
    assert exchange.reply == reply
    hydrated = emit_frame(
        "event", {"delta": {ROOT_STATE: {HYDRATED_VAR: True}}, "events": []}
    )
    assert navigation.reply == hydrated
    assert navigation.response_frames == 1
    # The token is a uuid4, so the request has a fixed length.
    assert navigation.request_bytes == size(
        event_frame(ON_LOAD_EVENT, {}, token="x" * 36, pathname="/counter")
    )
    assert hydration.received_frames == 4
    assert hydration.delta_bytes == {
        ROOT_STATE: size(
            '{"is_hydrated_rx_state_":false}', '{"is_hydrated_rx_state_":true}'
        )
    }


def test_measure_times_out(monkeypatch: pytest.MonkeyPatch):
    @contextlib.asynccontextmanager
    async def connect(url: str, **kwargs: Any) -> AsyncIterator[FakeTransport]:
        yield FakeTransport(lambda message: [])

    async def hang(session: wire.WireSession) -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(wire, "connect", connect)
    monkeypatch.setattr(wire, "WIRE_TIMEOUT_S", 0.05)
    with pytest.raises(TimeoutError):
        wire.measure(Endpoint("http://localhost:1"), hang)


ALLOWED_RX = {
    "State",
    "event",
    "Config",
    "App",
    "Component",
    "plugins",
    "text",
    "vstack",
    "heading",
}


def test_the_generated_app_is_valid_python_using_only_rx_apis():
    files = wire.delta_app_files()
    assert set(files) == {
        "rxconfig.py",
        "wire_delta/__init__.py",
        "wire_delta/state.py",
        "wire_delta/wire_delta.py",
    }
    handlers: set[str] = set()
    for path, source in files.items():
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert [alias.name for alias in node.names] == ["reflex"], path
                assert node.names[0].asname == "rx"
            elif isinstance(node, ast.ImportFrom):
                assert node.module == "wire_delta.state", path
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "rx"
            ):
                assert node.attr in ALLOWED_RX, f"{path}: rx.{node.attr}"
            elif (
                isinstance(node, ast.FunctionDef)
                and node.args.args[:1]
                and node.args.args[0].arg == "self"
            ):
                handlers.add(node.name)
    assert set(wire.CHANGES) <= handlers
    assert wire.CHANGES == CHANGES
    state = files["wire_delta/state.py"]
    assert "range(1000)" in state
    assert "range(200)" in state


def test_the_delta_shapes_echo_the_sequence_number():
    shape = wire.delta_shape("append_item")
    assert shape.name == f"{wire.WIRE_STATE}.append_item"
    assert shape.payload(4) == {"seq": 4}
    assert (shape.delta_key, shape.seq_var, shape.ordered) == (
        wire.WIRE_STATE,
        SEQ_VAR,
        True,
    )
    assert wire.WIRE_STATE == "reflex___state____state.wire_delta___state____wire_state"


def test_write_app_writes_the_files_and_hashes_them(tmp_path: Path):
    target = tmp_path / "app"
    target.mkdir()
    (target / "stale.py").write_text("gone\n")
    wire.write_app(target)
    written = sorted(
        str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()
    )
    assert written == sorted(wire.delta_app_files())
    assert (target / "wire_delta" / "state.py").read_text() == wire.delta_app_files()[
        "wire_delta/state.py"
    ]
    digest = wire.fixture_hash()
    assert digest.startswith("sha256:")
    assert len(digest) == 71
    assert digest == wire.fixture_hash()


def names(suite: str | None, *filters: str) -> list[str]:
    selected = registry.select(registry.discover().values(), filters, suite)
    return [planned.name for planned in plan(selected, suite=suite)]


def test_instance_ids_per_suite():
    cheap = ["wire.event[shape=simple]", "wire.hydrate", "wire.navigate[route=item]"]
    assert names("pr", "wire.*") == cheap
    assert names("smoke", "wire.*") == cheap
    everything = [
        *(f"wire.delta[change={change}]" for change in CHANGES),
        *(f"wire.event[shape={shape}]" for shape in SHAPES),
        "wire.hydrate",
        *(f"wire.navigate[route={route}]" for route in wire.ROUTES),
    ]
    assert names("daily", "wire.*") == everything
    assert names("all", "wire.*") == everything


def test_declarations():
    found = {
        bench_id: bench
        for bench_id, bench in registry.discover().items()
        if bench_id.startswith("wire.")
    }
    assert set(found) == {"wire.hydrate", "wire.event", "wire.navigate", "wire.delta"}
    assert set(found["wire.hydrate"].metrics) == {
        "hydrate_sent_bytes",
        "hydrate_received_bytes",
        "hydrate_frames",
    }
    for bench_id in ("wire.event", "wire.navigate"):
        assert set(found[bench_id].metrics) == {
            "request_bytes",
            "response_bytes",
            "response_frames",
        }
    assert wire.ROUTES == {
        "counter": ("/counter", {}),
        "item": ("/item/42", {"item_id": "42"}),
    }
    assert set(found["wire.delta"].metrics) == {"response_bytes"}
    for bench in found.values():
        assert bench.exact
        assert bench.kind == "track"
        assert bench.warmup == 0
        assert bench.min_version is None
        assert bench.setup_timeout > events_suite.COMPILE_TIMEOUT_S
        for name, metric in bench.metrics.items():
            assert metric.direction == "lower"
            assert metric.unit == ("1" if name.endswith("frames") else "B")


@dataclasses.dataclass
class Fakes:
    """What the fake app and websocket saw.

    Attributes:
        log: What happened, in order.
        compiled: The directories ``reflex compile`` ran in.
        envs: The environment of every started server.
        replies: The frames answering an event, by handler name.
    """

    log: list[str] = dataclasses.field(default_factory=list)
    compiled: list[Path] = dataclasses.field(default_factory=list)
    envs: list[dict[str, str]] = dataclasses.field(default_factory=list)
    replies: dict[str, list[str]] = dataclasses.field(default_factory=dict)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    state = Fakes()
    log = state.log

    def run_cli(python, args, *, cwd, env, timeout):  # fmt: skip
        log.append(f"run_cli {args[0]}")
        state.compiled.append(cwd)
        return CliResult(
            args=list(args), returncode=0, wall_s=1.0, lines=[], timeout_s=timeout
        )

    class FakeApp:
        def __init__(self, python, app_dir, *, mode, reflex_version, env, backend_only, start_timeout):  # fmt: skip
            assert (mode, backend_only) == ("prod", True)
            state.envs.append(env)
            self.backend_url = "http://localhost:8000"

        def start(self) -> None:
            log.append("app start")

        def wait_http_ready(self, timeout: float) -> float:
            return 1.0

        def stop(self) -> None:
            log.append("app stop")

    @contextlib.asynccontextmanager
    async def connect(url: str, **kwargs: Any) -> AsyncIterator[FakeTransport]:
        log.append("connect")
        yield FakeTransport(playground_script(replies=state.replies))

    monkeypatch.setattr(events_suite, "run_cli", run_cli)
    monkeypatch.setattr(
        events_suite,
        "copy_tracked",
        lambda source, target: log.append("copy playground"),
    )
    monkeypatch.setattr(wire, "run_cli", run_cli)
    monkeypatch.setattr(wire, "playground_states", lambda ctx: STATES)
    monkeypatch.setattr(wire, "AppProcess", FakeApp)
    monkeypatch.setattr(wire, "connect", connect)
    return state


def run_bench(tmp_path: Path, bench_id: str, **params: str) -> dict[str, Any]:
    bench = registry.discover()[bench_id]
    (param_set,) = bench.expand(params)
    runner = Scheduler(make_subject(), Policy(warmup=0), home=tmp_path, seed=1)
    return dict(runner.run_one(Planned(bench, param_set)))


def test_hydrate_starts_a_backend_per_sample_and_stops_it(tmp_path: Path, fakes: Fakes):
    entry = run_bench(tmp_path, "wire.hydrate")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"fixture": "playground"}
    assert entry["fixture_hash"] == fixtures.fixture_hash("playground")
    # Exact metrics: one sample.
    assert fakes.log == [
        "copy playground",
        "run_cli compile",
        "app start",
        "connect",
        "app stop",
    ]
    script = playground_script()
    # The token is a uuid4, so the sent frames only have a fixed length.
    hydrate = event_frame(HYDRATE_EVENT, {}, token="x" * 36)
    on_load = event_frame(ON_LOAD_EVENT, {}, token="x" * 36)
    first, second = script(hydrate)[0], script(on_load)[0]
    samples = {
        name: metric["samples"]["A"] for name, metric in entry["metrics"].items()
    }
    assert samples["hydrate_received_bytes"] == [size(OPEN, ACK, first, second)]
    assert samples["hydrate_frames"] == [4]
    assert samples["hydrate_sent_bytes"] == [size(CONNECT_FRAME, hydrate, on_load)]
    (extra,) = entry["sample_extra"]
    assert extra["largest_frame_bytes"] == size(first)
    assert set(extra["delta_bytes"]) == {ROOT_STATE, BENCH_STATE, PLAYGROUND_STATE}
    assert extra["sent_frames"] == 3
    (env,) = fakes.envs
    assert env["REFLEX_STATE_MANAGER_MODE"] == "memory"
    assert env["GRANIAN_WORKERS"] == "1"
    (compiled,) = fakes.compiled
    assert compiled.name == "app"
    assert compiled.is_relative_to(tmp_path / "cache")


def test_event_measures_one_exchange_per_shape(tmp_path: Path, fakes: Fakes):
    background = SHAPES["background"].name
    empty = delta_frame({}, events=[], final=True)
    echo = delta_frame({BENCH_STATE: {SEQ_VAR: 1}}, events=[], final=None)
    fakes.replies[background] = [empty, echo]
    entry = run_bench(tmp_path, "wire.event", shape="background")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"fixture": "playground"}
    assert entry["fixture_hash"] == fixtures.fixture_hash("playground")
    samples = {
        name: metric["samples"]["A"] for name, metric in entry["metrics"].items()
    }
    assert samples["response_bytes"] == [size(empty, echo)]
    assert samples["response_frames"] == [2]
    request = event_frame(background, {"seq": 1}, token="x" * 36, pathname="/")
    assert samples["request_bytes"] == [size(request)]
    (extra,) = entry["sample_extra"]
    assert extra["reply"] == echo
    assert extra["hydration"]["received_frames"] == 4
    assert fakes.log == [
        "copy playground",
        "run_cli compile",
        "app start",
        "connect",
        "app stop",
    ]


def test_navigate_measures_the_route_change_after_hydration(
    tmp_path: Path, fakes: Fakes
):
    entry = run_bench(tmp_path, "wire.navigate", route="item")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"fixture": "playground"}
    assert entry["fixture_hash"] == fixtures.fixture_hash("playground")
    samples = {
        name: metric["samples"]["A"] for name, metric in entry["metrics"].items()
    }
    request = event_frame(
        ON_LOAD_EVENT,
        {},
        token="x" * 36,
        pathname="/item/42",
        query={"item_id": "42"},
    )
    reply = navigation_reply({"pathname": "/item/42", "query": {"item_id": "42"}})
    assert samples["request_bytes"] == [size(request)]
    assert samples["response_bytes"] == [size(reply)]
    assert samples["response_frames"] == [1]
    (extra,) = entry["sample_extra"]
    assert extra["reply"] == reply
    # Hydrated on "/" first: its on_load reply carries no router.
    assert extra["hydration"]["received_frames"] == 4
    assert extra["hydration"]["delta_bytes"][ROOT_STATE] == size(
        '{"is_hydrated_rx_state_":false,"router_rx_state_":{"a":1}}',
        '{"is_hydrated_rx_state_":true}',
    )
    assert fakes.log == [
        "copy playground",
        "run_cli compile",
        "app start",
        "connect",
        "app stop",
    ]


def test_delta_generates_its_own_app_and_keys_the_series_on_its_hash(
    tmp_path: Path, fakes: Fakes
):
    # The change's reply carries the whole list, as a resent collection would.
    items = [*range(1000), 1]
    fakes.replies[f"{wire.WIRE_STATE}.append_item"] = [
        delta_frame({wire.WIRE_STATE: {"items_rx_state_": items, SEQ_VAR: 1}})
    ]
    entry = run_bench(tmp_path, "wire.delta", change="append_item")
    assert entry["status"] == "ok", entry["error"]
    assert entry["dims"] == {"fixture": "wire_delta"}
    assert entry["fixture_hash"] == wire.fixture_hash()
    assert fakes.log == ["run_cli compile", "app start", "connect", "app stop"]
    (app,) = fakes.compiled
    assert (app / "rxconfig.py").is_file()
    assert (app / "wire_delta" / "state.py").read_text() == wire.delta_app_files()[
        "wire_delta/state.py"
    ]
    reply = delta_frame({wire.WIRE_STATE: {"items_rx_state_": items, SEQ_VAR: 1}})
    assert entry["metrics"]["response_bytes"]["samples"]["A"] == [size(reply)]
    (extra,) = entry["sample_extra"]
    assert extra["request_bytes"] == size(
        event_frame(f"{wire.WIRE_STATE}.append_item", {"seq": 1}, token="x" * 36)
    )
    assert extra["response_frames"] == 1
    assert extra["delta_bytes"] == {
        wire.WIRE_STATE: size(
            json.dumps({"items_rx_state_": items, SEQ_VAR: 1}, separators=(",", ":"))
        )
    }


def test_a_failed_sample_still_stops_the_backend(tmp_path: Path, fakes: Fakes):
    fakes.replies[SHAPES["simple"].name] = [DISCONNECT_FRAME]
    entry = run_bench(tmp_path, "wire.event", shape="simple")
    assert entry["status"] == "failed"
    assert "disconnected" in entry["error"]
    assert fakes.log[-1] == "app stop"
