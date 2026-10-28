"""Development-time detection of event handlers blocking the asyncio loop."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex_base.registry import RegisteredEventHandler

logger = logging.getLogger(__name__)

# Name prefix of the asyncio task that processes one event.
EVENT_TASK_PREFIX = "reflex_event|"


class EventLoopBlockingMonitor:
    """Report event handlers that keep the event loop from responding."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        threshold: float,
        event_handlers: Mapping[str, RegisteredEventHandler],
    ) -> None:
        """Create a monitor for an event loop.

        Args:
            loop: The event loop to monitor.
            threshold: Blocking duration in seconds at which to warn.
            event_handlers: The registered handlers, by event name.
        """
        self.loop = loop
        self.threshold = threshold
        self.event_handlers = event_handlers
        self._stop = threading.Event()
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

    def _blocking_handler(self) -> str | None:
        """Name the handler of the event task that runs on the blocked loop.

        Returns:
            The handler name, or None if the running task processes no event.
        """
        task = asyncio.current_task(self.loop)
        if task is None or not (name := task.get_name()).startswith(EVENT_TASK_PREFIX):
            return None
        event_name = name[len(EVENT_TASK_PREFIX) :].partition("|")[0]
        if (registered := self.event_handlers.get(event_name)) is None:
            return event_name
        return registered.handler.fn.__qualname__

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

            # The task is only visible while the loop is blocked, so name it
            # then and report the full duration once the loop responds.
            handler_name = None
            while not responsive.wait(interval):
                if self._stop.is_set():
                    return
                if (
                    handler_name is None
                    and time.perf_counter() - started + interval >= self.threshold
                ):
                    handler_name = self._blocking_handler()
            if handler_name is not None:
                logger.warning(
                    "Event handler %s blocked the event loop for %.3fs "
                    "(threshold: %.3fs), including state updates such as computed "
                    "vars. Move blocking I/O to a thread pool or use a "
                    "non-blocking async API.",
                    handler_name,
                    time.perf_counter() - started,
                    self.threshold,
                )
