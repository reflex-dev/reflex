"""Development-time detection of tasks blocking the asyncio loop."""

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
from weakref import WeakSet

if TYPE_CHECKING:
    from collections.abc import Callable

    from reflex_base.registry import RegisteredEventHandler

logger = logging.getLogger(__name__)

# Name prefix of the asyncio task that processes one event.
EVENT_TASK_PREFIX = "reflex_event|"

# The standard library and installed packages hold no app code.
_LIBRARY_PATHS = tuple({
    f"{Path(sysconfig.get_path(name))}{os.sep}"
    for name in ("stdlib", "platstdlib", "purelib", "platlib")
})

_APP_ADVICE = "Move blocking I/O to a thread pool or use a non-blocking async API."
_PACKAGE_ADVICE = (
    "The handler is not part of this app, so it is reported once per process."
)

# Share reports across monitors without keeping unloaded handlers alive.
_reported_package_handlers: WeakSet[Callable] = WeakSet()


class EventLoopBlockingMonitor:
    """Report tasks, such as event handlers, that keep the event loop from responding."""

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

    def _describe_blocking(self) -> tuple[str, str, str, str, str] | None:
        """Describe the task that runs on the blocked loop.

        An event handler from an installed package, with no app code in its
        blocking stack, is described once per process: the app cannot fix it.

        Returns:
            The subject (event handler or task name), the scope note for event
            handlers (or an empty string), the location of the innermost app
            frame (or an empty string), the advice, and the formatted stack of
            the task, or None if no task runs, the task has left the loop, or
            the handler was already reported.
        """
        task = asyncio.current_task(self.loop)
        if task is None:
            return None
        name = task.get_name()
        event_name, fn = "", None
        if name.startswith(EVENT_TASK_PREFIX):
            event_name = name[len(EVENT_TASK_PREFIX) :].partition("|")[0]
            registered = self.event_handlers.get(event_name)
            if registered is not None:
                fn = registered.handler.fn
            subject = f"Event handler {event_name if fn is None else fn.__qualname__}"
            scope = ", including state updates such as computed vars"
        else:
            subject, scope = f"Task {name!r}", ""
        if (stack := self._task_stack(task)) is None:
            return None
        frames: list[traceback.FrameSummary] = stack
        advice = _APP_ADVICE
        app_frame = self._app_frame(stack)
        if app_frame is not None:
            location = (
                f" at {app_frame.filename[len(self._app_root) :]}:"
                f"{app_frame.lineno} in {app_frame.name}"
            )
        else:
            location = ""
            if fn is not None and not self._is_app_file(
                handler_file := fn.__code__.co_filename
            ):
                if fn in _reported_package_handlers:
                    return None
                _reported_package_handlers.add(fn)
                subject += f" (from package {fn.__module__.partition('.')[0]})"
                advice = _PACKAGE_ADVICE
                # Start at the handler, skipping the frames that dispatch it.
                for index, frame in enumerate(stack):
                    if frame.filename == handler_file:
                        frames = stack[index:]
                        break
        return subject, scope, location, advice, "".join(traceback.format_list(frames))

    def _is_app_file(self, filename: str) -> bool:
        """Check whether a file is app code, outside the stdlib and packages.

        Args:
            filename: The path of the file.

        Returns:
            Whether the file is app code.
        """
        return filename.startswith(self._app_root) and not filename.startswith(
            _LIBRARY_PATHS
        )

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
            if self._is_app_file(frame.filename):
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
            subject = None
            while not responsive.wait(interval):
                if self._stop.is_set():
                    break
                elapsed = time.perf_counter() - started
                if (
                    subject is None
                    and elapsed + interval >= self.threshold
                    and (blocking := self._describe_blocking()) is not None
                ):
                    subject, scope, location, advice, stack = blocking
                    logger.warning(
                        "%s is blocking the event loop%s (threshold: %.3fs)%s. %s\n"
                        "Blocking stack (most recent call last):\n%s",
                        subject,
                        location,
                        self.threshold,
                        scope,
                        advice,
                        stack.rstrip(),
                    )
            # A stop that lands as the loop responds still gets the total; one
            # that lands while the loop is blocked has no total to report.
            if subject is not None and responsive.is_set():
                logger.warning(
                    "%s blocked the event loop for %.3fs in total.",
                    subject,
                    time.perf_counter() - started,
                )
