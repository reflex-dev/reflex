"""Run reflex the way a user does: ``<python> -m reflex ...`` in a subprocess.

:func:`run_cli` runs one-shot commands (``init``, ``compile``, ``export``) and
:class:`AppProcess` runs ``reflex run`` until it is ready. Both start reflex
with the subject's interpreter in a new session, drain its merged stdout and
stderr on a thread and kill its whole process tree when done. The harness never imports the reflex under test:
the reflex version the caller passes decides what to expect from it.

Readiness has tiers, each a time in seconds since just before the spawn:

1. ``process_ready``: every expected ready line was printed and every expected
   port accepts TCP connections. In prod and preview reflex prints its line
   before the server binds, so a line alone never counts.
2. ``http_ready``: ``GET /`` (``/ping`` without a frontend) answers 200.
3. ``interactive_ready``: the page is interactive in a browser; measured by the
   browser driver of a later change.
"""

from __future__ import annotations

import atexit
import contextlib
import http.client
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import IO, Literal

import psutil
from packaging.version import Version

from reflex_bench.collectors import pss
from reflex_bench.collectors.cgroup import CgroupReading, CgroupScope
from reflex_bench.collectors.phases import (
    Attribution,
    TreePhases,
    TreeReport,
    attribute,
    parse_timing,
)
from reflex_bench.collectors.pss import PssResult, PssSampler
from reflex_bench.context import BASE_ENV

if sys.platform != "win32":
    import resource

Mode = Literal["dev", "prod", "preview"]

LOG_LINES = 2000
TAIL_LINES = 40
OWNER_ENV = "REFLEX_BENCH_OWNER"
APP_LINE = re.compile(r"App running at:\s*(\S+)")
BACKEND_LINE = re.compile(r"Backend running at:\s*(\S+)")
# From 0.9.0 prod serves frontend and backend on one port; --env preview exists from 0.9.8.
SINGLE_PORT_PROD = (0, 9)
PREVIEW = (0, 9, 8)

_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][0-9A-Za-z]|[@-Z\\-_])"
)
# Set whatever the caller passes: plain unbuffered output, no network checks and
# granian (0.8.23 prefers uvicorn when both are installed). A wide console keeps
# rich from wrapping a long ready line.
_FORCED_ENV = {
    **{
        name: BASE_ENV[name]
        for name in (
            "NO_COLOR",
            "PYTHONUNBUFFERED",
            "REFLEX_TELEMETRY_ENABLED",
            "REFLEX_CHECK_LATEST_VERSION",
            "REFLEX_USE_GRANIAN",
        )
    },
    "COLUMNS": "200",
}
# Runs the command, prints the tree's end marker, then holds the cgroup scope
# until stdin closes and exits with the command's status.
_KEEPER = (
    f'"$@" </dev/null; status=$?; echo "${OWNER_ENV}:done"; exec >&- 2>&-;'
    ' read -r _; exit "$status"'
)
_POLL_S = 0.02
_KILL_GRACE_S = 5.0


def strip_ansi(text: str) -> str:
    """Remove terminal escape sequences (colors, cursor moves, hyperlinks).

    Args:
        text: Output of a terminal program.

    Returns:
        The plain text.
    """
    return _ANSI.sub("", text)


def _clean(raw: bytes) -> str:
    """Turn a raw output line into plain text.

    Args:
        raw: A line read from the pipe.

    Returns:
        The line without escapes and without the parts a carriage return
        overwrote on a terminal (progress bars).
    """
    text = strip_ansi(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    segments = [segment for segment in text.split("\r") if segment.strip()]
    return segments[-1].rstrip() if segments else ""


def free_ports(count: int = 1) -> list[int]:
    """Pick free TCP ports by binding to port 0.

    Another process may take a port before reflex binds it; ready lines and TCP
    probes then report the problem.

    Args:
        count: How many ports.

    Returns:
        Distinct ports.
    """
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(sock)
            sock.bind(("", 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def cache_env(
    *,
    reflex_dir: Path | None = None,
    web_dir: Path | None = None,
    states_dir: Path | None = None,
    bun_cache: Path | None = None,
) -> dict[str, str]:
    """Point reflex's caches at directories a benchmark owns.

    A fresh ``reflex_dir`` is a cold start: bun and the templates live under it.
    bun's package cache does not, so a cold package install also needs a fresh
    ``bun_cache``.

    Args:
        reflex_dir: ``REFLEX_DIR``, reflex's data directory.
        web_dir: ``REFLEX_WEB_WORKDIR``, the app's ``.web`` directory.
        states_dir: ``REFLEX_STATES_WORKDIR``, the disk state manager's directory.
        bun_cache: ``BUN_INSTALL_CACHE_DIR``, bun's global package cache.

    Returns:
        The environment variables of the given directories.
    """
    names = {
        "REFLEX_DIR": reflex_dir,
        "REFLEX_WEB_WORKDIR": web_dir,
        "REFLEX_STATES_WORKDIR": states_dir,
        "BUN_INSTALL_CACHE_DIR": bun_cache,
    }
    return {name: str(path) for name, path in names.items() if path is not None}


def _reflex_env(env: Mapping[str, str]) -> dict[str, str]:
    """Build the environment of a reflex subprocess.

    Args:
        env: The caller's environment, normally ``ctx.env``.

    Returns:
        The environment with the settings the driver relies on forced.
    """
    return {**env, **_FORCED_ENV}


def _check_platform() -> None:
    """Refuse to drive reflex where process groups do not exist.

    Raises:
        NotImplementedError: On Windows.
    """
    if sys.platform == "win32":
        msg = "reflex-bench drives reflex on Linux and macOS; Windows is not supported"
        raise NotImplementedError(msg)


@dataclass(frozen=True)
class _Topology:
    """What ``reflex run`` announces and listens on, for one mode and version.

    Attributes:
        ready: The line announcing each role's URL (``frontend``, ``backend``);
            every one must be printed.
        single_port: Whether frontend and backend share one port.
    """

    ready: dict[str, re.Pattern[str]]
    single_port: bool


def _topology(mode: Mode, version: str | None, *, backend_only: bool) -> _Topology:
    """Decide what a ``reflex run`` of this mode and version prints and binds.

    Args:
        mode: ``dev``, ``prod`` or ``preview``.
        version: The subject's reflex version.
        backend_only: Whether it runs with ``--backend-only``.

    Returns:
        The topology.

    Raises:
        ValueError: On an unknown or unparsable version, or a mode the version lacks.
    """
    if version is None:
        msg = "the reflex version is unknown; pass the subject's reflex_version"
        raise ValueError(msg)
    release = Version(version).release
    if mode == "preview" and release < PREVIEW:
        msg = f"--env preview needs reflex 0.9.8 or later (subject has {version})"
        raise ValueError(msg)
    if mode == "dev" or release < SINGLE_PORT_PROD:
        # Dev and 0.8.23 prod (sirv) print both lines once the frontend is up;
        # the backend binds on its own schedule.
        if backend_only:
            return _Topology({"backend": BACKEND_LINE}, single_port=False)
        return _Topology(
            {"frontend": APP_LINE, "backend": BACKEND_LINE}, single_port=False
        )
    # One port, announced only by "App running at", even with --backend-only.
    return _Topology(
        {"backend" if backend_only else "frontend": APP_LINE}, single_port=True
    )


def _local_url(url: str) -> str:
    """Normalize an announced URL for clients on this machine.

    Args:
        url: E.g. ``http://0.0.0.0:3000/``.

    Returns:
        E.g. ``http://localhost:3000``: wildcard hosts become ``localhost`` and the
        trailing slash goes.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or "localhost"
    if host in {"0.0.0.0", "::"}:
        host = "localhost"
    netloc = f"[{host}]" if ":" in host else host
    if parts.port:
        netloc += f":{parts.port}"
    return urllib.parse.urlunsplit((
        parts.scheme or "http",
        netloc,
        parts.path.rstrip("/"),
        "",
        "",
    ))


def _endpoint(url: str) -> tuple[str, int]:
    """Find the TCP endpoint of a URL.

    Args:
        url: The URL.

    Returns:
        ``(host, port)``, with ``localhost`` as ``127.0.0.1``: reflex binds IPv4.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or "localhost"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return ("127.0.0.1" if host == "localhost" else host), port


# Local requests must not go through the proxies of the environment.
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url: str) -> str | None:
    """Request a URL once.

    Args:
        url: The URL.

    Returns:
        ``None`` for a 200 answer, else what went wrong (``HTTP 503``, a
        refused connection, ...).
    """
    try:
        with _LOCAL.open(url, timeout=5) as response:
            response.read()
            return None if response.status == 200 else f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        exc.close()
        return f"HTTP {exc.code}"
    except (OSError, http.client.HTTPException) as exc:
        return str(exc) or type(exc).__name__


def _accepts(endpoint: tuple[str, int]) -> bool:
    """Check that a TCP endpoint accepts connections.

    Args:
        endpoint: ``(host, port)``.

    Returns:
        Whether a connection succeeded.
    """
    try:
        with socket.create_connection(endpoint, timeout=0.5):
            return True
    except OSError:
        return False


class _ReadyLines:
    """Watches output for the lines that announce each role's URL."""

    def __init__(self, patterns: Mapping[str, re.Pattern[str]]) -> None:
        """Start watching.

        Args:
            patterns: The line announcing each role's URL; the URL is group 1.
        """
        self._pending = dict(patterns)
        self.urls: dict[str, str] = {}
        self.seen_at: float | None = None

    @property
    def done(self) -> bool:
        """Whether every line was seen.

        Returns:
            True once the last one was.
        """
        return not self._pending

    def feed(self, line: str, at: float) -> None:
        """Check one output line.

        Args:
            line: The line, escapes stripped.
            at: When it was read, in seconds since the spawn.
        """
        for role, pattern in list(self._pending.items()):
            if match := pattern.search(line):
                try:
                    url = _local_url(match[1])
                    _endpoint(url)
                except ValueError:
                    # Not a URL (e.g. a bad port); this runs on the reader
                    # thread, which must keep draining whatever it is fed.
                    continue
                self.urls[role] = url
                del self._pending[role]
                if not self._pending:
                    self.seen_at = at


class _Output:
    """Drains a child's merged stdout and stderr on a daemon thread.

    The child never blocks on a full pipe. Waiters are woken for every line and
    at the end of the output.
    """

    def __init__(
        self,
        stream: IO[bytes],
        t0: float,
        *,
        maxlen: int | None,
        on_line: Callable[[str, float], None] | None = None,
        marker: str | None = None,
    ) -> None:
        """Start draining.

        Args:
            stream: The child's stdout.
            t0: The ``time.perf_counter()`` taken just before the spawn.
            maxlen: The most lines to keep; ``None`` keeps all.
            on_line: Called with each line and its time since ``t0``, under the lock.
            marker: Text that ends the line printed when the command ended; it is
                removed from the output and its time kept in :attr:`marker_at`.
        """
        self._stream = stream
        self._t0 = t0
        self._lines: deque[str] = deque(maxlen=maxlen)
        self._on_line = on_line
        self._marker = marker
        self.closed_at: float | None = None
        self.marker_at: float | None = None
        self.cond = threading.Condition()
        self._thread = threading.Thread(
            target=self._drain, name="reflex-bench output", daemon=True
        )
        self._thread.start()

    def _drain(self) -> None:
        """Read lines until the end of the output."""
        try:
            for raw in iter(self._stream.readline, b""):
                at = time.perf_counter() - self._t0
                line = _clean(raw)
                with self.cond:
                    if self._marker is not None and line.endswith(self._marker):
                        # The marker follows the command's last line, even an unterminated one.
                        self.marker_at = at
                        line = line.removesuffix(self._marker)
                        if not line:
                            self.cond.notify_all()
                            continue
                    self._lines.append(line)
                    if self._on_line is not None:
                        self._on_line(line, at)
                    self.cond.notify_all()
        except (OSError, ValueError):
            # The pipe was closed under the reader.
            pass
        finally:
            with self.cond:
                self.closed_at = time.perf_counter() - self._t0
                self.cond.notify_all()

    @property
    def closed(self) -> bool:
        """Whether the output ended.

        Returns:
            True once every process holding the pipe closed it.
        """
        return self.closed_at is not None

    def lines(self) -> list[str]:
        """Copy the kept lines.

        Returns:
            The lines, oldest first.
        """
        with self.cond:
            return list(self._lines)

    def wait(self, predicate: Callable[[], bool], timeout: float) -> bool:
        """Wait until a condition holds, re-checking it after every line.

        Args:
            predicate: The condition.
            timeout: Seconds to wait at most.

        Returns:
            Whether the condition holds.
        """
        with self.cond:
            return self.cond.wait_for(predicate, max(0.0, timeout))

    def wake(self) -> None:
        """Wake the waiters, e.g. to notice a stop."""
        with self.cond:
            self.cond.notify_all()

    def join(self, timeout: float) -> None:
        """Wait for the end of the output, then close the pipe.

        Args:
            timeout: Seconds to wait.
        """
        self._thread.join(timeout)
        if not self._thread.is_alive():
            self._stream.close()


def _signal_group(pgid: int, sig: int) -> None:
    """Signal a process group, refusing groups that are not a benchmark's.

    ``killpg(1)`` is ``kill(-1)``: every process of the user. Groups below 2 and
    the harness's own group are never signalled.

    Args:
        pgid: The process group id.
        sig: The signal.
    """
    if pgid <= 1 or pgid == os.getpgrp():
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


def _signal(proc: psutil.Process, sig: int) -> None:
    """Signal one process, refusing pids below 2 and the harness itself.

    psutil checks the process's identity first, so a reused pid is never signalled.

    Args:
        proc: The process.
        sig: The signal.
    """
    if proc.pid <= 1 or proc.pid == os.getpid():
        return
    with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        proc.send_signal(sig)


def _pgid(proc: psutil.Process) -> int | None:
    """Read a process's group id.

    Args:
        proc: The process.

    Returns:
        The group id, or ``None`` when the process is gone.
    """
    try:
        return os.getpgid(proc.pid)
    except OSError:
        return None


def _running(proc: psutil.Process) -> bool:
    """Check that a process still runs; a zombie counts as gone.

    Args:
        proc: The process.

    Returns:
        Whether it runs; ``True`` when that cannot be told.
    """
    try:
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True


def _alive(procs: Sequence[psutil.Process]) -> list[psutil.Process]:
    """Keep the processes that still run.

    Args:
        procs: The processes.

    Returns:
        The running ones.
    """
    return [proc for proc in procs if _running(proc)]


def _wait_gone(procs: Sequence[psutil.Process], timeout: float) -> list[psutil.Process]:
    """Wait for processes to exit.

    Args:
        procs: The processes.
        timeout: Seconds to wait.

    Returns:
        The ones still running.
    """
    deadline = time.monotonic() + timeout
    alive = _alive(procs)
    while alive and time.monotonic() < deadline:
        time.sleep(_POLL_S)
        alive = _alive(alive)
    return alive


def _describe(proc: psutil.Process) -> str:
    """Name a process for an error message.

    Args:
        proc: The process.

    Returns:
        ``pid (name)``, or the pid when the name cannot be read.
    """
    try:
        return f"{proc.pid} ({proc.name()})"
    except psutil.Error:
        return str(proc.pid)


def _owned_by(proc: psutil.Process, token: str) -> bool:
    """Check whether a process belongs to a tree, by its environment.

    Args:
        proc: The process.
        token: The tree's owner token.

    Returns:
        Whether the process carries the token; ``False`` when its environment
        cannot be read.
    """
    try:
        return proc.environ().get(OWNER_ENV) == token
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


_LIVE: set[_ProcessTree] = set()
_LIVE_LOCK = threading.Lock()


class _ProcessTree:
    """A command started in its own session, with everything it spawns.

    The command leads a new session and process group, so the terminal's Ctrl-C
    never reaches it and one signal to the group reaches its children, except
    those that start a session of their own. Every process of the tree inherits
    ``REFLEX_BENCH_OWNER=<token>``, which finds them even after they were
    re-parented away from the root.
    """

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        maxlen: int | None,
        on_line: Callable[[str, float], None] | None = None,
        keeper: bool = False,
    ) -> None:
        """Start the command.

        Args:
            argv: The command.
            cwd: Its working directory.
            env: Its environment.
            maxlen: The most output lines to keep; ``None`` keeps all.
            on_line: Called with each output line and its time since the spawn.
            keeper: Whether the command runs under :data:`_KEEPER`, which reads
                stdin and marks the end of the command in its output.
        """
        self.token = secrets.token_hex(8)
        self.t0 = time.perf_counter()
        self.proc = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env={**env, OWNER_ENV: self.token},
            stdin=subprocess.PIPE if keeper else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.spawned = time.perf_counter() - self.t0
        # The new session's leader: its pid is the group id.
        self.pid = self.pgid = self.proc.pid
        self.root = psutil.Process(self.pid)
        self.exited_at: float | None = None
        self._reaped = threading.Event()
        self._reaper: threading.Thread | None = None
        assert self.proc.stdout is not None
        self.output = _Output(
            self.proc.stdout,
            self.t0,
            maxlen=maxlen,
            on_line=on_line,
            marker=f"{self.token}:done" if keeper else None,
        )
        with _LIVE_LOCK:
            _LIVE.add(self)

    def wait_exit(self, timeout: float) -> float | None:
        """Wait for the root to exit, and reap it.

        A blocking ``waitpid`` on a thread takes the exit time exactly, where
        ``Popen.wait(timeout)`` would poll.

        Args:
            timeout: Seconds to wait.

        Returns:
            When the root exited, in seconds since the spawn, or ``None`` after
            the timeout.
        """
        if self._reaper is None:
            self._reaper = threading.Thread(
                target=self._reap, name="reflex-bench reaper", daemon=True
            )
            self._reaper.start()
        self._reaped.wait(max(0.0, timeout))
        return self.exited_at

    def _reap(self) -> None:
        """Wait for the root and note when it exited."""
        self.proc.wait()
        self.exited_at = time.perf_counter() - self.t0
        self._reaped.set()

    def exited(self) -> bool:
        """Check whether the root exited, without reaping it.

        Returns:
            True once the root is a zombie or reaped.
        """
        if self.proc.returncode is not None:
            return True
        try:
            return self.root.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return True

    def members(self) -> list[psutil.Process]:
        """Find every process of the tree.

        Returns:
            The root, its descendants and every process carrying the owner token.
        """
        found: dict[int, psutil.Process] = {}
        try:
            for proc in [self.root, *self.root.children(recursive=True)]:
                found[proc.pid] = proc
        except psutil.NoSuchProcess:
            pass
        me = os.getpid()
        found.update(
            (proc.pid, proc)
            for proc in psutil.process_iter()
            if proc.pid not in found and proc.pid != me and _owned_by(proc, self.token)
        )
        return list(found.values())

    def kill(self, timeout: float) -> None:
        """Stop the whole tree and reap the root.

        SIGTERM goes to the process group and to members outside it; whatever
        still runs after ``timeout`` seconds, or was spawned meanwhile, gets
        SIGKILL.

        Args:
            timeout: Seconds to wait after SIGTERM.

        Raises:
            RuntimeError: When a process of the tree survives SIGKILL.
        """
        # Collect before signalling: children re-parent once their parent dies.
        procs = self.members()
        # Only an unreaped root keeps the group id from being reused.
        by_group = self.proc.returncode is None
        if by_group:
            _signal_group(self.pgid, signal.SIGTERM)
        for proc in procs:
            if not by_group or _pgid(proc) != self.pgid:
                _signal(proc, signal.SIGTERM)
        alive = _wait_gone(procs, timeout)
        for _ in range(3):
            known = {proc.pid for proc in procs}
            late = [proc for proc in self.members() if proc.pid not in known]
            procs.extend(late)
            alive = _alive([*alive, *late])
            if not alive:
                break
            for proc in alive:
                _signal(proc, signal.SIGKILL)
            alive = _wait_gone(alive, _KILL_GRACE_S)
        try:
            self.proc.wait(_KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            alive = _alive([self.root, *alive])
        self.output.join(_KILL_GRACE_S)
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        with _LIVE_LOCK:
            _LIVE.discard(self)
        if alive:
            msg = f"processes survived SIGKILL: {', '.join(map(_describe, alive))}"
            raise RuntimeError(msg)


def _kill_live_trees() -> None:
    """Kill the trees still running when the harness exits, e.g. after Ctrl-C."""
    with _LIVE_LOCK:
        trees = list(_LIVE)
    for tree in trees:
        # Survivors cannot be helped at exit; the other trees must still be killed.
        with contextlib.suppress(Exception):
            tree.kill(timeout=2.0)


atexit.register(_kill_live_trees)


def _wait_for_marker(tree: _ProcessTree, deadline: float) -> float | None:
    """Wait for the keeper to report the end of the command.

    Args:
        tree: The tree started with :data:`_KEEPER`.
        deadline: The ``time.perf_counter()`` to give up at.

    Returns:
        When the command ended, in seconds since the spawn (when the keeper died
        without reporting it, when the keeper exited), or ``None`` at the deadline.
    """
    output = tree.output
    while True:
        remaining = deadline - time.perf_counter()
        if output.wait(lambda: output.marker_at is not None, min(0.25, remaining)):
            return output.marker_at
        if tree.exited():
            return tree.wait_exit(_KILL_GRACE_S)
        if remaining <= 0:
            return None


def _children_cpu_s() -> float:
    """Read the CPU time of the harness's reaped children.

    Returns:
        User and system seconds, including the descendants they reaped.
    """
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


@dataclass(frozen=True)
class CliResult:
    """What :func:`run_cli` measured.

    Attributes:
        args: The reflex arguments that ran, ``--loglevel debug`` included.
        returncode: The exit code; negative for a signal (a timeout kills the tree).
        wall_s: Seconds from just before the spawn to the end of the command.
        lines: The merged stdout and stderr, escapes stripped.
        timeout_s: The timeout.
        timed_out: Whether the tree was killed at the timeout.
        cpu_s: CPU seconds of the tree.
        cpu_method: ``cgroup`` (the scope's ``cpu.stat``) or ``rusage`` (reaped
            children, so processes that outlive their parent are missed).
        peak_mem_bytes: The tree's peak memory, when measured.
        memory_method: ``cgroup`` or ``pss_sampling``; the two never compare.
        cgroup: The scope's counters, with a scope.
        pss: The PSS samples, with ``sample_memory`` and no scope.
        timing: Seconds per ``[timing]`` phase, with ``phases``.
        tree: The sampled process tree, with ``phases``.
    """

    args: list[str]
    returncode: int
    wall_s: float
    lines: list[str]
    timeout_s: float
    timed_out: bool = False
    cpu_s: float = 0.0
    cpu_method: str = "rusage"
    peak_mem_bytes: int | None = None
    memory_method: str | None = None
    cgroup: CgroupReading | None = None
    pss: PssResult | None = None
    timing: dict[str, float] = field(default_factory=dict)
    tree: TreeReport | None = None

    def tail(self, count: int = TAIL_LINES) -> str:
        """Show the end of the output.

        Args:
            count: How many lines.

        Returns:
            The last lines, newline-separated.
        """
        return "\n".join(self.lines[-count:])

    def check(self) -> CliResult:
        """Require a successful exit.

        Returns:
            The result.

        Raises:
            RuntimeError: When the command timed out or exited with an error,
                with the end of its output.
        """
        command = " ".join(["reflex", *self.args])
        if self.timed_out:
            msg = f"{command} timed out after {self.timeout_s:g} s:\n{self.tail()}"
            raise RuntimeError(msg)
        if self.returncode != 0:
            msg = f"{command} exited with code {self.returncode}:\n{self.tail()}"
            raise RuntimeError(msg)
        return self

    def attribution(self) -> Attribution | None:
        """Split the wall time into Python phases, installs, frontend tools and the rest.

        Returns:
            The attribution, or ``None`` without ``phases``.
        """
        if self.tree is None:
            return None
        return attribute(self.wall_s, self.timing, self.tree)


def run_cli(
    python: Path,
    args: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float,
    scope: CgroupScope | None = None,
    phases: bool = False,
    sample_memory: bool = False,
    prefix: Sequence[str] = ("-m", "reflex"),
) -> CliResult:
    """Run a one-shot reflex command (``init``, ``compile``, ``export``) and measure it.

    With a scope, the command runs under a small shell that keeps the scope's
    cgroup alive after the command exits, so its counters can be read; the
    shell adds about a megabyte to the peak.

    Args:
        python: The subject's interpreter.
        args: The reflex arguments, e.g. ``["compile"]``.
        cwd: The app directory.
        env: The environment: ``ctx.env``, or
            :func:`~reflex_bench.context.subject_env` of ``python`` outside a
            benchmark, so commands reflex starts by name come from the subject.
        timeout: Seconds before the whole tree is killed.
        scope: A cgroup scope to run in, for whole-tree peak memory and CPU.
        phases: Log at debug level, parse the ``[timing]`` lines and sample the
            process tree for :meth:`CliResult.attribution`.
        sample_memory: Without a scope, sample the tree's PSS for its peak.
        prefix: The interpreter arguments before ``args``; e.g.
            ``("-c", "import reflex")`` with no ``args`` times the import.

    Returns:
        The result; :meth:`CliResult.check` raises on failure.

    Raises:
        RuntimeError: When ``sample_memory`` is asked for where PSS cannot be read.
    """
    _check_platform()
    if sample_memory and scope is None and (reason := pss.available()) is not None:
        msg = f"cannot sample memory: {reason}"
        raise RuntimeError(msg)
    args = [*args, *(("--loglevel", "debug") if phases else ())]
    env = _reflex_env(env)
    argv = [str(python), *prefix, *args]
    if scope is not None:
        argv = scope.wrap(["/bin/sh", "-c", _KEEPER, "sh", *argv], env=env)
    cpu_before = _children_cpu_s()
    tree = _ProcessTree(argv, cwd=cwd, env=env, maxlen=None, keeper=scope is not None)
    tree_sampler = memory_sampler = reading = end = None
    try:
        if phases:
            tree_sampler = TreePhases(tree.pid, t0=tree.t0).start()
        if sample_memory and scope is None:
            memory_sampler = PssSampler(tree.pid, t0=tree.t0).start()
        deadline = tree.t0 + timeout
        if scope is None:
            end = tree.wait_exit(deadline - time.perf_counter())
        else:
            scope.attach(tree.pid)
            end = _wait_for_marker(tree, deadline)
            if tree.output.marker_at is not None:
                # The keeper still holds the scope, so its cgroup can be read.
                reading = scope.read()
    finally:
        if scope is not None:
            scope.close()
            if tree.proc.stdin is not None:
                tree.proc.stdin.close()
            if end is not None:
                # Let the keeper exit with the command's status before the teardown.
                tree.wait_exit(_KILL_GRACE_S)
        try:
            tree.kill(_KILL_GRACE_S)
        finally:
            try:
                tree_report = tree_sampler.stop() if tree_sampler else None
            finally:
                memory = memory_sampler.stop() if memory_sampler else None
    lines = tree.output.lines()
    if reading is not None:
        cpu_s, cpu_method = reading.cpu_s, "cgroup"
        peak, memory_method = reading.memory_peak_bytes, "cgroup"
    else:
        cpu_s, cpu_method = _children_cpu_s() - cpu_before, "rusage"
        peak = memory.peak_bytes if memory else None
        memory_method = memory.method if memory else None
    return CliResult(
        args=list(args),
        returncode=tree.proc.returncode,
        wall_s=timeout if end is None else end,
        lines=lines,
        timeout_s=timeout,
        timed_out=end is None,
        cpu_s=cpu_s,
        cpu_method=cpu_method,
        peak_mem_bytes=peak,
        memory_method=memory_method,
        cgroup=reading,
        pss=memory,
        timing=parse_timing(lines) if phases else {},
        tree=tree_report,
    )


@dataclass
class Readiness:
    """When a started app reached each readiness tier.

    Every time is in seconds since the ``time.perf_counter()`` taken just before
    the spawn.

    Attributes:
        spawned: When ``Popen`` returned.
        ready_line: When the last expected ready line was read.
        process_ready: Tier 1: when the lines were printed and every expected port
            accepted a TCP connection.
        http_ready: Tier 2: when ``GET`` answered 200 (:meth:`AppProcess.wait_http_ready`).
        interactive_ready: Tier 3: when the page was interactive in a browser, set
            by the browser driver.
    """

    spawned: float
    ready_line: float
    process_ready: float
    http_ready: float | None = None
    interactive_ready: float | None = None


class AppStartError(RuntimeError):
    """reflex did not become ready; the message ends with its last output lines."""

    def __init__(self, message: str, lines: Sequence[str]) -> None:
        """Describe the failure.

        Args:
            message: What went wrong.
            lines: The app's output.
        """
        tail = "\n".join(lines[-TAIL_LINES:])
        super().__init__(f"{message}\n{tail}" if tail else message)
        self.lines = list(lines)


class _NotReadyError(Exception):
    """A start failed; no message means the app exited."""


class AppProcess:
    """``reflex run`` in a subprocess, from start to readiness to teardown.

    Use it as a context manager, or call :meth:`start` and :meth:`stop`, which
    kills the whole process tree and may be called from another thread, e.g. by a
    benchmark's ``conclude`` while ``sample`` still waits for readiness.
    """

    def __init__(
        self,
        python: Path,
        app_dir: Path,
        *,
        mode: Mode,
        reflex_version: str | None,
        env: Mapping[str, str],
        extra_args: Sequence[str] = (),
        backend_only: bool = False,
        frontend_port: int | None = None,
        backend_port: int | None = None,
        start_timeout: float = 300.0,
        scope: CgroupScope | None = None,
        phases: bool = False,
    ) -> None:
        """Plan the run; nothing starts yet.

        Args:
            python: The subject's interpreter.
            app_dir: The app directory.
            mode: ``dev``, ``prod`` or ``preview`` (``--env``).
            reflex_version: The subject's reflex version, which decides the
                expected ready lines and ports.
            env: The environment: ``ctx.env``, or
                :func:`~reflex_bench.context.subject_env` of ``python`` outside
                a benchmark, so commands reflex starts by name (0.8.x prod
                starts ``granian``) come from the subject.
            extra_args: More ``reflex run`` arguments.
            backend_only: Run with ``--backend-only``.
            frontend_port: The frontend port; a free one by default.
            backend_port: The backend port; a free one by default. Where
                frontend and backend share a port, either one sets it.
            start_timeout: Seconds :meth:`start` waits for readiness.
            scope: A cgroup scope to run in; read it before :meth:`stop`.
            phases: Log at debug level, for the ``[timing]`` lines.

        Raises:
            ValueError: On ports that do not fit the mode and version.
        """
        _check_platform()
        self.python = python
        self.app_dir = app_dir
        self.mode = mode
        self.backend_only = backend_only
        self.start_timeout = start_timeout
        self.scope = scope
        self._topology = _topology(mode, reflex_version, backend_only=backend_only)
        if backend_only and frontend_port is not None:
            msg = "frontend_port does not apply to a backend-only run"
            raise ValueError(msg)
        if self._topology.single_port:
            if frontend_port and backend_port and frontend_port != backend_port:
                msg = f"reflex {reflex_version} runs --env {mode} on one port; the ports differ"
                raise ValueError(msg)
            backend_port = frontend_port or backend_port or free_ports()[0]
            frontend_port = None if backend_only else backend_port
        else:
            wanted = [backend_port is None, frontend_port is None and not backend_only]
            fresh = iter(free_ports(sum(wanted)))
            backend_port = backend_port or next(fresh)
            if not backend_only:
                frontend_port = frontend_port or next(fresh)
        ports = ["--backend-port", str(backend_port)]
        if frontend_port is not None:
            ports = ["--frontend-port", str(frontend_port), *ports]
        self._args = [
            "run",
            "--env",
            mode,
            *(["--backend-only"] if backend_only else []),
            *ports,
            *extra_args,
            *(["--loglevel", "debug"] if phases else []),
        ]
        self._env = _reflex_env(env)
        self.frontend_url: str | None = (
            None if frontend_port is None else f"http://localhost:{frontend_port}"
        )
        self.backend_url = f"http://localhost:{backend_port}"
        self.readiness: Readiness | None = None
        self._tree: _ProcessTree | None = None
        self._lock = threading.Lock()
        self._stopped = False

    @property
    def pid(self) -> int:
        """The pid of the started command (``systemd-run``/``sudo`` in a scope).

        Returns:
            The pid.

        Raises:
            RuntimeError: Before :meth:`start`.
        """
        if self._tree is None:
            msg = "the app was not started"
            raise RuntimeError(msg)
        return self._tree.pid

    def logs(self) -> list[str]:
        """Copy the app's recent output.

        Returns:
            Up to :data:`LOG_LINES` lines, escapes stripped, oldest first.
        """
        return self._tree.output.lines() if self._tree is not None else []

    def is_running(self) -> bool:
        """Check the started command.

        Returns:
            Whether it runs.
        """
        return self._tree is not None and not self._tree.exited()

    def start(self) -> Readiness:
        """Start ``reflex run`` and wait until it is process-ready (tier 1).

        A failed start stops the whole tree before raising.

        Returns:
            The readiness, also kept in :attr:`readiness`.

        Raises:
            AppStartError: When the app exits, is stopped or is not ready in
                time, with the end of its output.
            RuntimeError: When the app was already started.
        """
        with self._lock:
            if self._stopped:
                msg = "reflex run was stopped before it started"
                raise AppStartError(msg, [])
            if self._tree is not None:
                msg = "start() was already called"
                raise RuntimeError(msg)
            argv = [str(self.python), "-m", "reflex", *self._args]
            if self.scope is not None:
                argv = self.scope.wrap(argv, env=self._env)
            watcher = _ReadyLines(self._topology.ready)
            tree = self._tree = _ProcessTree(
                argv,
                cwd=self.app_dir,
                env=self._env,
                maxlen=LOG_LINES,
                on_line=watcher.feed,
            )
        try:
            if self.scope is not None:
                self.scope.attach(tree.pid, timeout=self.start_timeout)
            self.readiness = self._wait_until_ready(tree, watcher)
        except _NotReadyError as exc:
            self.stop()
            message = str(exc) or (
                f"reflex run exited with code {tree.proc.returncode} before it was ready"
            )
            raise AppStartError(message, tree.output.lines()) from None
        except BaseException:
            self.stop()
            raise
        return self.readiness

    def _wait_until_ready(self, tree: _ProcessTree, watcher: _ReadyLines) -> Readiness:
        """Wait for the ready lines, then for the announced ports.

        Args:
            tree: The started app.
            watcher: The watcher of its ready lines.

        Returns:
            The readiness.

        Raises:
            _NotReadyError: When the app exits, is stopped or runs out of time.
        """
        deadline = tree.t0 + self.start_timeout
        # A child that outlives reflex can hold the output open, so the root's
        # exit is checked as well as the end of the output.
        while not (watcher.done or self._stopped or tree.exited()):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            tree.output.wait(
                lambda: watcher.done or self._stopped, min(0.25, remaining)
            )
        ready_line = watcher.seen_at
        if self._stopped:
            msg = "reflex run was stopped before it was ready"
            raise _NotReadyError(msg)
        if ready_line is None:
            if tree.exited():
                raise _NotReadyError
            msg = f"reflex run was not ready within {self.start_timeout:g} s"
            raise _NotReadyError(msg)
        if "frontend" in watcher.urls:
            self.frontend_url = watcher.urls["frontend"]
        self.backend_url = watcher.urls.get(
            "backend", self.frontend_url or self.backend_url
        )
        pending = {
            _endpoint(url) for url in (self.frontend_url, self.backend_url) if url
        }
        while pending := {endpoint for endpoint in pending if not _accepts(endpoint)}:
            if self._stopped:
                msg = "reflex run was stopped before it was ready"
                raise _NotReadyError(msg)
            if tree.exited():
                raise _NotReadyError
            if time.perf_counter() >= deadline:
                ports = ", ".join(str(port) for _, port in sorted(pending))
                msg = (
                    "reflex run printed its ready lines but was not accepting"
                    f" connections on port {ports} within {self.start_timeout:g} s"
                )
                raise _NotReadyError(msg)
            time.sleep(_POLL_S)
        return Readiness(
            spawned=tree.spawned,
            ready_line=ready_line,
            process_ready=time.perf_counter() - tree.t0,
        )

    def wait_http_ready(self, path: str | None = None, timeout: float = 120.0) -> float:
        """Wait until ``GET`` answers 200 (tier 2).

        Args:
            path: The path to request; ``/`` on the frontend, or ``/ping`` on the
                backend without a frontend.
            timeout: Seconds to wait.

        Returns:
            When it answered, in seconds since the spawn; also kept in
            :attr:`readiness`.

        Raises:
            RuntimeError: Before :meth:`start`.
            AppStartError: When the app exits or does not answer in time.
        """
        tree, readiness = self._tree, self.readiness
        if tree is None or readiness is None:
            msg = "start() the app before waiting for HTTP"
            raise RuntimeError(msg)
        if path is None:
            path = "/" if self.frontend_url else "/ping"
        url = (self.frontend_url or self.backend_url) + path
        deadline = time.perf_counter() + timeout
        while (last := _get(url)) is not None:
            if self._stopped or tree.exited():
                how = "was stopped" if self._stopped else "exited"
                msg = f"reflex run {how} while waiting for GET {path} to answer 200"
                raise AppStartError(msg, tree.output.lines())
            if time.perf_counter() >= deadline:
                msg = (
                    f"GET {path} did not answer 200 within {timeout:g} s (last: {last})"
                )
                raise AppStartError(msg, tree.output.lines())
            time.sleep(0.05)
        readiness.http_ready = time.perf_counter() - tree.t0
        return readiness.http_ready

    def stop(self, timeout: float = 10.0) -> None:
        """Kill the whole process tree; safe to call again and from another thread.

        A call made while another thread stops the app returns once that
        teardown is done.

        Args:
            timeout: Seconds between SIGTERM and SIGKILL.
        """
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            tree = self._tree
            if tree is None:
                return
            tree.output.wake()
            try:
                tree.kill(timeout)
            finally:
                if self.scope is not None:
                    self.scope.close()

    def __enter__(self) -> AppProcess:
        """Start the app.

        Returns:
            The app, process-ready.
        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the app.

        Args:
            exc_type: The exception type, if any.
            exc: The exception, if any.
            traceback: Its traceback, if any.
        """
        self.stop()
