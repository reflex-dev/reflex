"""Benchmark counter and table events through the in-memory event pipeline."""

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
from reflex_base.utils.format import format_event_handler, json_dumps

from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import StateUpdate

from .fixtures import BenchmarkState, TableState


@pytest_asyncio.fixture(params=["counter", "table"])
async def event_processing_harness(request: pytest.FixtureRequest):
    """Set up a fixed event batch, warming the table before timing.

    Args:
        request: Selects the counter or table workload.

    Yields:
        An async callable that processes one batch and checks its delta count.
    """
    table = request.param == "table"
    handler = (
        TableState.event_handlers["set_status"]
        if table
        else BenchmarkState.event_handlers["increment"]
    )
    payloads = (
        [{"status": status} for status in ("open", "", "paid") * 2]
        if table
        else [{}] * 3
    )
    events = [
        Event(
            name=format_event_handler(handler),
            router_data={"query": {}, "path": "/"},
            payload=payload,
        )
        for payload in payloads
    ]
    emitted = 0

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        nonlocal emitted
        emitted += 1
        if table:
            json_dumps(StateUpdate(delta=delta), separators=(",", ":"))

    async def emit_event_impl(token: str, *events: Event) -> None:
        pass

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    processor = BaseStateEventProcessor(
        backend_exception_handler=handle_backend_exception,
        graceful_shutdown_timeout=5,
    )
    # Skip initial hydration because there is no frontend.
    with mock.patch.object(processor, "_rehydrate", new=mock.AsyncMock()):
        state_manager = StateManagerMemory()
        processor._root_context = EventContext(
            token="",
            state_manager=state_manager,
            enqueue_impl=processor.enqueue_many,
            emit_delta_impl=emit_delta_impl,
            emit_event_impl=emit_event_impl,
        )

        async def run_events() -> None:
            """Process the batch and verify that each event emitted a delta."""
            nonlocal emitted
            emitted = 0
            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue("benchmark-token", event) for event in events
                ]):
                    pass
            assert emitted == len(events)

        try:
            if table:
                await run_events()
            yield run_events
        finally:
            await state_manager.close()


def test_process_event(event_processing_harness, benchmark: BenchmarkFixture):
    """Benchmark a batch of three counter events or six table events.

    Args:
        event_processing_harness: The async batch runner.
        benchmark: The codspeed benchmark fixture.
    """
    loop = asyncio.get_event_loop()

    @benchmark
    def _():
        loop.run_until_complete(event_processing_harness())
