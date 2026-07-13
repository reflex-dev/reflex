"""Benchmark for the event processing pipeline.

Measures the time from enqueuing events via ``BaseStateEventProcessor``
to collecting all emitted ``StateUpdate`` deltas, with mock emit
callbacks that record the deltas.
"""

import asyncio
import traceback
from collections.abc import Mapping, Sequence
from typing import Any
from unittest import mock

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.utils.format import format_event_handler

from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken

from .fixtures import BenchmarkState


@pytest.fixture
def event_processing_harness():
    """Set up the full event processing pipeline for benchmarking.

    Creates a ``BaseStateEventProcessor`` wired to a real
    ``StateManagerMemory`` with mock emit callbacks.  Events are
    enqueued directly and deltas are collected via the emit callback.

    Yields:
        An async event runner, a helper that purges token state between
        explicitly cold benchmark rounds, and the state manager's async
        ``close``, which each test must run on its own event loop before
        closing it.
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

        handler_name = format_event_handler(BenchmarkState.event_handlers["increment"])
        event = Event(
            name=handler_name,
            router_data={
                "query": {},
                "path": "/",
            },
            payload={},
        )

        async def run_events(tokens: Sequence[str]) -> None:
            """Enqueue events for the given tokens and wait for their deltas.

            Args:
                tokens: Client tokens to enqueue one increment event for.
            """
            emitted_deltas.clear()

            async with processor as p:
                async for _ in asyncio.as_completed([
                    await p.enqueue(token, event) for token in tokens
                ]):
                    pass
            assert len(emitted_deltas) == len(tokens)

        def purge_tokens(tokens: Sequence[str]) -> None:
            """Remove benchmark tokens from the in-memory state manager.

            Args:
                tokens: Client tokens whose state and lock bookkeeping should be removed.
            """
            for token in tokens:
                state_manager._purge_token(  # pyright: ignore [reportPrivateUsage]
                    BaseStateToken(ident=token, cls=BenchmarkState)
                )

        yield run_events, purge_tokens, state_manager.close


def test_process_event(
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark processing 3 increment events through the full pipeline.

    The first event creates fresh state (cold path), the next two reuse
    the existing state (warm path).  Only event processing is timed.

    The token is purged in per-round setup so the cold path is exercised on
    every measured round. Without it, CodSpeed's warmup invocation hydrates the
    shared token and every subsequent round would measure three warm events,
    silently duplicating ``test_process_event_warm``.

    Args:
        event_processing_harness: The event runner, token purge, and shutdown helpers.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, purge_tokens, shutdown = event_processing_harness
    loop = asyncio.new_event_loop()

    def setup():
        """Return the batch args after purging the token for a cold round."""
        purge_tokens(["benchmark-token"])
        # Each event handler (increment) does a single state mutation with
        # no yields, so we expect 1 delta per event = 3 total.
        return ((["benchmark-token"] * 3,), {})

    def run_batch(tokens):
        """Process one cold-then-warm batch for the given tokens."""
        loop.run_until_complete(run_events(tokens))

    try:
        benchmark.pedantic(run_batch, setup=setup)
    finally:
        loop.run_until_complete(shutdown())
        loop.close()


def test_process_event_cold(
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark one event whose token has no existing state.

    Args:
        event_processing_harness: The event runner, token purge, and shutdown helpers.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, purge_tokens, shutdown = event_processing_harness
    loop = asyncio.new_event_loop()
    iteration = 0

    def setup():
        """Return a unique cold token for the next measured round."""
        nonlocal iteration
        iteration += 1
        return ((f"cold-token-{iteration}",), {})

    def run_cold(token: str) -> None:
        """Process one event with no state cached for its token."""
        loop.run_until_complete(run_events([token]))

    def teardown(token: str) -> None:
        """Discard the measured token so cold rounds do not retain state."""
        purge_tokens([token])

    try:
        benchmark.pedantic(run_cold, setup=setup, teardown=teardown)
    finally:
        loop.run_until_complete(shutdown())
        loop.close()


def test_process_event_warm(
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark one event for a token whose state is already initialized.

    Args:
        event_processing_harness: The event runner, token purge, and shutdown helpers.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, _, shutdown = event_processing_harness
    loop = asyncio.new_event_loop()
    try:
        token = "warm-token"
        loop.run_until_complete(run_events([token]))

        @benchmark
        def _():
            loop.run_until_complete(run_events([token]))

    finally:
        loop.run_until_complete(shutdown())
        loop.close()


@pytest.mark.parametrize("num_events", [1, 10, 100])
def test_process_event_burst_same_token(
    num_events: int,
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark queued events serialized through one token.

    Args:
        num_events: Number of events in the burst.
        event_processing_harness: The event runner, token purge, and shutdown helpers.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, _, shutdown = event_processing_harness
    loop = asyncio.new_event_loop()
    try:
        tokens = ["burst-token"] * num_events
        loop.run_until_complete(run_events([tokens[0]]))

        @benchmark
        def _():
            loop.run_until_complete(run_events(tokens))

    finally:
        loop.run_until_complete(shutdown())
        loop.close()


@pytest.mark.parametrize("num_events", [1, 10, 100])
def test_process_event_burst_independent_tokens(
    num_events: int,
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark queued events distributed across independent tokens.

    Args:
        num_events: Number of independent tokens and events.
        event_processing_harness: The event runner, token purge, and shutdown helpers.
        benchmark: The codspeed benchmark fixture.
    """
    run_events, _, shutdown = event_processing_harness
    loop = asyncio.new_event_loop()
    try:
        tokens = [f"independent-token-{index}" for index in range(num_events)]
        loop.run_until_complete(run_events(tokens))

        @benchmark
        def _():
            loop.run_until_complete(run_events(tokens))

    finally:
        loop.run_until_complete(shutdown())
        loop.close()
