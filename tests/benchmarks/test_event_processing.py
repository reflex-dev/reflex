"""Benchmarks for the event processing pipeline.

Events are enqueued via ``BaseStateEventProcessor`` against a real
``StateManagerMemory`` and every emitted delta is collected. The
``test_process_event`` benchmark times the pipeline alone; the table
benchmark also encodes each delta for the wire the way the socket path does.
"""

import asyncio
import json
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.utils.format import format_event_handler, json_dumps

from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import StateUpdate

from .fixtures import BenchmarkState, TableState

RunEvents = Callable[[int, int], Awaitable[None]]


@asynccontextmanager
async def _event_pipeline(
    handler_name: str,
    payloads: list[dict[str, Any]],
    on_delta: Callable[[Mapping[str, Mapping[str, Any]]], None],
) -> AsyncIterator[RunEvents]:
    """Wire a ``BaseStateEventProcessor`` to an in-memory state manager.

    Args:
        handler_name: The formatted event handler name to enqueue.
        payloads: The payloads to cycle through, one per enqueued event.
        on_delta: Called with each emitted delta.

    Yields:
        An async callable that enqueues the given number of events and
        waits for all expected deltas.
    """
    emitted = 0

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        nonlocal emitted
        emitted += 1
        on_delta(delta)

    async def emit_event_impl(token: str, *events: Event) -> None:
        pass

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    processor = BaseStateEventProcessor(
        backend_exception_handler=handle_backend_exception,
        graceful_shutdown_timeout=5,
    )
    # Mock _rehydrate so the processor doesn't try to push full state
    # to a non-existent frontend on the first event.
    with mock.patch.object(processor, "_rehydrate", new=mock.AsyncMock()):
        state_manager = StateManagerMemory()
        root_context = EventContext(
            token="",
            state_manager=state_manager,
            enqueue_impl=processor.enqueue_many,
            emit_delta_impl=emit_delta_impl,
            emit_event_impl=emit_event_impl,
        )
        processor._root_context = root_context

        token = "benchmark-token"
        events = [
            Event(
                name=handler_name,
                router_data={"query": {}, "path": "/"},
                payload=payload,
            )
            for payload in payloads
        ]

        async def run_events(num_events: int, num_expected_deltas: int) -> None:
            """Enqueue events and wait for all deltas to be emitted.

            Args:
                num_events: Number of events to enqueue, cycling the payloads.
                num_expected_deltas: How many deltas to wait for.
            """
            nonlocal emitted
            emitted = 0

            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue(token, events[i % len(events)])
                    for i in range(num_events)
                ]):
                    pass
            assert emitted == num_expected_deltas

        try:
            yield run_events
        finally:
            await state_manager.close()


@pytest_asyncio.fixture
async def event_processing_harness():
    """Set up the pipeline for ``BenchmarkState.increment`` with a mock emit.

    Yields:
        An async callable that enqueues the given number of events
        and waits for all expected deltas.
    """
    handler_name = format_event_handler(BenchmarkState.event_handlers["increment"])
    async with _event_pipeline(handler_name, [{}], lambda delta: None) as run:
        yield run


@pytest_asyncio.fixture
async def table_event_harness():
    """Set up the pipeline for ``TableState.set_status`` with wire encoding.

    Deltas use Reflex's JSON encoder and StateUpdate envelope. Socket.IO
    packet framing, network transport, and frontend rendering are excluded.

    Yields:
        An async callable that enqueues the given number of events
        and waits for all expected deltas.
    """
    handler_name = format_event_handler(TableState.event_handlers["set_status"])
    payloads = [{"status": "open"}, {"status": ""}, {"status": "paid"}]

    def encode(delta: Mapping[str, Mapping[str, Any]]) -> None:
        """Serialize a delta using the application's JSON encoder.

        Args:
            delta: The state changes emitted by the processor.
        """
        json_dumps(StateUpdate(delta=delta), separators=(",", ":"))

    async with _event_pipeline(handler_name, payloads, encode) as run:
        # Warm caches and finish two filter cycles so sort direction repeats.
        await run(6, 6)
        yield run


def test_process_event(
    event_processing_harness: RunEvents,
    benchmark: BenchmarkFixture,
):
    """Benchmark processing 3 increment events through the full pipeline.

    The first invocation creates fresh state; subsequent invocations reuse
    it. Processor startup and shutdown are included in the timing.

    Args:
        event_processing_harness: The run_events async callable.
        benchmark: The codspeed benchmark fixture.
    """
    run_events = event_processing_harness
    loop = asyncio.get_event_loop()

    # Each event handler (increment) does a single state mutation with
    # no yields, so we expect 1 delta per event = 3 total.
    @benchmark
    def _():
        loop.run_until_complete(run_events(3, 3))


def test_process_table_event(
    table_event_harness: RunEvents,
    benchmark: BenchmarkFixture,
):
    """Benchmark 6 filter events on a warm 1000-row table with JSON encoding.

    Every event assigns base vars, iterates the proxied rows, sorts them,
    recomputes both computed vars with their return-type checks, and
    produces a delta of hundreds of dataclass rows that is encoded like a
    real update.

    Args:
        table_event_harness: The run_events async callable.
        benchmark: The codspeed benchmark fixture.
    """
    run_events = table_event_harness
    loop = asyncio.get_event_loop()

    @benchmark
    def _():
        loop.run_until_complete(run_events(6, 6))


@pytest.mark.asyncio
async def test_table_event_deltas():
    """Verify filtered rows, sort direction, and totals across repeated batches."""
    updates: list[str] = []

    def record(delta: Mapping[str, Mapping[str, Any]]) -> None:
        """Capture serialized updates for assertions outside the benchmark.

        Args:
            delta: The state changes emitted by the processor.
        """
        updates.append(json_dumps(StateUpdate(delta=delta), separators=(",", ":")))

    statuses = ["open", "", "paid"]
    handler_name = format_event_handler(TableState.event_handlers["set_status"])
    async with _event_pipeline(
        handler_name, [{"status": status} for status in statuses], record
    ) as run:
        for _ in range(2):
            await run(6, 6)

    for index, update in enumerate(updates):
        status = statuses[index % len(statuses)]
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
