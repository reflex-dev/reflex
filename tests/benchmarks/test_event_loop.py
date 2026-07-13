"""Deterministic benchmarks for event-processor scheduling and lifecycle paths."""

import asyncio
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast

from pytest_codspeed import BenchmarkFixture
from reflex_base.event.context import EventContext
from reflex_base.event.processor.event_processor import EventProcessor
from reflex_base.registry import RegistrationContext

from reflex.app import EventNamespace
from reflex.event import Event, EventHandler
from reflex.state import StateUpdate


async def _noop_handler() -> None:
    """Complete without application work."""


async def _chain_handler() -> None:
    """Enqueue a child event from the active event context."""
    await EventContext.get().enqueue(Event.from_event_type(NOOP_EVENT())[0])


async def _slow_handler() -> None:
    """Remain pending until shutdown cancellation."""
    await asyncio.sleep(60)


async def _yield_handler() -> None:
    """Emit rapid intermediate deltas in order."""
    context = EventContext.get()
    await context.emit_delta({"state": {"value": 1}})
    await context.emit_delta({"state": {"value": 2}})


NOOP_EVENT = EventHandler(fn=_noop_handler)
CHAIN_EVENT = EventHandler(fn=_chain_handler)
SLOW_EVENT = EventHandler(fn=_slow_handler)
YIELD_EVENT = EventHandler(fn=_yield_handler)


def _register_handlers() -> RegistrationContext:
    """Create an attached registry containing benchmark handlers.

    Returns:
        Attached registration context.
    """
    context = RegistrationContext()
    context.__enter__()
    for handler in (NOOP_EVENT, CHAIN_EVENT, SLOW_EVENT, YIELD_EVENT):
        RegistrationContext.register_event_handler(handler)
    return context


async def _process(handler: EventHandler, token: str = "token") -> None:
    """Process one event through a configured processor.

    Args:
        handler: Registered handler.
        token: Client token.
    """
    processor = EventProcessor(graceful_shutdown_timeout=2)
    processor.configure()
    async with processor:
        future = await processor.enqueue(token, Event.from_event_type(handler())[0])
        await future.wait_all()


def test_event_queue_dispatch(benchmark: BenchmarkFixture):
    """Benchmark enqueue, dispatch, task completion, and clean shutdown.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()
    try:
        benchmark(lambda: loop.run_until_complete(_process(NOOP_EVENT)))
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_future_tree(benchmark: BenchmarkFixture):
    """Benchmark a parent event that enqueues and waits for one child.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()
    try:
        benchmark(lambda: loop.run_until_complete(_process(CHAIN_EVENT)))
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_shutdown_drain(benchmark: BenchmarkFixture):
    """Benchmark graceful draining of ten queued no-op events.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()

    async def drain() -> None:
        """Enqueue a burst and let processor shutdown drain it."""
        processor = EventProcessor(graceful_shutdown_timeout=2)
        processor.configure()
        async with processor:
            for _ in range(10):
                await processor.enqueue("token", Event.from_event_type(NOOP_EVENT())[0])

    try:
        benchmark(lambda: loop.run_until_complete(drain()))
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_shutdown_cancel(benchmark: BenchmarkFixture):
    """Benchmark forced cancellation during zero-grace shutdown.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()

    async def cancel() -> bool:
        """Start a slow task and stop without a drain period.

        Returns:
            Whether shutdown cancelled its future.
        """
        processor = EventProcessor(graceful_shutdown_timeout=0)
        processor.configure()
        async with processor:
            future = await processor.enqueue(
                "token", Event.from_event_type(SLOW_EVENT())[0]
            )
            await asyncio.sleep(0)
        return future.cancelled()

    try:
        assert benchmark(lambda: loop.run_until_complete(cancel()))
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_yield_intermediate_update(benchmark: BenchmarkFixture):
    """Benchmark ordered streaming of rapid intermediate deltas.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()

    async def collect() -> list[Mapping[str, Any]]:
        """Stream all deltas from the yielding event.

        Returns:
            Ordered emitted deltas.
        """
        processor = EventProcessor(graceful_shutdown_timeout=2)
        processor.configure()
        async with processor:
            return [
                delta
                async for delta in processor.enqueue_stream_delta(
                    "token", Event.from_event_type(YIELD_EVENT())[0]
                )
            ]

    try:
        deltas = benchmark(lambda: loop.run_until_complete(collect()))
        assert deltas == [
            {"state": {"value": 1}},
            {"state": {"value": 2}},
        ]
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_emit_update(benchmark: BenchmarkFixture):
    """Benchmark the real emit-update await and socket-flush scheduling path.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    emitted: list[StateUpdate] = []

    async def emit(  # noqa: RUF029
        _event: str, update: StateUpdate, *, to: str
    ) -> None:
        """Record a stand-in Socket.IO write.

        Args:
            _event: Socket event name.
            update: State update.
            to: Socket ID.
        """
        assert to == "sid"
        emitted.append(update)

    token_manager = SimpleNamespace(
        instance_id="instance",
        token_to_socket={"token": SimpleNamespace(instance_id="instance", sid="sid")},
    )
    namespace = cast(
        EventNamespace,
        SimpleNamespace(_token_manager=token_manager, emit=emit),
    )
    update = StateUpdate(delta={"state": {"value": 1}})

    try:
        benchmark(
            lambda: loop.run_until_complete(
                EventNamespace.emit_update(namespace, update, "token")
            )
        )
        assert emitted
    finally:
        loop.close()
