"""Tests for development-time event-loop blocking detection."""

from collections.abc import Callable
import asyncio
import logging
import threading
import time
from typing import Any

import pytest

from reflex_base.event.processor.blocking import EventLoopBlockingMonitor


async def test_sync_handler_blocking_is_reported(caplog: pytest.LogCaptureFixture):
    """Report the qualified name and duration of a blocking sync handler."""

    def blocking_handler():
        time.sleep(0.12)

    monitor = EventLoopBlockingMonitor(asyncio.get_running_loop(), threshold=0.04)
    caplog.set_level(logging.WARNING, logger="reflex_base.event.processor.blocking")
    monitor.handler_started(blocking_handler)
    monitor.start()
    try:
        # Let the monitor queue a responsiveness probe before blocking the loop.
        await asyncio.sleep(0.02)
        blocking_handler()
        await asyncio.sleep(0)
    finally:
        monitor.handler_finished(blocking_handler)
        monitor.stop()

    assert "blocking_handler" in caplog.text
    assert "blocked the event loop" in caplog.text
    assert "thread pool or use a non-blocking async API" in caplog.text


async def test_handler_blocking_just_over_threshold_is_detected(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """Account for the time between responsiveness probes."""
    loop = asyncio.get_running_loop()
    probe_queued = threading.Event()
    call_soon_threadsafe = loop.call_soon_threadsafe

    def track_probe(
        callback: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> asyncio.Handle:
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        probe_queued.set()
        return handle

    monkeypatch.setattr(loop, "call_soon_threadsafe", track_probe)

    def blocking_handler():
        assert probe_queued.wait(timeout=1)
        time.sleep(0.055)

    monitor = EventLoopBlockingMonitor(loop, threshold=0.04)
    caplog.set_level(logging.WARNING, logger="reflex_base.event.processor.blocking")
    monitor.handler_started(blocking_handler)
    monitor.start()
    try:
        blocking_handler()
        await asyncio.sleep(0)
    finally:
        monitor.handler_finished(blocking_handler)
        monitor.stop()

    assert "blocking_handler" in caplog.text


async def test_async_handler_blocking_is_reported(caplog: pytest.LogCaptureFixture):
    """Report synchronous blocking code inside an async handler."""

    async def blocking_handler():
        time.sleep(0.12)

    monitor = EventLoopBlockingMonitor(asyncio.get_running_loop(), threshold=0.04)
    caplog.set_level(logging.WARNING, logger="reflex_base.event.processor.blocking")
    monitor.handler_started(blocking_handler)
    monitor.start()
    try:
        # Let the monitor queue a responsiveness probe before blocking the loop.
        await asyncio.sleep(0.02)
        await blocking_handler()
        await asyncio.sleep(0)
    finally:
        monitor.handler_finished(blocking_handler)
        monitor.stop()

    assert "blocking_handler" in caplog.text


async def test_async_handler_await_does_not_report_as_blocking(
    caplog: pytest.LogCaptureFixture,
):
    """Do not report handlers that yield control while doing async work."""

    async def yielding_handler():
        await asyncio.sleep(0.1)

    monitor = EventLoopBlockingMonitor(asyncio.get_running_loop(), threshold=0.04)
    caplog.set_level(logging.WARNING, logger="reflex_base.event.processor.blocking")
    monitor.handler_started(yielding_handler)
    monitor.start()
    try:
        await yielding_handler()
    finally:
        monitor.handler_finished(yielding_handler)
        monitor.stop()

    assert "blocked the event loop" not in caplog.text
