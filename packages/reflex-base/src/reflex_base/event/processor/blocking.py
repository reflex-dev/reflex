"""Development-time detection of event handlers blocking the asyncio loop."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import sysconfig
import threading
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex_base.registry import RegisteredEventHandler

logger = logging.getLogger(__name__)

# Name prefix of the asyncio task that processes one event.
EVENT_TASK_PREFIX = "reflex_event|"

# The standard library and installed packages hold no app code.
_LIBRARY_PATHS = tuple({
    f"{Path(sysconfig.get_path(name))}{os.sep}"
    for name in ("stdlib", "platstdlib", "purelib", "platlib")
})


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
        # The monitor is created on the loop thread, in the app root.
        self._loop_thread_id = threading.get_ident()
        self._app_root = f"{Path.cwd()}{os.sep}"
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

    def _describe_blocking(self) -> tuple[str, str, str] | None:
        """Describe the event task that runs on the blocked loop.

        Returns:
            The handler name, the location of the innermost app frame (or an
            empty string), and the formatted stack of the event task, or None
            if the running task processes no event or has left the loop.
        """
        task = asyncio.current_task(self.loop)
        if task is None or not (name := task.get_name()).startswith(EVENT_TASK_PREFIX):
            return None
        event_name = name[len(EVENT_TASK_PREFIX) :].partition("|")[0]
        registered = self.event_handlers.get(event_name)
        if (stack := self._task_stack(task)) is None:
            return None
        handler_name = (
            event_name if registered is None else registered.handler.fn.__qualname__
        )
        app_frame = self._app_frame(stack)
        location = (
            ""
            if app_frame is None
            else f" at {app_frame.filename[len(self._app_root) :]}:"
            f"{app_frame.lineno} in {app_frame.name}"
        )
        return handler_name, location, "".join(traceback.format_list(stack))

    def _app_frame(
        self, stack: traceback.StackSummary
    ) -> traceback.FrameSummary | None:
        """Find the innermost frame of app code, outside the stdlib and packages.

        Args:
            stack: The frames, outermost first.

        Returns:
            The innermost app frame, or None if no frame is app code.
        """
        for frame in reversed(stack):
            if frame.filename.startswith(
                self._app_root
            ) and not frame.filename.startswith(_LIBRARY_PATHS):
                return frame
        return None

    def _task_stack(self, task: asyncio.Task) -> traceback.StackSummary | None:
        """Extract the loop thread's frames from the task entry to the blocking line.

        Args:
            task: The task that runs on the blocked loop.

        Returns:
            The frames, outermost first, or None if the loop thread no longer
            runs the task.
        """
        entry = getattr(task.get_coro(), "cr_frame", None)
        frame = sys._current_frames().get(self._loop_thread_id)
        frames = []
        while frame is not None:
            frames.append(frame)
            if frame is entry:
                return traceback.StackSummary.extract(
                    (frame, frame.f_lineno) for frame in reversed(frames)
                )
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

            # The task is only visible while the loop is blocked, so report it
            # then, and report the total duration once the loop responds.
            handler_name = None
            while not responsive.wait(interval):
                if self._stop.is_set():
                    return
                elapsed = time.perf_counter() - started
                if (
                    handler_name is None
                    and elapsed + interval >= self.threshold
                    and (blocking := self._describe_blocking()) is not None
                ):
                    handler_name, location, stack = blocking
                    logger.warning(
                        "Event handler %s is blocking the event loop%s (threshold: "
                        "%.3fs), including state updates such as computed vars. "
                        "Move blocking I/O to a thread pool or use a non-blocking "
                        "async API.\n"
                        "Blocking stack (most recent call last):\n%s",
                        handler_name,
                        location,
                        self.threshold,
                        stack.rstrip(),
                    )
            if handler_name is not None:
                logger.warning(
                    "Event handler %s blocked the event loop for %.3fs in total.",
                    handler_name,
                    time.perf_counter() - started,
                )
