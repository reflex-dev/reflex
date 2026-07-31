"""Benchmarks for the event processing pipeline."""

import asyncio
import contextlib
import json
import traceback
from collections.abc import Mapping
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
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

from .fixtures import BenchmarkState

TOKEN = "benchmark-token"
ROUTER_DATA = {"query": {}, "path": "/"}


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


@pytest_asyncio.fixture
async def event_processing_harness():
    """Set up the full event processing pipeline for benchmarking.

    Creates a ``BaseStateEventProcessor`` wired to a real
    ``StateManagerMemory`` with mock emit callbacks.  Events are
    enqueued directly and deltas are collected via the emit callback.

    Yields:
        An async callable that enqueues the given number of events
        and waits for all expected deltas.
    """
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]] = []

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        emitted_deltas.append((token, delta))

    async with _processing_pipeline(emit_delta_impl) as processor:
        handler_name = format_event_handler(BenchmarkState.event_handlers["increment"])
        event = Event(
            name=handler_name,
            router_data=ROUTER_DATA,
            payload={},
        )

        async def run_events(num_events: int, num_expected_deltas: int) -> None:
            """Enqueue events and wait for all deltas to be emitted.

            Args:
                num_events: Number of increment events to enqueue.
                num_expected_deltas: How many deltas to wait for.
            """
            emitted_deltas.clear()

            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue(TOKEN, event) for _ in range(num_events)
                ]):
                    pass
            assert len(emitted_deltas) == num_expected_deltas

        yield run_events


def test_process_event(
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark processing 3 increment events through the full pipeline.

    The first event creates fresh state (cold path), the next two reuse
    the existing state (warm path).  Only event processing is timed.

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
        loop.run_until_complete(run_events(num_events=3, num_expected_deltas=3))


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
