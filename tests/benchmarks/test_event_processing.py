"""Benchmark for the event processing pipeline.

Measures the time from enqueuing events via ``BaseStateEventProcessor``
to collecting all emitted ``StateUpdate`` deltas, with mock emit
callbacks that record the deltas.
"""

import asyncio
import traceback
from collections.abc import Mapping
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.utils.format import format_event_handler

from reflex.istate.manager.memory import StateManagerMemory

from .fixtures import BenchmarkState


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
        handler_name = format_event_handler(BenchmarkState.event_handlers["increment"])
        event = Event(
            name=handler_name,
            router_data={
                "query": {},
                "path": "/",
            },
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
                    await p.enqueue(token, event) for _ in range(num_events)
                ]):  # ty:ignore[not-iterable]
                    pass
            assert len(emitted_deltas) == num_expected_deltas

        yield run_events

        await state_manager.close()


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
