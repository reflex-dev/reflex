"""Tests for development-time event-loop blocking detection."""

import asyncio
import importlib
import logging
import os
import re
import sys
import threading
import time
import traceback
from collections.abc import Callable, Coroutine, Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from weakref import WeakSet

import pytest
from reflex_base.event.processor import blocking
from reflex_base.event.processor.blocking import (
    EVENT_TASK_PREFIX,
    EventLoopBlockingMonitor,
)
from reflex_base.registry import RegisteredEventHandler

from reflex.event import EventHandler

# Seconds the blocking handlers hold the loop, well past the monitor threshold.
_BLOCK_SECONDS = 0.12


def _blocked_total(text: str, subject: str) -> float:
    """Extract the total blocking duration the monitor reported for a subject.

    Args:
        text: The captured log text.
        subject: The subject of the report, such as ``Task 'name'``.

    Returns:
        The reported duration in seconds.
    """
    match = re.search(
        rf"{re.escape(subject)} blocked the event loop for (\d+\.\d+)s in total\.",
        text,
    )
    assert match is not None, text
    return float(match[1])


def _track_pending_probe(
    loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
) -> threading.Event:
    """Return an event set while a responsiveness probe waits for the loop to run it.

    A handler that waits for it before blocking holds the loop with a probe
    outstanding, so the probe times the whole block. A probe that already ran
    leaves it clear: the monitor queues the next one only a polling gap later,
    which may be well into the block on a loaded runner.
    """
    probe_pending = threading.Event()
    call_soon_threadsafe = loop.call_soon_threadsafe

    def track_probe(
        callback: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> asyncio.Handle:
        """Queue the callback and record that a probe waits for the loop.

        Args:
            callback: The callback to queue.
            *args: Positional arguments for the callback.
            **kwargs: Keyword arguments for call_soon_threadsafe.

        Returns:
            The handle of the queued callback.
        """

        def run_probe(*args: Any) -> None:
            """Record that the probe ran, then run it.

            Args:
                *args: Positional arguments for the callback.
            """
            probe_pending.clear()
            callback(*args)

        # Set before queuing, so a probe the loop runs at once cannot leave it set.
        probe_pending.set()
        return call_soon_threadsafe(run_probe, *args, **kwargs)

    monkeypatch.setattr(loop, "call_soon_threadsafe", track_probe)
    return probe_pending


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
    probe_pending: threading.Event, duration: float
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Create a coroutine function that blocks the loop while a probe is pending.

    Returns:
        The blocking coroutine function.
    """

    async def blocking_handler():  # noqa: RUF029
        """Block the loop for the duration once a probe waits for it."""
        assert probe_pending.wait(timeout=1)
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


@pytest.fixture
def warned() -> Generator[threading.Event, None, None]:
    """Yield an event that is set once the blocking monitor logs a warning."""
    event = threading.Event()

    class _SetOnWarning(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            """Record that the monitor logged a warning.

            Args:
                record: The log record.
            """
            event.set()

    handler = _SetOnWarning(level=logging.WARNING)
    blocking_logger = logging.getLogger("reflex_base.event.processor.blocking")
    blocking_logger.addHandler(handler)
    try:
        yield event
    finally:
        blocking_logger.removeHandler(handler)


async def test_blocking_event_is_reported_with_handler_name(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Name the registered handler of the blocking event task."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)
    handler = _blocking(probe_pending, _BLOCK_SECONDS)
    registered = RegisteredEventHandler(handler=EventHandler(fn=handler), states=())

    await _run_monitored(
        handler,
        f"{EVENT_TASK_PREFIX}state.blocking|token|txid",
        {"state.blocking": registered},
    )

    assert "blocking_handler" in caplog_blocking.text
    # The total covers the whole block, not just the time until it was detected.
    # A loaded runner only lengthens it, so there is no upper bound.
    assert (
        _blocked_total(
            caplog_blocking.text,
            "Event handler _blocking.<locals>.blocking_handler",
        )
        >= _BLOCK_SECONDS
    )
    assert "time.sleep(duration)  # noqa: ASYNC251" in caplog_blocking.text
    assert "_run_monitored" not in caplog_blocking.text
    assert "thread pool or use a non-blocking async API" in caplog_blocking.text


async def test_package_handler_is_reported_once_with_its_package(
    caplog_blocking: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Report a handler from outside the app once, by package, from its own frame."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)
    handler = _blocking(probe_pending, _BLOCK_SECONDS)
    registered = RegisteredEventHandler(handler=EventHandler(fn=handler), states=())
    # A frame from another file runs the handler, as the event processor does.
    namespace: dict[str, Any] = {}
    exec(
        compile(
            "async def dispatch(handler):\n    await handler()\n",
            "dispatcher.py",
            "exec",
        ),
        namespace,
    )
    for event_name in ("state.blocking", "state.alias"):
        monitor = EventLoopBlockingMonitor(
            asyncio.get_running_loop(),
            threshold=0.04,
            event_handlers={event_name: registered},
        )
        # The app lives elsewhere, so this module is not app code.
        monitor._app_root = f"{tmp_path}{os.sep}"
        monitor.start()
        try:
            await asyncio.create_task(
                namespace["dispatch"](handler),
                name=f"{EVENT_TASK_PREFIX}{event_name}|token|txid",
            )
            await asyncio.sleep(0)
        finally:
            monitor.stop()

    subject = (
        "Event handler _blocking.<locals>.blocking_handler "
        f"(from package {__name__.partition('.')[0]})"
    )
    messages = [
        re.sub(r"line \d+|for \d+\.\d+s", "N", record.getMessage())
        for record in caplog_blocking.records
    ]
    assert messages == [
        (
            f"{subject} is blocking the event loop (threshold: 0.040s), including "
            "state updates such as computed vars. The handler is not part of this "
            "app, so it is reported once per process.\n"
            "Stack when the threshold was reached (most recent call last):\n"
            f'  File "{__file__}", N, in blocking_handler\n'
            "    time.sleep(duration)  # noqa: ASYNC251"
        ),
        f"{subject} blocked the event loop N in total.",
    ]


def _fake_frame(filename: str, lineno: int, name: str, module: str = "fake") -> Any:
    """Build a stand-in for a live frame running a line of a function.

    Args:
        filename: The file of the function.
        lineno: The line the frame runs.
        name: The name of the function.
        module: The module the function belongs to, or the module that
            ``_find_and_load`` loads.

    Returns:
        An object with the frame attributes the monitor reads.
    """
    code = compile("", filename, "exec").replace(co_name=name)
    return SimpleNamespace(
        f_code=code,
        f_lineno=lineno,
        f_globals={"__name__": module},
        f_locals={"name": module},
    )


def _extract(frames: list[Any]) -> traceback.StackSummary:
    """Extract the stack summary the monitor builds from frames.

    Args:
        frames: The frames, outermost first.

    Returns:
        The stack summary.
    """
    return traceback.StackSummary.extract((frame, frame.f_lineno) for frame in frames)


async def test_reported_package_handler_still_reports_app_frames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Keep app warnings after reporting the same package handler once."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.04, event_handlers={}
    )
    monitor._app_root = f"{tmp_path}{os.sep}"
    package_frames = [_fake_frame("package/handler.py", 1, "handler")]
    app_frames = [_fake_frame(str(tmp_path / "app.py"), 2, "computed")]
    frames = iter((package_frames, app_frames, app_frames))
    monkeypatch.setattr(monitor, "_task_frames", lambda task: next(frames))

    async def handler():  # noqa: RUF029
        """Describe a package block followed by two app blocks.

        Returns:
            The descriptions of each blocking stack.
        """
        return [monitor._describe_blocking() for _ in range(3)]

    monitor.event_handlers = {
        "state.blocking": RegisteredEventHandler(
            handler=EventHandler(fn=handler), states=()
        )
    }
    descriptions = await asyncio.create_task(
        handler(), name=f"{EVENT_TASK_PREFIX}state.blocking|token|txid"
    )
    subject = f"Event handler {handler.__qualname__}"
    package_subject = f"{subject} (from package {__name__.partition('.')[0]})"
    app_report = blocking._BlockingReport(
        subject,
        f"{subject} is blocking the event loop at app.py:2 in computed (threshold: "
        "0.040s), including state updates such as computed vars. Move blocking I/O "
        "to a thread pool or use a non-blocking async API.",
        _extract(app_frames),
    )
    assert descriptions == [
        blocking._BlockingReport(
            package_subject,
            f"{package_subject} is blocking the event loop (threshold: 0.040s), "
            "including state updates such as computed vars. The handler is not part "
            "of this app, so it is reported once per process.",
            _extract(package_frames),
        ),
        app_report,
        app_report,
    ]


async def test_package_handler_import_keeps_package_advice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Name the import of a package handler, with the advice for package handlers."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.04, event_handlers={}
    )
    monitor._app_root = f"{tmp_path}{os.sep}"
    handler_frame = _fake_frame("package/handler.py", 3, "handler")
    module_frame = _fake_frame("package/sdk.py", 1, "<module>", module="package.sdk")
    frames = [
        handler_frame,
        _fake_frame(
            "<frozen importlib._bootstrap>",
            1371,
            "_find_and_load",
            module="package.sdk",
        ),
        module_frame,
    ]
    monkeypatch.setattr(monitor, "_task_frames", lambda task: frames)

    async def handler():  # noqa: RUF029
        """Describe the blocking from inside the event task.

        Returns:
            The description of the blocking.
        """
        return monitor._describe_blocking()

    monitor.event_handlers = {
        "state.importing": RegisteredEventHandler(
            handler=EventHandler(fn=handler), states=()
        )
    }
    report = await asyncio.create_task(
        handler(), name=f"{EVENT_TASK_PREFIX}state.importing|token|txid"
    )

    subject = (
        f"Event handler {handler.__qualname__} "
        f"(from package {__name__.partition('.')[0]})"
    )
    assert report == blocking._BlockingReport(
        subject,
        f"{subject} is blocking the event loop while importing package.sdk "
        "(threshold: 0.040s), including state updates such as computed vars. The "
        "handler is not part of this app, so it is reported once per process.",
        _extract([handler_frame, module_frame]),
    )


async def test_concurrent_monitors_report_package_handler_once(  # noqa: RUF029
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Claim a package report only once when two monitors observe it together."""

    class SlowMembership(WeakSet):
        def __contains__(self, item: object) -> bool:
            """Let another monitor run between checking and recording a handler.

            Args:
                item: The handler to check.

            Returns:
                Whether the handler was already reported.
            """
            present = super().__contains__(item)
            if not present:
                time.sleep(0.05)
            return present

    def handler():
        """Represent the shared installed handler."""

    registered = RegisteredEventHandler(handler=EventHandler(fn=handler), states=())
    monitors = [
        EventLoopBlockingMonitor(
            asyncio.get_running_loop(),
            threshold=0.04,
            event_handlers={"state.blocking": registered},
        )
        for _ in range(2)
    ]
    frames = [_fake_frame("package/handler.py", 1, "handler")]
    monkeypatch.setattr(blocking, "_reported_package_handlers", SlowMembership())
    monkeypatch.setattr(
        asyncio,
        "current_task",
        lambda loop: SimpleNamespace(
            get_name=lambda: f"{EVENT_TASK_PREFIX}state.blocking"
        ),
    )
    for monitor in monitors:
        monitor._app_root = f"{tmp_path}{os.sep}"
        monkeypatch.setattr(monitor, "_task_frames", lambda task: frames)
    ready = threading.Barrier(2)

    def describe(monitor: EventLoopBlockingMonitor):
        """Describe both monitors' observations at the same time.

        Args:
            monitor: The monitor observing the handler.

        Returns:
            The description, if this monitor claimed the report.
        """
        ready.wait(timeout=1)
        return monitor._describe_blocking()

    with ThreadPoolExecutor(max_workers=2) as pool:
        descriptions = list(pool.map(describe, monitors))
    assert descriptions.count(None) == 1
    subject = (
        f"Event handler {handler.__qualname__} "
        f"(from package {__name__.partition('.')[0]})"
    )
    assert [description for description in descriptions if description is not None] == [
        blocking._BlockingReport(
            subject,
            f"{subject} is blocking the event loop (threshold: 0.040s), including "
            "state updates such as computed vars. The handler is not part of this "
            "app, so it is reported once per process.",
            _extract(frames),
        )
    ]


async def test_unregistered_event_is_reported_with_event_name(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Fall back to the event name when no handler is registered for it."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(
        _blocking(probe_pending, _BLOCK_SECONDS),
        f"{EVENT_TASK_PREFIX}state.unknown|token|txid",
    )

    assert "Event handler state.unknown blocked" in caplog_blocking.text


async def test_blocking_just_over_threshold_is_detected(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Account for the time between responsiveness probes."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(
        _blocking(probe_pending, 0.055), f"{EVENT_TASK_PREFIX}state.blocking|token|txid"
    )

    assert "state.blocking" in caplog_blocking.text


async def test_blocking_outside_event_task_is_reported_with_task_name(
    caplog_blocking: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Report blocking in a task that processes no event by the task name."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)

    await _run_monitored(_blocking(probe_pending, _BLOCK_SECONDS), "other_task")

    assert "Task 'other_task' is blocking the event loop" in caplog_blocking.text
    assert _blocked_total(caplog_blocking.text, "Task 'other_task'") >= _BLOCK_SECONDS
    assert "time.sleep(duration)  # noqa: ASYNC251" in caplog_blocking.text
    assert "Event handler" not in caplog_blocking.text
    assert "computed vars" not in caplog_blocking.text


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
    caplog_blocking: pytest.LogCaptureFixture, warned: threading.Event
):
    """Warn when the threshold is reached, before the loop responds again."""

    async def hung_handler():  # noqa: RUF029
        """Hold the loop until the monitor warns, like a handler that never returns."""
        assert warned.wait(timeout=1)

    await _run_monitored(hung_handler, f"{EVENT_TASK_PREFIX}state.hung|token|txid")

    assert "state.hung is blocking the event loop" in caplog_blocking.text
    assert "warned.wait(timeout=1)" in caplog_blocking.text


async def test_stop_as_the_loop_responds_still_reports_the_total(
    caplog_blocking: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    warned: threading.Event,
):
    """Report the total when a stop lands as the loop responds.

    The loop responds and stops the monitor between a timed-out responsiveness
    wait and the monitor's check for a stop.
    """
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.04, event_handlers={}
    )
    overtaken = threading.Event()

    class _OvertakenEvent(threading.Event):
        """An event the loop sets, and then stops the monitor, as a wait on it times out."""

        def wait(self, timeout: float | None = None) -> bool:
            """Wait, letting the loop and a stop overtake the first timeout after the warning.

            Args:
                timeout: Seconds to wait for the event.

            Returns:
                Whether the event was set before the wait timed out.
            """
            if super().wait(timeout):
                return True
            if warned.is_set() and not overtaken.is_set():
                self.set()
                monitor._stop.set()
                overtaken.set()
            return False

    # Only the responsiveness probes are created after this point.
    monkeypatch.setattr(
        blocking,
        "threading",
        SimpleNamespace(Event=_OvertakenEvent, Thread=threading.Thread),
    )

    async def hung_handler():  # noqa: RUF029
        """Hold the loop until the monitor's wait has been overtaken."""
        assert warned.wait(timeout=1)
        assert overtaken.wait(timeout=1)

    monitor.start()
    try:
        await asyncio.create_task(
            hung_handler(), name=f"{EVENT_TASK_PREFIX}state.hung|token|txid"
        )
    finally:
        monitor.stop()

    assert "Event handler state.hung blocked the event loop for" in caplog_blocking.text


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


def _write_import_app(root: Path, importer: str, imported: str, body: str) -> None:
    """Write an app module whose load() first imports another app module.

    Args:
        root: The app root to write the modules in.
        importer: The name of the module that imports in load().
        imported: The name of the module load() imports.
        body: The top-level code of the imported module.
    """
    (root / f"{importer}.py").write_text(f"def load():\n    import {imported}\n")
    (root / f"{imported}.py").write_text(body)


@pytest.fixture
def app_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Make a fresh directory the app root and importable.

    Yields:
        The app root.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    modules = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - modules:
        del sys.modules[name]


async def test_import_is_reported_at_the_import_site(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
):
    """Name the imported module and the app line that imports it, without import machinery frames."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.2, event_handlers={}
    )
    reports = []
    monkeypatch.setitem(
        sys.modules,
        "blocking_probe",
        SimpleNamespace(describe=lambda: reports.append(monitor._describe_blocking())),
    )
    _write_import_app(
        app_root,
        "importer",
        "heavy_sdk",
        "import blocking_probe\nblocking_probe.describe()\n",
    )
    importer = importlib.import_module("importer")

    async def handler():  # noqa: RUF029
        """Import a module for the first time on the loop."""
        importer.load()

    await asyncio.create_task(
        handler(), name=f"{EVENT_TASK_PREFIX}state.importing|token|txid"
    )

    [report] = reports
    assert report is not None
    assert report.subject == "Event handler state.importing"
    assert report.summary == (
        "Event handler state.importing is blocking the event loop at importer.py:2 "
        "in load while importing heavy_sdk (threshold: 0.200s), including state "
        "updates such as computed vars. Import heavy_sdk at the top of a module so "
        "it loads with the app, or, in an async handler, load it in a thread first "
        "with `await asyncio.to_thread(importlib.import_module, 'heavy_sdk')`."
    )
    assert [(frame.filename, frame.name) for frame in report.stack] == [
        (__file__, "handler"),
        (str(app_root / "importer.py"), "load"),
        (str(app_root / "heavy_sdk.py"), "<module>"),
        (__file__, "<lambda>"),
        (blocking.__file__, "_describe_blocking"),
        (blocking.__file__, "_task_frames"),
    ]


class _ProbingFinder:
    """Find no module, after a probe while looking for one name."""

    def __init__(self, name: str, probe: Callable[[], None]) -> None:
        """Probe while looking for a module.

        Args:
            name: The module to probe for.
            probe: The function to call while looking for the module.
        """
        self.name = name
        self.probe = probe

    def find_spec(self, fullname: str, *args: Any) -> None:
        """Probe for the module name, then find nothing.

        Args:
            fullname: The name of the module to find.
            *args: The import path and target, unused.
        """
        if fullname == self.name:
            self.probe()


def _probe_in_parent_package(root: Path, probe: Callable[[], None]) -> None:
    """Write a package whose parent probes, so the leaf is not yet loading.

    Args:
        root: The app root to write the package in.
        probe: The function to call, unused: the package calls blocking_probe.
    """
    (root / "heavy_pkg" / "sub").mkdir(parents=True)
    (root / "heavy_pkg" / "__init__.py").write_text(
        "import blocking_probe\nblocking_probe.describe()\n"
    )
    (root / "heavy_pkg" / "sub" / "__init__.py").write_text("")
    (root / "heavy_pkg" / "sub" / "leaf.py").write_text("")


def _probe_in_finder(root: Path, probe: Callable[[], None]) -> None:
    """Probe while a finder looks for the module, before any module body runs.

    Args:
        root: The app root, unused.
        probe: The function to call while looking for the module.
    """
    sys.meta_path.insert(0, _ProbingFinder("virtual_sdk", probe))


@pytest.mark.parametrize(
    ("module", "setup"),
    [
        ("heavy_pkg.sub.leaf", _probe_in_parent_package),
        ("virtual_sdk", _probe_in_finder),
    ],
    ids=["parent_package", "finder"],
)
async def test_import_names_the_module_the_statement_imports(
    app_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    setup: Callable[[Path, Callable[[], None]], None],
):
    """Name the module the import statement imports, wherever the import blocks."""
    monitor = EventLoopBlockingMonitor(
        asyncio.get_running_loop(), threshold=0.2, event_handlers={}
    )
    reports = []

    def describe():
        """Describe the blocking import."""
        reports.append(monitor._describe_blocking())

    monkeypatch.setitem(
        sys.modules, "blocking_probe", SimpleNamespace(describe=describe)
    )
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    setup(app_root, describe)
    (app_root / "importer.py").write_text(
        f"def load():\n    try:\n        import {module}\n    except ImportError:\n"
        "        pass\n"
    )
    importer = importlib.import_module("importer")

    async def handler():  # noqa: RUF029
        """Import a module for the first time on the loop."""
        importer.load()

    await asyncio.create_task(
        handler(), name=f"{EVENT_TASK_PREFIX}state.importing|token|txid"
    )

    [report] = reports
    assert report is not None
    assert report.summary == (
        "Event handler state.importing is blocking the event loop at importer.py:3 "
        f"in load while importing {module} (threshold: 0.200s), including state "
        f"updates such as computed vars. Import {module} at the top of a module so "
        "it loads with the app, or, in an async handler, load it in a thread first "
        f"with `await asyncio.to_thread(importlib.import_module, {module!r})`."
    )


async def test_blocking_import_is_logged_with_import_advice(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
):
    """Log the import summary over the stack sampled at the threshold."""
    probe_pending = _track_pending_probe(asyncio.get_running_loop(), monkeypatch)
    in_body = threading.Event()
    monkeypatch.setitem(
        sys.modules,
        "blocking_probe",
        SimpleNamespace(pending=probe_pending, in_body=in_body),
    )
    _write_import_app(
        app_root,
        "importer",
        "slow_sdk",
        "import time\n"
        "import blocking_probe\n"
        "assert blocking_probe.pending.wait(timeout=1)\n"
        "blocking_probe.in_body.set()\n"
        f"time.sleep({_BLOCK_SECONDS})\n",
    )
    describe_blocking = EventLoopBlockingMonitor._describe_blocking

    def describe_in_body(monitor: EventLoopBlockingMonitor) -> Any:
        """Sample the blocked loop once the module body runs.

        Finding and compiling a new module can reach the threshold on its own on
        a slow file system, before the body this test samples.

        Args:
            monitor: The monitor sampling the loop.

        Returns:
            The report of the blocking task.
        """
        in_body.wait(timeout=1)
        return describe_blocking(monitor)

    monkeypatch.setattr(
        EventLoopBlockingMonitor, "_describe_blocking", describe_in_body
    )
    importer = importlib.import_module("importer")
    records = []

    class _Record(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            """Keep the record.

            Args:
                record: The log record.
            """
            records.append(record)

    handler = _Record(level=logging.WARNING)
    blocking_logger = logging.getLogger("reflex_base.event.processor.blocking")
    blocking_logger.addHandler(handler)

    async def load():  # noqa: RUF029
        """Import a slow module for the first time on the loop."""
        importer.load()

    try:
        await _run_monitored(load, "loader")
    finally:
        blocking_logger.removeHandler(handler)

    report, total = (record.getMessage() for record in records)
    summary, stack_title, *stack = report.split("\n")
    assert summary == (
        "Task 'loader' is blocking the event loop at importer.py:2 in load while "
        "importing slow_sdk (threshold: 0.040s). Import slow_sdk at the top of a "
        "module so it loads with the app, or, in an async handler, load it in a "
        "thread first with `await asyncio.to_thread(importlib.import_module, "
        "'slow_sdk')`."
    )
    assert stack_title == (
        "Stack when the threshold was reached (most recent call last):"
    )
    assert stack[-2:] == [
        f'  File "{app_root / "slow_sdk.py"}", line 5, in <module>',
        f"    time.sleep({_BLOCK_SECONDS})",
    ]
    assert [line for line in stack if "<frozen" in line] == []
    assert re.fullmatch(
        r"Task 'loader' blocked the event loop for \d+\.\d{3}s in total\.", total
    )
