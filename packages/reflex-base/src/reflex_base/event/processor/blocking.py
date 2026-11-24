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
from types import FrameType
from typing import TYPE_CHECKING, NamedTuple
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
_package_reports_lock = threading.Lock()

# Filename prefix of the import machinery's frames, which tracebacks leave out too.
_IMPORT_MACHINERY = "<frozen importlib._bootstrap"


def _import_site(frames: list[FrameType]) -> tuple[int, str] | None:
    """Find the import that runs in the frames and the module it imports.

    Args:
        frames: The frames, outermost first.

    Returns:
        The index of the outermost import machinery frame and the name of the
        module the import statement imports, or None if no import runs.
    """
    importing = next(
        (
            index
            for index, frame in enumerate(frames)
            if frame.f_code.co_filename.startswith(_IMPORT_MACHINERY)
        ),
        None,
    )
    if importing is None:
        return None
    for frame in frames[importing:]:
        # The outermost load is the import statement's module, even while a
        # parent package or a finder runs. A lazy module body has no load frame.
        if frame.f_code.co_name == "_find_and_load":
            return importing, frame.f_locals["name"]
        if frame.f_code.co_name == "<module>":
            return importing, frame.f_globals["__name__"]
    return None


class _BlockingReport(NamedTuple):
    """What blocks the loop, sampled when the threshold was reached."""

    # The event handler or task that blocks the loop.
    subject: str
    # The one-line warning, with the location and advice.
    summary: str
    # The task's frames, outermost first, without the import machinery.
    stack: traceback.StackSummary


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

    def _describe_blocking(self) -> _BlockingReport | None:
        """Describe the task that runs on the blocked loop.

        An event handler from an installed package, with no app code in its
        blocking stack, is described once per process: the app cannot fix it.

        Returns:
            The report of the blocking task, or None if no task runs, the task
            has left the loop, or the handler was already reported.
        """
        task = asyncio.current_task(self.loop)
        if task is None or (frames := self._task_frames(task)) is None:
            return None
        name = task.get_name()
        fn = None
        if name.startswith(EVENT_TASK_PREFIX):
            event_name = name[len(EVENT_TASK_PREFIX) :].partition("|")[0]
            registered = self.event_handlers.get(event_name)
            if registered is not None:
                fn = registered.handler.fn
            subject = f"Event handler {event_name if fn is None else fn.__qualname__}"
            scope = ", including state updates such as computed vars"
        else:
            subject, scope = f"Task {name!r}", ""
        app_frame = self._app_frame(frames)
        site = _import_site(frames)
        activity = "" if site is None else f" while importing {site[1]}"
        if (
            fn is not None
            and app_frame is None
            and not self._is_app_file(handler_file := fn.__code__.co_filename)
        ):
            with _package_reports_lock:
                if fn in _reported_package_handlers:
                    return None
                _reported_package_handlers.add(fn)
            subject += f" (from package {fn.__module__.partition('.')[0]})"
            advice = _PACKAGE_ADVICE
            # Start at the handler, skipping the frames that dispatch it.
            frames = frames[
                next(
                    (
                        index
                        for index, frame in enumerate(frames)
                        if frame.f_code.co_filename == handler_file
                    ),
                    0,
                ) :
            ]
        elif site is None:
            advice = _APP_ADVICE
        else:
            importing, module = site
            # Point at the app line that starts the import, not inside the module.
            app_frame = self._app_frame(frames[:importing])
            advice = (
                f"Import {module} at the top of a module so it loads with the app, "
                "or, in an async handler, load it in a thread first with `await "
                f"asyncio.to_thread(importlib.import_module, {module!r})`."
            )
        location = (
            ""
            if app_frame is None
            else f" at {app_frame.f_code.co_filename[len(self._app_root) :]}:"
            f"{app_frame.f_lineno} in {app_frame.f_code.co_name}"
        )
        return _BlockingReport(
            subject,
            f"{subject} is blocking the event loop{location}{activity} "
            f"(threshold: {self.threshold:.3f}s){scope}. {advice}",
            traceback.StackSummary.extract(
                (frame, frame.f_lineno)
                for frame in frames
                if not frame.f_code.co_filename.startswith(_IMPORT_MACHINERY)
            ),
        )

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

    def _app_frame(self, frames: list[FrameType]) -> FrameType | None:
        """Find the innermost frame of app code, outside the stdlib and packages.

        Args:
            frames: The frames, outermost first.

        Returns:
            The innermost app frame, or None if no frame is app code.
        """
        for frame in reversed(frames):
            if self._is_app_file(frame.f_code.co_filename):
                return frame
        return None

    def _task_frames(self, task: asyncio.Task) -> list[FrameType] | None:
        """Collect the loop thread's frames from the task entry to the blocking line.

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
                frames.reverse()
                return frames
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
                    and (report := self._describe_blocking()) is not None
                ):
                    subject = report.subject
                    logger.warning(
                        "%s\n"
                        "Stack when the threshold was reached (most recent call last):\n%s",
                        report.summary,
                        "".join(report.stack.format()).rstrip(),
                    )
            # A stop that lands as the loop responds still gets the total; one
            # that lands while the loop is blocked has no total to report.
            if subject is not None and responsive.is_set():
                logger.warning(
                    "%s blocked the event loop for %.3fs in total.",
                    subject,
                    time.perf_counter() - started,
                )
