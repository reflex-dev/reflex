"""Deterministic benchmarks for event-processor scheduling and lifecycle paths."""

import asyncio
import contextvars
from collections.abc import Coroutine, Mapping
from types import SimpleNamespace
from typing import Any, cast

from pytest_codspeed import BenchmarkFixture
from reflex_base.event.context import EventContext
from reflex_base.event.processor import EventFuture, EventProcessor
from reflex_base.registry import RegistrationContext

from reflex.app import EventNamespace
from reflex.event import Event, EventHandler
from reflex.state import StateUpdate

# Drain budget far above any instrumented runtime so measured shutdowns never
# flip from graceful drain to cancellation under benchmark slowdown.
_DRAIN_BUDGET_SECONDS = 60.0


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


def _make_processor() -> EventProcessor:
    """Construct and configure a processor outside any measured region.

    Returns:
        A configured event processor with a generous drain budget.
    """
    return EventProcessor(graceful_shutdown_timeout=_DRAIN_BUDGET_SECONDS).configure()


def _run_in_context(
    loop: asyncio.AbstractEventLoop,
    ctx: contextvars.Context,
    coro: Coroutine[Any, Any, Any],
) -> Any:
    """Run a coroutine on the loop inside a fixed contextvars context.

    Lets ``EventProcessor.start`` and ``stop`` run in separate
    ``run_until_complete`` calls while sharing the context that owns the
    attached ``EventContext`` token.

    Args:
        loop: The event loop to run on.
        ctx: The shared context for the wrapping task.
        coro: The coroutine to run.

    Returns:
        The coroutine's result.
    """
    return loop.run_until_complete(loop.create_task(coro, context=ctx))


def test_event_queue_dispatch(benchmark: BenchmarkFixture):
    """Benchmark enqueueing one no-op event and awaiting its completion.

    Processor construction, configuration, startup, and shutdown all happen
    in per-round setup and teardown, so only queueing and dispatch are
    measured.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()
    ctx = contextvars.copy_context()

    async def dispatch(processor: EventProcessor, event: Event) -> None:
        """Enqueue one no-op event and await its completion.

        Args:
            processor: The started processor.
            event: The pre-built event to enqueue.
        """
        future = await processor.enqueue("token", event)
        await future.wait_all()

    def setup():
        """Construct and start a processor for the next measured round.

        Returns:
            Pedantic (args, kwargs) holding the started processor and event.
        """
        processor = _make_processor()
        _run_in_context(loop, ctx, processor.start())
        # Build the event in setup so only queueing and dispatch are measured.
        event = Event.from_event_type(NOOP_EVENT())[0]
        return ((processor, event), {})

    def run(processor: EventProcessor, event: Event) -> None:
        """Dispatch one event through the started processor.

        Runs inside ``ctx`` where ``start`` attached the ``EventContext``, so
        enqueue takes the production ``EventContext.get().fork()`` path rather
        than the ``LookupError`` fallback a bare loop context would trigger.

        Args:
            processor: The started processor.
            event: The pre-built event to enqueue.
        """
        _run_in_context(loop, ctx, dispatch(processor, event))

    def teardown(processor: EventProcessor, event: Event) -> None:
        """Stop the measured round's processor.

        Args:
            processor: The started processor.
            event: The event dispatched this round (unused at teardown).
        """
        _run_in_context(loop, ctx, processor.stop())

    try:
        benchmark.pedantic(run, setup=setup, teardown=teardown)
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_future_tree(benchmark: BenchmarkFixture):
    """Benchmark a parent event that enqueues and waits for one child.

    Processor lifecycle happens in per-round setup and teardown, so only
    the parent dispatch, chained child enqueue, and future-tree completion
    are measured.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()
    ctx = contextvars.copy_context()

    async def dispatch(processor: EventProcessor, event: Event) -> None:
        """Enqueue one chaining event and await the whole future tree.

        Args:
            processor: The started processor.
            event: The pre-built parent event to enqueue.
        """
        future = await processor.enqueue("token", event)
        await future.wait_all()

    def setup():
        """Construct and start a processor for the next measured round.

        Returns:
            Pedantic (args, kwargs) holding the started processor and event.
        """
        processor = _make_processor()
        _run_in_context(loop, ctx, processor.start())
        # Build the event in setup so only dispatch and chaining are measured.
        event = Event.from_event_type(CHAIN_EVENT())[0]
        return ((processor, event), {})

    def run(processor: EventProcessor, event: Event) -> None:
        """Dispatch the parent event through the started processor.

        Runs inside ``ctx`` where ``start`` attached the ``EventContext``, so
        enqueue takes the production ``EventContext.get().fork()`` path rather
        than the ``LookupError`` fallback a bare loop context would trigger.

        Args:
            processor: The started processor.
            event: The pre-built parent event to enqueue.
        """
        _run_in_context(loop, ctx, dispatch(processor, event))

    def teardown(processor: EventProcessor, event: Event) -> None:
        """Stop the measured round's processor.

        Args:
            processor: The started processor.
            event: The event dispatched this round (unused at teardown).
        """
        _run_in_context(loop, ctx, processor.stop())

    try:
        benchmark.pedantic(run, setup=setup, teardown=teardown)
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_shutdown_drain(benchmark: BenchmarkFixture):
    """Benchmark graceful draining of ten queued no-op events.

    The measured region intentionally covers processor startup, the
    ten-event enqueue burst, and the graceful drain performed by shutdown;
    construction and configuration happen in per-round setup.  Events use
    independent tokens because same-token bursts serialize and are partially
    cancelled rather than drained at shutdown.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()
    drained: list[EventFuture] = []

    async def drain(processor: EventProcessor) -> list[EventFuture]:
        """Enqueue a burst and let processor shutdown drain it.

        Args:
            processor: The configured processor.

        Returns:
            The futures for the enqueued burst.
        """
        async with processor:
            return [
                await processor.enqueue(
                    f"token-{index}", Event.from_event_type(NOOP_EVENT())[0]
                )
                for index in range(10)
            ]

    def setup():
        """Construct a processor for the next measured round.

        Returns:
            Pedantic (args, kwargs) holding the configured processor.
        """
        return ((_make_processor(),), {})

    def run(processor: EventProcessor) -> None:
        """Run the burst-and-drain round, recording its futures.

        Args:
            processor: The configured processor.
        """
        drained[:] = loop.run_until_complete(drain(processor))

    try:
        benchmark.pedantic(run, setup=setup)
        assert len(drained) == 10
        assert all(future.done() and not future.cancelled() for future in drained), (
            "shutdown cancelled queued events instead of draining them"
        )
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_event_shutdown_cancel(benchmark: BenchmarkFixture):
    """Benchmark forced cancellation during zero-grace shutdown.

    The measured region intentionally covers startup, enqueueing one slow
    event, and the zero-budget shutdown that cancels it; construction and
    configuration happen in per-round setup.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()

    async def cancel(processor: EventProcessor) -> bool:
        """Start a slow task and stop without a drain period.

        Args:
            processor: The configured processor.

        Returns:
            Whether shutdown cancelled its future.
        """
        async with processor:
            future = await processor.enqueue(
                "token", Event.from_event_type(SLOW_EVENT())[0]
            )
            await asyncio.sleep(0)
        return future.cancelled()

    def setup():
        """Construct a zero-grace processor for the next measured round.

        Returns:
            Pedantic (args, kwargs) holding the configured processor.
        """
        return ((EventProcessor(graceful_shutdown_timeout=0).configure(),), {})

    def run(processor: EventProcessor) -> bool:
        """Run the cancel round.

        Args:
            processor: The configured processor.

        Returns:
            Whether shutdown cancelled the slow event's future.
        """
        return loop.run_until_complete(cancel(processor))

    try:
        assert benchmark.pedantic(run, setup=setup)
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_yield_intermediate_update(benchmark: BenchmarkFixture):
    """Benchmark ordered streaming of rapid intermediate deltas.

    The measured region intentionally covers startup, streaming both deltas,
    and clean shutdown; construction and configuration happen in per-round
    setup.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    loop = asyncio.new_event_loop()
    registry = _register_handlers()

    async def collect(processor: EventProcessor) -> list[Mapping[str, Any]]:
        """Stream all deltas from the yielding event.

        Args:
            processor: The configured processor.

        Returns:
            Ordered emitted deltas.
        """
        async with processor:
            return [
                delta
                async for delta in processor.enqueue_stream_delta(
                    "token", Event.from_event_type(YIELD_EVENT())[0]
                )
            ]

    def setup():
        """Construct a processor for the next measured round.

        Returns:
            Pedantic (args, kwargs) holding the configured processor.
        """
        return ((_make_processor(),), {})

    def run(processor: EventProcessor) -> list[Mapping[str, Any]]:
        """Run the streaming round.

        Args:
            processor: The configured processor.

        Returns:
            Ordered emitted deltas.
        """
        return loop.run_until_complete(collect(processor))

    try:
        deltas = benchmark.pedantic(run, setup=setup)
        assert deltas == [
            {"state": {"value": 1}},
            {"state": {"value": 2}},
        ]
    finally:
        registry.__exit__(None, None, None)
        loop.close()


def test_emit_update(benchmark: BenchmarkFixture):
    """Benchmark emit_update's socket lookup and task-based flush scheduling.

    The Socket.IO ``emit`` call itself is mocked to a recording no-op, so
    only token-to-socket routing and the emit task scheduling are measured,
    not any real socket write.

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
