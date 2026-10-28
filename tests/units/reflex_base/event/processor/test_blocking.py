"""Tests for development-time event-loop blocking detection."""

import asyncio
import logging
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

    assert "blocked the event loop" not in caplog_blocking.text


async def test_awaiting_event_is_not_reported(
    caplog_blocking: pytest.LogCaptureFixture,
):
    """Do not report handlers that yield control while doing async work."""

    async def yielding_handler():
        await asyncio.sleep(0.1)

    await _run_monitored(
        yielding_handler, f"{EVENT_TASK_PREFIX}state.yielding|token|txid"
    )

    assert "blocked the event loop" not in caplog_blocking.text
