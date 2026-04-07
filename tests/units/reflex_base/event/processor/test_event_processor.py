"""Tests for EventProcessor lifecycle, task management, and error handling."""

import asyncio
import contextlib
from typing import Any

import pytest
from reflex_base.event.context import EventContext
from reflex_base.event.processor.event_processor import EventProcessor, QueueShutDown
from reflex_base.registry import RegistrationContext

from reflex.event import Event, EventHandler

# Module-level log so event handlers can record what happened.
_CALL_LOG: list[dict[str, Any]] = []


async def _noop_handler():
    """A handler that does nothing."""


async def _slow_handler(delay: float = 0.5):
    """A handler that sleeps for *delay* seconds.

    Args:
        delay: How long to sleep in seconds.
    """
    await asyncio.sleep(delay)


async def _error_handler():  # noqa: RUF029
    """A handler that always raises."""
    raise RuntimeError("boom")  # noqa: EM101


async def _logging_handler(value: str = "default"):  # noqa: RUF029
    """A handler that records its invocation.

    Args:
        value: The value to log.
    """
    _CALL_LOG.append({"value": value})


async def _chaining_handler():
    """A handler that enqueues a logging event via the current EventContext."""
    ctx = EventContext.get()
    await ctx.enqueue(
        Event.from_event_type(logging_event("chained"))[0],
    )


async def _delta_handler():
    """A handler that emits a single delta."""
    ctx = EventContext.get()
    await ctx.emit_delta({"state": {"x": 1}})


async def _multi_delta_handler():
    """A handler that emits multiple deltas with a small pause between them."""
    ctx = EventContext.get()
    for i in range(3):
        await ctx.emit_delta({"state": {"i": i}})
        await asyncio.sleep(0.01)


async def _slow_logging_handler(value: str = "default"):
    """A slow logging handler that pauses before recording.

    Args:
        value: The value to log.
    """
    await asyncio.sleep(0.05)
    _CALL_LOG.append({"value": value})


async def _multi_chaining_handler():
    """A handler that enqueues three slow logging events in sequence."""
    ctx = EventContext.get()
    for label in ("first", "second", "third"):
        await ctx.enqueue(
            Event.from_event_type(slow_logging_event(label))[0],
        )


async def _background_then_normal_handler():
    """A handler that enqueues a background event followed by a normal slow event."""
    ctx = EventContext.get()
    await ctx.enqueue(Event.from_event_type(background_slow_logging_event("bg"))[0])
    await ctx.enqueue(Event.from_event_type(slow_logging_event("normal"))[0])


async def _error_then_logging_handler():
    """A handler that enqueues an error event followed by a logging event."""
    ctx = EventContext.get()
    await ctx.enqueue(Event.from_event_type(error_event())[0])
    await ctx.enqueue(Event.from_event_type(logging_event("after_chain_error"))[0])


async def _background_slow_logging_handler(value: str = "default"):
    """A background version of the slow logging handler.

    Args:
        value: The value to log.
    """
    await asyncio.sleep(0.05)
    _CALL_LOG.append({"value": value})


_background_slow_logging_handler._reflex_background_task = True  # type: ignore[attr-defined]


noop_event = EventHandler(fn=_noop_handler)
slow_event = EventHandler(fn=_slow_handler)
error_event = EventHandler(fn=_error_handler)
logging_event = EventHandler(fn=_logging_handler)
chaining_event = EventHandler(fn=_chaining_handler)
delta_event = EventHandler(fn=_delta_handler)
multi_delta_event = EventHandler(fn=_multi_delta_handler)
slow_logging_event = EventHandler(fn=_slow_logging_handler)
multi_chaining_event = EventHandler(fn=_multi_chaining_handler)
background_slow_logging_event = EventHandler(fn=_background_slow_logging_handler)
background_then_normal_event = EventHandler(fn=_background_then_normal_handler)
error_then_logging_event = EventHandler(fn=_error_then_logging_handler)


@pytest.fixture(autouse=True)
def _register_handlers(forked_registration_context: RegistrationContext):
    """Register all test event handlers and clear the call log.

    Args:
        forked_registration_context: Isolated registration context for the test.
    """
    _CALL_LOG.clear()
    for handler in (
        noop_event,
        slow_event,
        error_event,
        logging_event,
        chaining_event,
        delta_event,
        multi_delta_event,
        slow_logging_event,
        multi_chaining_event,
        background_slow_logging_event,
        background_then_normal_event,
        error_then_logging_event,
    ):
        RegistrationContext.register_event_handler(handler)


@pytest.fixture
def processor() -> EventProcessor:
    """A bare EventProcessor with no backend_exception_handler.

    Returns:
        A fresh EventProcessor instance.
    """
    return EventProcessor(graceful_shutdown_timeout=2)


def test_configure_once(processor: EventProcessor):
    """Calling configure() twice raises RuntimeError.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    with pytest.raises(RuntimeError, match="already configured"):
        processor.configure()


async def test_start_before_configure(processor: EventProcessor):
    """Starting before configure raises RuntimeError.

    Args:
        processor: The event processor fixture.
    """
    with pytest.raises(RuntimeError, match="not configured"):
        await processor.start()


async def test_start_twice(processor: EventProcessor):
    """Starting a second time raises RuntimeError.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    await processor.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            await processor.start()
    finally:
        await processor.stop()


async def test_stop_idempotent(processor: EventProcessor):
    """Stopping an already-stopped processor does not error.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    await processor.start()
    await processor.stop()
    await processor.stop()


async def test_async_context_manager(processor: EventProcessor):
    """Entering/exiting via ``async with`` starts and stops the processor.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    async with processor as ep:
        assert ep._queue is not None
    assert ep._queue is None
    assert ep._queue_task is None


async def test_enqueue_after_stop_raises(processor: EventProcessor):
    """Enqueueing after stop raises because the queue is gone.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    async with processor:
        pass
    with pytest.raises(QueueShutDown, match="not running"):
        await processor.enqueue("tok", Event.from_event_type(noop_event())[0])


async def test_enqueue_before_start_raises(processor: EventProcessor):
    """Enqueueing before start raises because the queue doesn't exist.

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    with pytest.raises(QueueShutDown, match="not running"):
        await processor.enqueue("tok", Event.from_event_type(noop_event())[0])


async def test_events_are_processed(
    mock_event_processor: EventProcessor,
    emitted_deltas: list,
    token: str,
):
    """Events enqueued are actually processed.

    Args:
        mock_event_processor: The event processor with mock root context.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """
    async with mock_event_processor as ep:
        await ep.enqueue(token, Event.from_event_type(logging_event("hello"))[0])
    assert _CALL_LOG == [{"value": "hello"}]


async def test_enqueue_returns_future(
    mock_event_processor: EventProcessor,
    token: str,
):
    """enqueue() returns a Future that resolves when the task finishes.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        future = await ep.enqueue(token, Event.from_event_type(noop_event())[0])
        assert isinstance(future, asyncio.Future)
    assert future.done()


async def test_tasks_cleared_after_stop(
    mock_event_processor: EventProcessor,
    token: str,
):
    """After stop(), the internal _tasks dict is empty.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        await ep.enqueue(token, Event.from_event_type(noop_event())[0])
    assert ep._tasks == {}


async def test_futures_cleared_after_stop(
    mock_event_processor: EventProcessor,
    token: str,
):
    """After stop(), the internal _futures dict is empty.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        await ep.enqueue(token, Event.from_event_type(noop_event())[0])
    assert ep._futures == {}


async def test_slow_tasks_cancelled_on_stop(processor: EventProcessor):
    """Tasks that haven't finished by the graceful timeout are cancelled.

    Args:
        processor: The event processor fixture.
    """
    processor.graceful_shutdown_timeout = 0
    processor.configure()
    async with processor as ep:
        future = await ep.enqueue("tok", Event.from_event_type(slow_event(10.0))[0])
    assert future.cancelled()
    assert ep._tasks == {}


async def test_multiple_futures_cancelled_on_stop(processor: EventProcessor):
    """Unresolved futures are cancelled during stop.

    Args:
        processor: The event processor fixture.
    """
    processor.graceful_shutdown_timeout = 0
    processor.configure()
    async with processor as ep:
        f1 = await ep.enqueue("t1", Event.from_event_type(slow_event(10.0))[0])
        f2 = await ep.enqueue("t2", Event.from_event_type(slow_event(10.0))[0])
    for f in (f1, f2):
        assert f.done()
    assert ep._futures == {}


async def test_cancel_future_before_task_starts(
    mock_event_processor: EventProcessor,
    token: str,
):
    """Cancelling the future before the task starts skips processing.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        future = await ep.enqueue(token, Event.from_event_type(slow_event(10.0))[0])
        future.cancel()
        await asyncio.sleep(0.05)
    assert ep._tasks == {}


async def test_cancel_future_cancels_running_task(
    mock_event_processor: EventProcessor,
    token: str,
):
    """Cancelling the future cancels an already-running task.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        future = await ep.enqueue(token, Event.from_event_type(slow_event(10.0))[0])
        await asyncio.sleep(0.05)
        future.cancel()
        await asyncio.sleep(0.05)
    assert ep._tasks == {}


async def test_exception_propagated_to_future(
    processor: EventProcessor,
    token: str,
):
    """An exception in the handler is set on the future.

    Args:
        processor: The event processor fixture.
        token: The client token.
    """
    processor.configure()
    async with processor as ep:
        future = await ep.enqueue(token, Event.from_event_type(error_event())[0])
    assert future.done()
    with pytest.raises(RuntimeError, match="boom"):
        future.result()


async def test_backend_exception_handler_called(token: str):
    """The backend_exception_handler receives the exception.

    Args:
        token: The client token.
    """
    caught: list[Exception] = []

    def _catch(ex: Exception) -> None:
        caught.append(ex)

    ep = EventProcessor(backend_exception_handler=_catch, graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        await ep.enqueue(token, Event.from_event_type(error_event())[0])
    assert len(caught) == 1
    assert isinstance(caught[0], RuntimeError)


async def test_error_does_not_stop_queue(
    processor: EventProcessor,
    token: str,
):
    """A failing event does not prevent subsequent events from processing.

    Args:
        processor: The event processor fixture.
        token: The client token.
    """
    processor.configure()
    async with processor as ep:
        await ep.enqueue(token, Event.from_event_type(error_event())[0])
        await ep.enqueue(token, Event.from_event_type(logging_event("after_error"))[0])
    assert _CALL_LOG == [{"value": "after_error"}]


async def test_chained_event_processed(token: str):
    """An event handler that enqueues another event via ctx.enqueue succeeds.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        await ep.enqueue(token, Event.from_event_type(chaining_event())[0])
    assert _CALL_LOG == [{"value": "chained"}]


async def test_join_when_not_started(processor: EventProcessor):
    """join() when not started is a no-op (queue is None).

    Args:
        processor: The event processor fixture.
    """
    processor.configure()
    await processor.join(timeout=1)


async def test_join_completes_after_processing(
    mock_event_processor: EventProcessor,
    token: str,
):
    """join() returns once all queued entries have been dequeued.

    Args:
        mock_event_processor: The event processor with mock root context.
        token: The client token.
    """
    async with mock_event_processor as ep:
        await ep.enqueue(token, Event.from_event_type(noop_event())[0])
        await ep.join(timeout=5)


async def test_stream_delta_yields_single_delta(token: str):
    """enqueue_stream_delta yields a delta emitted by the handler.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        event = Event.from_event_type(delta_event())[0]
        collected = [d async for d in ep.enqueue_stream_delta(token, event)]
    assert collected == [{"state": {"x": 1}}]


async def test_stream_delta_yields_multiple_deltas(token: str):
    """enqueue_stream_delta yields all deltas in order.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        event = Event.from_event_type(multi_delta_event())[0]
        collected = [d async for d in ep.enqueue_stream_delta(token, event)]
    assert collected == [
        {"state": {"i": 0}},
        {"state": {"i": 1}},
        {"state": {"i": 2}},
    ]


async def test_stream_delta_noop_handler_yields_nothing(token: str):
    """enqueue_stream_delta with a handler that emits no deltas yields nothing.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        event = Event.from_event_type(noop_event())[0]
        collected = [d async for d in ep.enqueue_stream_delta(token, event)]
    assert collected == []


async def test_stream_delta_not_configured_raises():
    """enqueue_stream_delta raises RuntimeError if processor is not configured."""
    ep = EventProcessor()
    with pytest.raises(RuntimeError, match="not configured"):
        async for _ in ep.enqueue_stream_delta("tok", Event(name="x", payload={})):
            pass


async def test_sequential_chained_events_run_in_order(token: str):
    """Chained events enqueued by a handler run in the order they were enqueued.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        future = await ep.enqueue(
            token, Event.from_event_type(multi_chaining_event())[0]
        )
        await future.wait_all()
    assert [entry["value"] for entry in _CALL_LOG] == ["first", "second", "third"]


async def test_futures_cleaned_up_after_chained_events(token: str):
    """All futures are removed from _futures after chained events complete.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        future = await ep.enqueue(
            token, Event.from_event_type(multi_chaining_event())[0]
        )
        await future.wait_all()
    assert ep._futures == {}


async def test_background_event_does_not_block_sequential_sibling(token: str):
    """A background event enqueued before a sequential sibling does not delay it.

    The background event (sequential=False) should execute concurrently while
    the normal sibling is free to start without waiting for the background
    event to finish first.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        future = await ep.enqueue(
            token, Event.from_event_type(background_then_normal_event())[0]
        )
        await future.wait_all()
    # Both events should have been processed regardless of order.
    values = {entry["value"] for entry in _CALL_LOG}
    assert values == {"bg", "normal"}


async def test_sequential_chain_continues_after_error(token: str):
    """A sequential chained event still runs when the preceding sibling raised an exception.

    The error in the first chained event must not block the second chained
    event from executing.

    Args:
        token: The client token.
    """
    ep = EventProcessor(graceful_shutdown_timeout=2)
    ep.configure()
    async with ep:
        future = await ep.enqueue(
            token, Event.from_event_type(error_then_logging_event())[0]
        )
        with contextlib.suppress(Exception):
            await future.wait_all()
    assert _CALL_LOG == [{"value": "after_chain_error"}]
