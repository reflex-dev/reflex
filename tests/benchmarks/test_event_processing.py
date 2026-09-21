"""Benchmarks for the event processing pipeline."""

import asyncio
import contextlib
import json
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event
from reflex_base.event.context import EmitDeltaProtocol, EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.utils.format import (
    format_event_handler,
    orjson_dumps_socket,
    orjson_loads,
)

import reflex as rx
from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import StateUpdate

from .fixtures import BenchmarkState, TableState

TOKEN = "benchmark-token"
ROUTER_DATA = {"query": {}, "path": "/"}
TABLE_STATUSES = ("open", "", "paid")


def _make_rows(count: int) -> list[dict[str, str | int | float | bool]]:
    """Build a deterministic table-like payload.

    Args:
        count: Number of rows to generate.

    Returns:
        A list of row dicts with mixed scalar types.
    """
    return [
        {
            "id": i,
            "name": f"customer_{i}",
            "email": f"user{i}@example.com",
            "balance": i * 1.37,
            "active": i % 2 == 0,
            "notes": "lorem ipsum dolor sit amet " * 3,
        }
        for i in range(count)
    ]


class WireBenchState(rx.State):
    """State whose handler produces a realistic table-sized delta."""

    rows: rx.Field[list[dict[str, str | int | float | bool]]] = rx.field(
        default_factory=list
    )

    @rx.event
    def refresh_rows(self, count: int):
        """Replace the rows with a freshly generated table.

        Args:
            count: Number of rows to generate.
        """
        self.rows = _make_rows(count)


def _handle_backend_exception(ex: Exception) -> None:
    formatted_exc = "\n".join(traceback.format_exception(ex))
    pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")


@contextlib.asynccontextmanager
async def _processing_pipeline(emit_delta_impl: EmitDeltaProtocol):
    """Wire a ``BaseStateEventProcessor`` to a real ``StateManagerMemory``.

    Args:
        emit_delta_impl: Callback receiving each emitted (token, delta).

    Yields:
        The configured processor.
    """

    async def emit_event_impl(token: str, *events: Event) -> None:
        pass

    processor = BaseStateEventProcessor(
        backend_exception_handler=_handle_backend_exception,
        graceful_shutdown_timeout=5,
    )
    # There is no frontend to receive the initial full-state push.
    with mock.patch.object(processor, "_rehydrate", new=mock.AsyncMock()):
        state_manager = StateManagerMemory()
        processor._root_context = EventContext(
            token="",
            state_manager=state_manager,
            enqueue_impl=processor.enqueue_many,
            emit_delta_impl=emit_delta_impl,
            emit_event_impl=emit_event_impl,
        )
        try:
            yield processor
        finally:
            await state_manager.close()


def _encode_delta(delta: Mapping[str, Mapping[str, Any]]) -> str:
    """Serialize a delta the way the socket path does.

    Args:
        delta: The state changes emitted by the processor.

    Returns:
        The delta encoded as a StateUpdate envelope.
    """
    return orjson_dumps_socket(StateUpdate(delta=delta), separators=(",", ":"))


def _events(handler_name: str, payloads: list[dict[str, Any]]) -> list[Event]:
    """Build one event per payload for the given handler.

    Args:
        handler_name: The formatted event handler name.
        payloads: One payload per event.

    Returns:
        The events to enqueue.
    """
    return [
        Event(name=handler_name, router_data=ROUTER_DATA, payload=payload)
        for payload in payloads
    ]


def _counter_events() -> list[Event]:
    """Two increments followed by two decrements, returning to the start.

    Returns:
        The counter event batch.
    """
    increment = format_event_handler(BenchmarkState.event_handlers["increment"])
    decrement = format_event_handler(BenchmarkState.event_handlers["decrement"])
    return _events(increment, [{}] * 2) + _events(decrement, [{}] * 2)


def _table_events() -> list[Event]:
    """Two filter cycles, ending on the starting sort direction.

    Returns:
        The table event batch.
    """
    set_status = format_event_handler(TableState.event_handlers["set_status"])
    return _events(set_status, [{"status": status} for status in TABLE_STATUSES * 2])


@contextlib.asynccontextmanager
async def _event_pipeline(
    events: list[Event],
    on_delta: Callable[[Mapping[str, Mapping[str, Any]]], Any],
) -> AsyncIterator[Callable[[], Awaitable[None]]]:
    """Wire the processing pipeline to a fixed batch of events.

    Args:
        events: The batch to enqueue on each run.
        on_delta: Called with each emitted delta.

    Yields:
        An async callable that processes one batch and checks its delta count.
    """
    emitted = 0

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        nonlocal emitted
        emitted += 1
        on_delta(delta)

    async with _processing_pipeline(emit_delta_impl) as processor:

        async def run_events() -> None:
            """Process the batch and verify that each event emitted a delta."""
            nonlocal emitted
            emitted = 0
            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue(TOKEN, event) for event in events
                ]):
                    pass
            assert emitted == len(events)

        yield run_events


@pytest_asyncio.fixture(params=["counter", "table"])
async def event_processing_harness(request: pytest.FixtureRequest):
    """Set up a fixed event batch, warming the table before timing.

    Both batches return state to its starting point, so every benchmark
    sample measures identical work.

    Args:
        request: Selects the counter or table workload.

    Yields:
        An async callable that processes one batch and checks its delta count.
    """
    table = request.param == "table"
    events = _table_events() if table else _counter_events()
    on_delta = _encode_delta if table else (lambda delta: None)
    async with _event_pipeline(events, on_delta) as run_events:
        if table:
            await run_events()
        yield run_events


def test_process_event(event_processing_harness, benchmark: BenchmarkFixture):
    """Benchmark a batch of four counter events or six table events.

    Args:
        event_processing_harness: The async batch runner.
        benchmark: The codspeed benchmark fixture.
    """
    loop = asyncio.get_event_loop()

    @benchmark
    def _():
        loop.run_until_complete(event_processing_harness())


@pytest.mark.asyncio
async def test_table_event_deltas():
    """Verify filtered rows, sort direction, and totals across repeated batches."""
    updates: list[str] = []

    async with _event_pipeline(
        _table_events(), lambda delta: updates.append(_encode_delta(delta))
    ) as run_events:
        for _ in range(2):
            await run_events()

    for index, update in enumerate(updates):
        status = TABLE_STATUSES[index % len(TABLE_STATUSES)]
        reverse = index % 2 == 0
        expected = [
            {
                "name": f"order {i}",
                "customer": f"customer {i % 50}",
                "amount": i * 1.5,
                "status": ("open", "paid", "shipped")[i % 3],
            }
            for i in sorted(range(1000), reverse=reverse)
            if not status or ("open", "paid", "shipped")[i % 3] == status
        ]
        delta = json.loads(update)["delta"][TableState.get_full_name()]
        assert delta["status" + FIELD_MARKER] == status
        assert delta["sort_reverse" + FIELD_MARKER] == reverse
        assert delta["filtered_orders" + FIELD_MARKER] == expected
        assert delta["total_amount" + FIELD_MARKER] == sum(
            row["amount"] for row in expected
        )


@pytest_asyncio.fixture
async def wire_event_processing_harness():
    """Set up event processing with JSON decoding and encoding.

    Yields:
        An async callable taking raw event JSON strings and the expected
        number of serialized wire payloads.
    """
    wire_payloads: list[str] = []

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        wire_payloads.append(
            orjson_dumps_socket(
                ["event", StateUpdate(delta=delta)], separators=(",", ":")
            )
        )

    async with _processing_pipeline(emit_delta_impl) as processor:

        async def run_raw_events(raw_events: list[str], num_expected: int) -> None:
            """Decode, enqueue, and serialize the given raw events.

            Args:
                raw_events: JSON strings, each an encoded event.
                num_expected: How many wire payloads to expect.
            """
            wire_payloads.clear()

            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue(
                        TOKEN,
                        Event(
                            name=(fields := orjson_loads(raw))["name"],
                            router_data=fields["router_data"],
                            payload=fields["payload"],
                        ),
                    )
                    for raw in raw_events
                ]):
                    pass
            assert len(wire_payloads) == num_expected

        yield run_raw_events


@pytest.mark.parametrize("row_count", [5, 500], ids=["small_delta", "large_delta"])
def test_process_event_wire(
    wire_event_processing_harness,
    benchmark: BenchmarkFixture,
    row_count: int,
):
    """Benchmark receiving, processing, and serializing three events.

    Args:
        wire_event_processing_harness: The run_raw_events async callable.
        benchmark: The codspeed benchmark fixture.
        row_count: Rows per delta (small ~2KB, large ~200KB wire payload).
    """
    run_raw_events = wire_event_processing_harness
    loop = asyncio.get_event_loop()

    handler_name = format_event_handler(WireBenchState.event_handlers["refresh_rows"])
    raw_events = [
        json.dumps({
            "name": handler_name,
            "router_data": ROUTER_DATA,
            "payload": {"count": row_count},
        })
        for _ in range(3)
    ]

    # refresh_rows reassigns the rows field, so each event yields 1 delta.
    @benchmark
    def _():
        loop.run_until_complete(run_raw_events(raw_events, num_expected=3))


@pytest.fixture
def on_event_harness():
    """Set up an EventNamespace with a connected socket for benchmarking on_event.

    The event processor's enqueue is mocked out so the benchmark isolates the
    per-event router_data preparation (which reuses the connection-scoped
    data gathered once in on_connect).

    Yields:
        An async callable that feeds the given number of events through
        ``EventNamespace.on_event``, and the event loop to drive it with.
    """
    from reflex.app import App, EventNamespace

    app = App()
    app._event_processor = mock.Mock(enqueue=mock.AsyncMock())
    namespace = EventNamespace("/event", app)

    sid = "benchmark-sid"
    environ = {
        "QUERY_STRING": "token=benchmark-token",
        "asgi.scope": {
            "headers": [
                (b"host", b"localhost:3000"),
                (b"origin", b"http://localhost:3000"),
                (b"user-agent", b"Mozilla/5.0 (X11; Linux x86_64) benchmark"),
                (b"accept-encoding", b"gzip, deflate, br"),
                (b"accept-language", b"en-US,en;q=0.9"),
                (b"cookie", b"session=abc123; theme=dark"),
                (b"upgrade", b"websocket"),
                (b"connection", b"Upgrade"),
                (b"sec-websocket-version", b"13"),
                (b"sec-websocket-key", b"dGhlIHNhbXBsZSBub25jZQ=="),
                (b"x-forwarded-for", b"203.0.113.7, 10.0.0.1"),
            ],
            "client": ("127.0.0.1", 54321),
        },
    }

    async def run_events(num_events: int) -> None:
        """Feed events through on_event.

        Args:
            num_events: Number of events to process.
        """
        for _ in range(num_events):
            await namespace.on_event(
                sid,
                {
                    "name": "state.hydrate",
                    "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
                    "payload": {},
                },
            )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(namespace.on_connect(sid, environ))
    yield run_events, loop
    loop.close()


def test_on_event_router_data(
    on_event_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark the per-event router_data preparation in on_event.

    Headers and client IP are gathered once at connect time, so the
    per-event path is reduced to merging the cached connection-scoped dict
    with the event's navigation data.

    Args:
        on_event_harness: The run_events async callable and its event loop.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, loop = on_event_harness

    @benchmark
    def _():
        loop.run_until_complete(run_events(num_events=10))
