"""Development-time detection of event handlers blocking the asyncio loop."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import types

logger = logging.getLogger(__name__)


class EventLoopBlockingMonitor:
    """Report event handlers that keep the event loop from responding."""

    def __init__(self, loop: asyncio.AbstractEventLoop, threshold: float) -> None:
        """Create a monitor for an event loop.

        Args:
            loop: The event loop to monitor.
            threshold: Blocking duration in seconds at which to warn.
        """
        self.loop = loop
        self.threshold = threshold
        self._loop_thread_id = threading.get_ident()
        self._stop = threading.Event()
        self._handlers_lock = threading.Lock()
        self._handlers: dict[types.CodeType, tuple[str, int]] = {}
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the single monitor thread for this event processor."""
        self._thread = threading.Thread(
            target=self._run,
            name="reflex-event-loop-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor thread."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None

    def handler_started(self, handler: object) -> None:
        """Record a handler while its event task is executing.

        Args:
            handler: The registered handler function.
        """
        code = getattr(handler, "__code__", None)
        name = getattr(handler, "__qualname__", None)
        if not isinstance(code, types.CodeType) or not isinstance(name, str):
            return
        with self._handlers_lock:
            current_name, count = self._handlers.get(code, (name, 0))
            self._handlers[code] = current_name, count + 1

    def handler_finished(self, handler: object) -> None:
        """Remove a handler after its event task finishes.

        Args:
            handler: The registered handler function.
        """
        code = getattr(handler, "__code__", None)
        if not isinstance(code, types.CodeType):
            return
        with self._handlers_lock:
            if (current := self._handlers.get(code)) is None:
                return
            name, count = current
            if count == 1:
                del self._handlers[code]
            else:
                self._handlers[code] = name, count - 1

    def _find_handler(self) -> str | None:
        """Find the innermost active handler frame on the event-loop thread."""
        frame = sys._current_frames().get(self._loop_thread_id)
        if frame is None:
            return None
        with self._handlers_lock:
            handlers = self._handlers.copy()
        while frame is not None:
            if handler := handlers.get(frame.f_code):
                return handler[0]
            frame = frame.f_back
        return None

    def _run(self) -> None:
        """Poll loop responsiveness from outside the event-loop thread."""
        # Poll at one tenth of the threshold, between one and 10 milliseconds.
        interval = min(max(self.threshold / 10, 0.001), 0.01)
        while not self._stop.wait(interval):
            responsive = threading.Event()
            started = time.perf_counter()
            try:
                self.loop.call_soon_threadsafe(responsive.set)
            except RuntimeError:
                return

            reported = False
            while not responsive.wait(interval):
                if self._stop.is_set():
                    return
                duration = time.perf_counter() - started
                if duration + interval >= self.threshold and not reported:
                    if handler_name := self._find_handler():
                        logger.warning(
                            "Event handler %s blocked the event loop "
                            "(observed delay: %.3fs; threshold: %.3fs). Move blocking "
                            "I/O to a thread pool or use a non-blocking async API.",
                            handler_name,
                            duration,
                            self.threshold,
                        )
                        reported = True
