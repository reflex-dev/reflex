"""Output supervisor for ``reflex run --json``.

:func:`supervise_output` re-runs the command with its stdout and stderr on
pipes and turns every line into a JSON record, so a consumer sees one JSON
object per line even for output that never went through ``logging``. It also
owns the command's shutdown: signals are passed on, the command tree is
killed after a deadline, and the drain never leaves a cut record on a pipe.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import re
import select
import signal
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

from reflex_base.utils.process_tree import stop_process_tree

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import FrameType


# The supervisor PID, set for the child of supervise_output() and inherited
# by its descendants.
_SUPERVISED_ENV_VAR = "REFLEX_OUTPUT_SUPERVISED"

# How long a reader may sit idle after the child exits before the supervisor
# stops waiting for descendants that still hold the pipe.
_DRAIN_IDLE_SECONDS = 0.5

# Maximum drain time after the child exits, excluding time forwarding output.
_DRAIN_MAX_SECONDS = 5

# Seconds after the first shutdown signal before the command tree is killed.
_STOP_DEADLINE_SECONDS = 15

# Stop shutdown after 30 seconds even when a consumer blocks every write.
_DRAIN_WALL_SECONDS = 30

# Seconds a reader gets to finish the record it is writing when the drain ends.
_DRAIN_RECORD_GRACE_SECONDS = 2

# Line ends in child output; a lone ``\r`` ends a progress-bar update.
_LINE_END = re.compile(rb"\r\n|\r|\n")

# Largest write a POSIX pipe accepts whole or not at all. Windows has no such
# constant and no such guarantee; the Linux value keeps writes small there.
_PIPE_BUF = getattr(select, "PIPE_BUF", 4096)


def is_output_supervised() -> bool:
    """Check whether this process runs under supervise_output().

    Returns:
        True if a parent process turns this process's output into JSON records.
    """
    return bool(os.environ.get(_SUPERVISED_ENV_VAR))


def _is_json_record(line: bytes) -> bool:
    """Check whether a line already is a JSON log record.

    Args:
        line: The line to check.

    Returns:
        True if the line is a JSON object with a level and a message.
    """
    if not line.startswith(b"{"):
        return False
    try:
        record = json.loads(line)
    except ValueError:
        return False
    return isinstance(record, dict) and "level" in record and "message" in record


def _to_records(
    lines: list[bytes], traceback: list[str], level: str, name: str, final: bool
) -> list[bytes]:
    """Convert raw output lines to JSON lines.

    Lines that already are JSON log records pass through unchanged. A Python
    traceback is collected, across calls, into one record with the traceback
    text in its ``exception`` field.

    Args:
        lines: Complete output lines, without their newline.
        traceback: The lines of a traceback still being collected.
        level: The record level for plain lines.
        name: The logger name for the records.
        final: Whether the output ended, so an open traceback is emitted too.

    Returns:
        The JSON records, each ending with a newline.
    """
    timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()
    out: list[bytes] = []

    def record(message: str, level: str = level, exception: str | None = None):
        payload = {
            "timestamp": timestamp,
            "level": level,
            "logger": name,
            "message": message,
        }
        if exception is not None:
            payload["exception"] = exception
        out.append(json.dumps(payload).encode())

    for raw in lines:
        if _is_json_record(raw):
            out.append(raw)
            continue
        line = raw.decode("utf-8", "replace")
        if traceback:
            traceback.append(line)
            # Frames are indented; the exception line is not.
            if line.strip() and not line[0].isspace():
                record(line.strip(), "error", "\n".join(traceback) + "\n")
                traceback.clear()
        elif line.startswith("Traceback (most recent call last):"):
            traceback.append(line)
        else:
            record(line)
    if final and traceback:
        record(traceback[-1].strip(), "error", "\n".join(traceback) + "\n")
    return [line + b"\n" for line in out]


def _atomic_chunks(records: list[bytes]) -> Iterator[bytes]:
    """Group records into writes no larger than the pipe's atomic write size.

    A write of at most ``PIPE_BUF`` bytes enters a POSIX pipe whole or not at
    all, so a reader thread that is abandoned mid-write can never leave a
    partial record behind; only a single record above that size can be cut.

    Args:
        records: The JSON records, each ending with a newline.

    Yields:
        Chunks of consecutive records.
    """
    chunk: list[bytes] = []
    size = 0
    for record in records:
        if chunk and size + len(record) > _PIPE_BUF:
            yield b"".join(chunk)
            chunk, size = [], 0
        chunk.append(record)
        size += len(record)
    if chunk:
        yield b"".join(chunk)


def _write_all(fd: int, data: bytes):
    """Write all bytes to a file descriptor.

    Args:
        fd: The file descriptor.
        data: The bytes to write.
    """
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


class _OutputPump(threading.Thread):
    """Reader thread that turns one child output pipe into JSON lines."""

    def __init__(self, read_fd: int, write_fd: int, level: str, name: str):
        """Create the reader.

        Args:
            read_fd: The read end of the child's output pipe.
            write_fd: The file descriptor to write JSON lines to.
            level: The record level for plain lines.
            name: The logger name for the records.
        """
        super().__init__(name=f"reflex-output-{name}", daemon=True)
        self.read_fd = read_fd
        self.write_fd = write_fd
        self.level = level
        self.logger_name = name
        # Set by drain() when time is up: finish the current write, drop the rest.
        self._dropping = False
        # When the reader started waiting for data; None while it works.
        self.idle_since: float | None = None
        # Cumulative write time and the start of any ongoing write.
        self._write_state: tuple[float, float | None] = (0.0, None)
        self._write_lock = threading.Lock()
        # Clear while a write is in progress.
        self._write_done = threading.Event()
        self._write_done.set()

    def run(self):
        """Forward the pipe until every writer closed it."""
        pending = b""
        traceback: list[str] = []
        while True:
            self.idle_since = time.monotonic()
            chunk = os.read(self.read_fd, 1 << 16)
            self.idle_since = None
            if not chunk:
                break
            data = pending + chunk
            # A trailing \r may be the first half of a \r\n.
            cut = len(data) - data.endswith(b"\r")
            *lines, pending = _LINE_END.split(data[:cut])
            pending += data[cut:]
            self._write(lines, traceback, final=False)
        os.close(self.read_fd)
        pending = pending.removesuffix(b"\r")
        self._write([pending] if pending else [], traceback, final=True)

    def _write(self, lines: list[bytes], traceback: list[str], final: bool):
        """Write converted lines, dropping them if the consumer is gone.

        Args:
            lines: Complete output lines.
            traceback: The lines of a traceback still being collected.
            final: Whether the output ended.
        """
        records = _to_records(lines, traceback, self.level, self.logger_name, final)
        if not records or self._dropping:
            return
        self._write_done.clear()
        with self._write_lock:
            elapsed, _ = self._write_state
            started = time.monotonic()
            self._write_state = (elapsed, started)
        # Keep reading when the consumer is gone: a full pipe blocks the child.
        with contextlib.suppress(OSError):
            for chunk in _atomic_chunks(records):
                if self._dropping:
                    break
                _write_all(self.write_fd, chunk)
        with self._write_lock:
            self._write_state = (elapsed + time.monotonic() - started, None)
        self._write_done.set()

    def writing_snapshot(self) -> tuple[float, float]:
        """Capture the current time and cumulative write duration together.

        Returns:
            The monotonic time and seconds spent writing up to that time.
        """
        with self._write_lock:
            elapsed, started = self._write_state
            now = time.monotonic()
            return now, elapsed if started is None else elapsed + now - started

    def drain(self, exited_at: float, writing_at_exit: float, wall_deadline: float):
        """Wait until the pipe is drained after the child exited.

        Returns early when the reader sat idle for a while after the exit, or
        when the drain took too long. Time spent forwarding output does not
        count toward the active limit. A separate wall deadline bounds shutdown
        even when a consumer stops reading. A write in progress when time is
        up gets a short grace to complete; writes never exceed the pipe's
        atomic size, so an abandoned one cannot leave a partial record.

        Args:
            exited_at: The monotonic time of the pump's snapshot after child exit.
            writing_at_exit: The cumulative write time at that snapshot.
            wall_deadline: The shared monotonic deadline for shutdown.
        """
        while self.is_alive():
            self.join(0.05)
            now, writing_elapsed = self.writing_snapshot()
            idle_since = self.idle_since
            # Seconds charged against the five-second active drain budget.
            drain_elapsed = now - exited_at - (writing_elapsed - writing_at_exit)
            if (
                now > wall_deadline
                or drain_elapsed > _DRAIN_MAX_SECONDS
                or (
                    idle_since is not None
                    and now - max(idle_since, exited_at) > _DRAIN_IDLE_SECONDS
                )
            ):
                break
        self._dropping = True
        self._write_done.wait(_DRAIN_RECORD_GRACE_SECONDS)


def supervise_output(args: list[str]) -> int:
    """Run a command and turn everything it and its descendants print into JSON records.

    The command runs with its stdout and stderr on pipes, which every process
    it starts inherits. Reader threads write each line to this process's
    stdout and stderr as a JSON record: lines that already are JSON log
    records pass through, and a Python traceback becomes one record.

    Shutdown is bounded from the first SIGINT or SIGTERM: each one is passed
    on to the command, its whole process tree is killed if it is still
    running ``_STOP_DEADLINE_SECONDS`` later, and the output drain ends by
    ``_DRAIN_WALL_SECONDS`` after the request. Output goes out in writes of
    at most ``PIPE_BUF`` bytes, so on a pipe a record up to that size is
    never cut; a larger one can be when its consumer is slower than the
    grace the drain allows.

    Args:
        args: The command to run.

    Returns:
        The command's exit code.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.flush()
    # The readers decode UTF-8; Python otherwise uses the locale encoding.
    # A configured error handler is kept.
    _, _, errors = os.environ.get("PYTHONIOENCODING", "").partition(":")
    env = {
        "PYTHONUNBUFFERED": "1",
        **os.environ,
        _SUPERVISED_ENV_VAR: str(os.getpid()),
        "PYTHONIOENCODING": f"utf-8:{errors}" if errors else "utf-8",
    }
    # Raw pipes that only the readers close: closing a pipe while a reader is
    # blocked on it waits for that read on Windows.
    out_read, out_write = os.pipe()
    err_read, err_write = os.pipe()
    # The command stays in this process group: a terminal Ctrl-C or a group
    # kill from a service manager reaches it and its workers directly.
    proc = subprocess.Popen(args, stdout=out_write, stderr=err_write, env=env)
    os.close(out_write)
    os.close(err_write)
    shutdown = _Shutdown(proc)
    pumps = [
        _OutputPump(out_read, 1, "info", "stdout"),
        _OutputPump(err_read, 2, "warning", "stderr"),
    ]
    for pump in pumps:
        pump.start()
    # SIGTERM only on Windows, where Ctrl-C arrives as KeyboardInterrupt.
    handled = (
        (signal.SIGTERM, signal.SIGINT) if os.name == "posix" else (signal.SIGTERM,)
    )
    previous = {signum: signal.signal(signum, shutdown.on_signal) for signum in handled}
    try:
        while True:
            try:
                returncode = proc.wait()
                break
            except KeyboardInterrupt:
                # The command shares the console and received the Ctrl-C too.
                shutdown.request(None)
        requested_at = shutdown.requested_at
        _drain_pumps(
            pumps,
            (requested_at if requested_at is not None else time.monotonic())
            + _DRAIN_WALL_SECONDS,
        )
        # A child killed by a signal reports -signum; shells report 128 + signum.
        return returncode if returncode >= 0 else 128 - returncode
    finally:
        shutdown.cancel()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _drain_pumps(pumps: list[_OutputPump], wall_deadline: float):
    """Drain the readers after the command exited.

    Args:
        pumps: The reader threads.
        wall_deadline: The monotonic time by which the drain ends.
    """
    snapshots = [pump.writing_snapshot() for pump in pumps]
    for pump, (exited_at, writing_at_exit) in zip(pumps, snapshots, strict=True):
        while True:
            try:
                pump.drain(exited_at, writing_at_exit, wall_deadline)
                break
            except KeyboardInterrupt:
                # A repeated Windows Ctrl-C does not cut the drain short.
                continue


class _Shutdown:
    """Bounded shutdown of the supervised command.

    Every shutdown signal is passed on to the command, which decides what a
    repeat means. The first one also starts a deadline after which the whole
    command tree is killed, so a command that never finishes stopping, or one
    blocked on a full output pipe, cannot keep the supervisor alive.
    """

    def __init__(self, proc: subprocess.Popen):
        """Create the shutdown tracker.

        Args:
            proc: The supervised command.
        """
        self.proc = proc
        self.requested_at: float | None = None
        self._timer: threading.Timer | None = None

    def on_signal(self, signum: int, _frame: FrameType | None):
        """Handle a shutdown signal.

        Args:
            signum: The signal number.
            _frame: The interrupted frame.
        """
        self.request(signum)

    def request(self, signum: int | None):
        """Pass a shutdown request on to the command and arm the deadline.

        Args:
            signum: The signal to forward, or None when the command already
                received it (a Windows console Ctrl-C).
        """
        if self.requested_at is None:
            self.requested_at = time.monotonic()
            self._timer = threading.Timer(_STOP_DEADLINE_SECONDS, self._kill)
            self._timer.daemon = True
            self._timer.start()
        if signum is None:
            return
        if os.name == "posix":
            self.proc.send_signal(signum)
        else:
            # Windows has no graceful signal: terminating only the command
            # would leave its workers behind, so the whole tree goes at once.
            self._kill()

    def _kill(self):
        """Stop the command tree once the deadline passed."""
        stop_process_tree(self.proc, timeout=1)

    def cancel(self):
        """Disarm the deadline once the command exited."""
        if self._timer is not None:
            self._timer.cancel()
