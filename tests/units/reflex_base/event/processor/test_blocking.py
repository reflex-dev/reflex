"""Tests for development-time event-loop blocking detection."""

import asyncio
import logging
import sys
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from reflex_base.event.processor.blocking import (
    EVENT_TASK_PREFIX,
    EventLoopBlockingMonitor,
)
from reflex_base.registry import RegisteredEventHandler

from reflex.event import EventHandler


def _track_queued_probe(
    loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
) -> threading.Event:
    """Return an event set after the monitor queues a responsiveness probe."""
    probe_queued = threading.Event()
    call_soon_threadsafe = loop.call_soon_threadsafe

    def track_probe(
        callback: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> asyncio.Handle:
        """Queue the callback and record that a probe was queued.

        Args:
            callback: The callback to queue.
            *args: Positional arguments for the callback.
            **kwargs: Keyword arguments for call_soon_threadsafe.

        Returns:
            The handle of the queued callback.
        """
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        probe_queued.set()
        return handle

    monkeypatch.setattr(loop, "call_soon_threadsafe", track_probe)
    return probe_queued


async def _run_monitored(
    fn: Callable[[], Coroutine[Any, Any, None]],
    task_name: str,
    event_handlers: dict[str, RegisteredEventHandler] | None = None,
) -> None:
    """Run fn in a task with the given name while a monitor watches the loop."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.04, event_handlers=event_handlers or {}
    )
    monitor.start()
    try:
        await asyncio.create_task(fn(), name=task_name)
        await asyncio.sleep(0)
    finally:
        monitor.stop()


def _blocking(
    probe_queued: threading.Event, duration: float
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Create a coroutine function that blocks the loop after a probe is queued.

    Returns:
        The blocking coroutine function.
    """

    async def blocking_handler():  # noqa: RUF029
        """Block the loop for the duration after a probe is queued."""
        assert probe_queued.wait(timeout=1)
        time.sleep(duration)  # noqa: ASYNC251

    return blocking_handler


@pytest.fixture
def caplog_blocking(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture warnings of the blocking monitor.

    Returns:
        The log capture fixture.
    """
    caplog.set_level(logging.WARNING, logger="reflex_base.event.processor.blocking")
    return caplog


async def test_blocking_event_is_reported_with_handler_name(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Name the registered handler of the blocking event task."""
    probe_queued = _track_queued_probe(asyncio.get_running_loop(), monkeypatch)
    handler = _blocking(probe_queued, 0.12)
    registered = RegisteredEventHandler(handler=EventHandler(fn=handler), states=())

    await _run_monitored(
        handler,
        f"{EVENT_TASK_PREFIX}state.blocking|token|txid",
        {"state.blocking": registered},
    )

    assert "blocking_handler" in caplog_blocking.text
    assert "blocked the event loop for 0.1" in caplog_blocking.text
    assert "time.sleep(duration)  # noqa: ASYNC251" in caplog_blocking.text
    assert "_run_monitored" not in caplog_blocking.text
    assert "thread pool or use a non-blocking async API" in caplog_blocking.text


async def test_unregistered_event_is_reported_with_event_name(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Fall back to the event name when no handler is registered for it."""
    probe_queued = _track_queued_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(
        _blocking(probe_queued, 0.12), f"{EVENT_TASK_PREFIX}state.unknown|token|txid"
    )

    assert "Event handler state.unknown blocked" in caplog_blocking.text


async def test_blocking_just_over_threshold_is_detected(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Account for the time between responsiveness probes."""
    probe_queued = _track_queued_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(
        _blocking(probe_queued, 0.055), f"{EVENT_TASK_PREFIX}state.blocking|token|txid"
    )

    assert "state.blocking" in caplog_blocking.text


async def test_blocking_outside_event_task_is_not_reported(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Only report tasks that process an event."""
    probe_queued = _track_queued_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(_blocking(probe_queued, 0.12), "other_task")

    assert "the event loop" not in caplog_blocking.text


async def test_awaiting_event_is_not_reported(
    caplog_blocking: pytest.LogCaptureFixture,
):
    """Do not report handlers that yield control while doing async work."""

    async def yielding_handler():
        """Yield to the loop while waiting."""
        await asyncio.sleep(0.1)

    await _run_monitored(
        yielding_handler, f"{EVENT_TASK_PREFIX}state.yielding|token|txid"
    )

    assert "the event loop" not in caplog_blocking.text


async def test_hung_event_is_reported_while_still_blocked(
    caplog_blocking: pytest.LogCaptureFixture,
):
    """Warn when the threshold is reached, before the loop responds again."""
    warned = threading.Event()

    class _SetOnWarning(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            """Record that the monitor logged a warning.

            Args:
                record: The log record.
            """
            warned.set()

    handler = _SetOnWarning(level=logging.WARNING)
    blocking_logger = logging.getLogger("reflex_base.event.processor.blocking")
    blocking_logger.addHandler(handler)

    async def hung_handler():  # noqa: RUF029
        """Hold the loop until the monitor warns, like a handler that never returns."""
        assert warned.wait(timeout=1)

    try:
        await _run_monitored(hung_handler, f"{EVENT_TASK_PREFIX}state.hung|token|txid")
    finally:
        blocking_logger.removeHandler(handler)

    assert "state.hung is blocking the event loop" in caplog_blocking.text
    assert "warned.wait(timeout=1)" in caplog_blocking.text


async def test_stack_without_task_entry_is_not_reported(
    monkeypatch: pytest.MonkeyPatch,
):
    """Do not describe a frame snapshot taken after the task left the loop."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.04, event_handlers={}
    )
    unrelated = sys._getframe()
    monkeypatch.setattr(
        sys,
        "_current_frames",
        lambda: {monitor._loop_thread_id: unrelated},
    )

    async def handler():  # noqa: RUF029
        """Describe the blocking from inside the event task.

        Returns:
            The description of the blocking.
        """
        return monitor._describe_blocking()

    description = await asyncio.create_task(
        handler(), name=f"{EVENT_TASK_PREFIX}state.moved|token|txid"
    )

    assert description is None
