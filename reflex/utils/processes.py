"""Process operations."""

from __future__ import annotations

import collections
import contextlib
import ctypes
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from _thread import interrupt_main
from collections.abc import Callable, Generator, Sequence
from concurrent import futures
from contextlib import closing
from pathlib import Path
from typing import Any, Literal, overload

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment
from rich.markup import escape
from rich.progress import Progress

from reflex.utils import console, path_ops, prerequisites
from reflex.utils.registry import get_npm_registry

logger = logging.getLogger(__name__)


def kill(pid: int):
    """Kill a process.

    Args:
        pid: The process ID.
    """
    os.kill(pid, signal.SIGTERM)


def get_num_workers() -> int:
    """Get the number of backend worker processes.

    Returns:
        The number of backend worker processes.

    Raises:
        SystemExit: If unable to connect to Redis.
    """
    if get_config().transport == "polling":
        return 1

    if (redis_client := prerequisites.get_redis_sync()) is None:
        return 1

    from redis.exceptions import RedisError

    try:
        redis_client.ping()
    except RedisError as re:
        logger.error(f"Unable to connect to Redis: {re}")
        raise SystemExit(1) from None
    return (os.cpu_count() or 1) * 2 + 1


def _can_bind_at_port(
    address_family: socket.AddressFamily | int, address: str, port: int
) -> bool:
    """Check if a given address and port are responsive.

    Args:
        address_family: The address family (e.g., socket.AF_INET or socket.AF_INET6).
        address: The address to check.
        port: The port to check.

    Returns:
        Whether the address and port are responsive.
    """
    try:
        with closing(socket.socket(address_family, socket.SOCK_STREAM)) as sock:
            if sys.platform != "win32":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((address, port))
    except (OverflowError, PermissionError, OSError) as e:
        logger.warning(f"Unable to bind to {address}:{port} due to: {e}.")
        return False
    return True


def _can_bind_at_any_port(address_family: socket.AddressFamily | int) -> bool:
    """Check if any port is available for binding.

    Args:
        address_family: The address family (e.g., socket.AF_INET or socket.AF_INET6).

    Returns:
        Whether any port is available for binding.
    """
    try:
        with closing(socket.socket(address_family, socket.SOCK_STREAM)) as sock:
            sock.bind(("", 0))  # Bind to any available port
            return True
    except (OverflowError, PermissionError, OSError) as e:
        logger.debug(f"Unable to bind to any port for {address_family}: {e}")
        return False


def is_process_on_port(
    port: int,
    address_families: Sequence[socket.AddressFamily | int] = (
        socket.AF_INET,
        socket.AF_INET6,
    ),
) -> bool:
    """Check if a process is running on the given port.

    Args:
        port: The port.
        address_families: The address families to check (default: IPv4 and IPv6).

    Returns:
        Whether a process is running on the given port.
    """
    return any(not _can_bind_at_port(family, "", port) for family in address_families)


MAXIMUM_PORT = 2**16 - 1


def handle_port(service_name: str, port: int, auto_increment: bool) -> int:
    """Change port if the specified port is in use and is not explicitly specified as a CLI arg or config arg.
    Otherwise tell the user the port is in use and exit the app.

    Args:
        service_name: The frontend or backend.
        port: The provided port.
        auto_increment: Whether to automatically increment the port.

    Returns:
        The port to run the service on.

    Raises:
        SystemExit:when the port is in use.
    """
    logger.debug(f"Checking if {service_name.capitalize()} port: {port} is in use.")

    families = [
        address_family
        for address_family in (socket.AF_INET, socket.AF_INET6)
        if _can_bind_at_any_port(address_family)
    ]

    if not families:
        logger.error(
            f"Unable to bind to any port for {service_name}. "
            "Please check your network configuration."
        )
        raise SystemExit(1)

    logger.debug(
        f"Checking if {service_name.capitalize()} port: {port} is in use for families: {families}."
    )

    if not is_process_on_port(port, families):
        logger.debug(f"{service_name.capitalize()} port: {port} is not in use.")
        return port

    if auto_increment:
        for new_port in range(port + 1, MAXIMUM_PORT + 1):
            if not is_process_on_port(new_port, families):
                logger.info(
                    f"The {service_name} will run on port [bold underline]{new_port}[/bold underline].",
                    extra={"rich": True},
                )
                return new_port
            logger.debug(
                f"{service_name.capitalize()} port: {new_port} is already in use."
            )

        # If we reach here, it means we couldn't find an available port.
        logger.error(f"Unable to find an available port for {service_name}")
    else:
        logger.error(f"{service_name.capitalize()} port: {port} is already in use.")

    raise SystemExit(1)


@overload
def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: Literal[False] = False,
    show_logs: bool = False,
    run_managed: bool = False,
    **kwargs,
) -> subprocess.Popen[str]: ...


@overload
def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: Literal[True],
    show_logs: bool = False,
    run_managed: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess[str]: ...


def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: bool = False,
    show_logs: bool = False,
    run_managed: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
    """Wrapper over subprocess.Popen to unify the launch of child processes.

    Args:
        args: A string, or a sequence of program arguments.
        run: Whether to run the process to completion.
        show_logs: Whether to show the logs of the process.
        run_managed: Whether the child belongs to the enclosing
            run_concurrently_context (if any) and must be terminated when that
            run unwinds. Children that do not opt in are never tracked.
        **kwargs: Kwargs to override default wrap values to pass to subprocess.Popen as arguments.

    Returns:
        Execute a child program in a new process.

    Raises:
        SystemExit: When attempting to run a command with a None value.
    """
    # Check for invalid command first.
    non_empty_args = list(filter(None, args)) if isinstance(args, list) else [args]
    if isinstance(args, list) and len(non_empty_args) != len(args):
        logger.error(f"Invalid command: {args}")
        raise SystemExit(1)

    path_env: str = os.environ.get("PATH", "")

    # Add node_bin_path to the PATH environment variable.
    if not environment.REFLEX_BACKEND_ONLY.get():
        node_bin_path = path_ops.get_node_bin_path()
        if node_bin_path:
            path_env = os.pathsep.join([str(node_bin_path), path_env])

    env: dict[str, str] = {
        **os.environ,
        "PATH": path_env,
        **kwargs.pop("env", {}),
    }

    kwargs = {
        "env": env,
        "stderr": None if show_logs else subprocess.STDOUT,
        "stdout": None if show_logs else subprocess.PIPE,
        "universal_newlines": True,
        "encoding": "UTF-8",
        "errors": "replace",  # Avoid UnicodeDecodeError in unknown command output
        **kwargs,
    }
    logger.debug(f"Running command: {non_empty_args}")

    if run:
        return subprocess.run(non_empty_args, **kwargs)

    process = subprocess.Popen(non_empty_args, **kwargs)
    if run_managed:
        registry = getattr(_active_registry, "registry", None)
        if registry is not None:
            registry.register(process)
    return process


# Thread-local binding from a run_concurrently_context worker thread to that
# context's child registry. Threads outside such a context have no registry,
# so their new_process children are never tracked - or terminated - here.
_active_registry = threading.local()


def _own_process_group(process: subprocess.Popen) -> int | None:
    """Get the process group a child leads, when it was started detached.

    Args:
        process: The child process.

    Returns:
        The process group ID when the child is a group leader, else None.
    """
    if sys.platform == "win32":
        return None
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return None
    return pgid if pgid == process.pid else None


def _process_group_exists(pgid: int) -> bool:
    """Check whether a process group still has members.

    Args:
        pgid: The process group ID.

    Returns:
        True while any member of the group is still around.
    """
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _JobObjectBasicLimitInformation(ctypes.Structure):
    """Win32 JOBOBJECT_BASIC_LIMIT_INFORMATION struct."""

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _IoCounters(ctypes.Structure):
    """Win32 IO_COUNTERS struct."""

    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    """Win32 JOBOBJECT_EXTENDED_LIMIT_INFORMATION."""

    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _win32_kernel32():
    """Return kernel32 with the job-object signatures set, or None off Windows.

    Returns:
        The configured kernel32 module, or None when WinDLL is unavailable.
    """
    windll = getattr(ctypes, "WinDLL", None)
    if windll is None:
        return None
    kernel32 = windll("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel32


def _create_kill_job(process: subprocess.Popen) -> int | None:
    """Assign a Windows child to a new job object that kills on close.

    Job membership is established at spawn time, so it outlives the child
    itself: once assigned, every descendant the child spawns joins the job,
    and terminating the job kills them even when the root already exited -
    the case a psutil tree walk cannot recover. Any setup failure closes the
    job handle and returns None, and the caller falls back to the psutil
    sweep.

    Args:
        process: The child process to own.

    Returns:
        The job handle, or None off Windows or when setup failed.
    """
    if sys.platform != "win32":
        return None
    kernel32 = _win32_kernel32()
    if kernel32 is None:
        return None
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _JobObjectExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        return None
    # Popen keeps the Windows process handle on a private attribute.
    process_handle = int(getattr(process, "_handle", 0) or 0)
    if not process_handle or not kernel32.AssignProcessToJobObject(job, process_handle):
        kernel32.CloseHandle(job)
        return None
    return int(job)


def _terminate_job(job: int) -> None:
    """Terminate every process in a job and close the job handle.

    Args:
        job: The job handle from _create_kill_job.
    """
    kernel32 = _win32_kernel32()
    if kernel32 is None:
        return
    kernel32.TerminateJobObject(job, 1)
    kernel32.CloseHandle(job)


def _terminate_process_tree_windows(process: subprocess.Popen, timeout: float) -> None:
    """Terminate a Windows child tree, including descendants spawned mid-teardown.

    Retains psutil handles so a pid cannot be reused under us while we wait,
    re-enumerates descendants after the terminate pass to catch children a
    dying parent just spawned, and force-kills whatever ignores termination.
    Processes that deny access survive (nothing more can be done without
    elevation); their AccessDenied is contained per process so one stubborn
    or protected descendant neither aborts the sweep nor masks the fate of
    the others.

    This is the fallback sweep for descendants spawned before the child's
    kill-on-close job assignment landed (or when no job could be created).
    Tree ownership after the root exits comes from the job object: psutil
    offers no tree lookup without the root. POSIX teardown has no such gap
    because the process group is signaled directly.

    Args:
        process: The root child process.
        timeout: Seconds to wait for graceful exits before killing.
    """
    import psutil

    try:
        root = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return

    handles: dict[int, psutil.Process] = {}

    def collect() -> list[psutil.Process]:
        """Refresh the retained handle set with the current tree.

        Returns:
            Handles for the root and every descendant currently visible.
        """
        try:
            current = [root, *root.children(recursive=True)]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            current = [root]
        for proc in current:
            handles.setdefault(proc.pid, proc)
        return list(handles.values())

    for proc in collect():
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            proc.terminate()
    _gone, alive = psutil.wait_procs(collect(), timeout=timeout)
    # Descendants spawned during the terminate pass join the kill sweep.
    for proc in collect():
        if proc in alive or proc.is_running():
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                proc.kill()
    psutil.wait_procs(list(handles.values()), timeout=1)


def _terminate_process_tree(process: subprocess.Popen, pgid: int | None) -> None:
    """SIGTERM a child, signaling its whole process group when it leads one.

    A detached child (e.g. the frontend dev server) takes its descendants down
    with it via the group signal - and the group is signaled whenever it still
    has members, even if the leader itself already exited, since its
    descendants keep the group alive. A non-detached child is terminated
    directly.

    Args:
        process: The child process.
        pgid: The process group captured at registration, if the child led one.
    """
    if pgid is not None:
        if _process_group_exists(pgid):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pgid, signal.SIGTERM)
        return
    if process.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        process.terminate()


def _drain_process_tree(
    process: subprocess.Popen,
    pgid: int | None,
    timeout: float,
    job: int | None = None,
) -> None:
    """Terminate a child tree, then wait and force-kill survivors.

    Args:
        process: The child process.
        pgid: The process group captured at registration, if the child led one.
        timeout: Seconds to wait for graceful exits before killing.
        job: The kill-on-close job owning the child's tree, if assigned.
    """
    if sys.platform == "win32":
        # Sweep first: descendants spawned before the job assignment landed
        # are only discoverable while the root is alive, and the job kill
        # below takes the root down. The job then kills everything that
        # joined it, including after a root exit.
        _terminate_process_tree_windows(process, timeout)
        if job is not None:
            _terminate_job(job)
        return
    _terminate_process_tree(process, pgid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        child_done = process.poll() is not None
        group_done = pgid is None or not _process_group_exists(pgid)
        if child_done and group_done:
            break
        time.sleep(0.05)
    if process.poll() is None or (pgid is not None and _process_group_exists(pgid)):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            if pgid is not None:
                os.killpg(pgid, signal.SIGKILL)
            else:
                process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1)


class _RunChildRegistry:
    """Run-managed children spawned by the tasks of one run_concurrently_context.

    A child is tracked only when its new_process caller opts in with
    run_managed=True, so unrelated or one-shot children in the same threads
    are never signaled.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._lock = threading.Lock()
        # process -> process group captured at registration (None when the
        # child shares our group). Capturing while the child's identity is
        # certain avoids re-resolving a possibly-reused pid at teardown.
        self._processes: dict[subprocess.Popen, int | None] = {}
        # Windows kill-on-close job handles keyed by child: ownership
        # established at spawn time, valid even after the child exits.
        self._jobs: dict[subprocess.Popen, int] = {}
        self._terminating = False

    def register(self, process: subprocess.Popen) -> None:
        """Track a child, draining it at once if shutdown already began.

        Args:
            process: The child process to track.
        """
        pgid = _own_process_group(process)
        job = _create_kill_job(process)
        with self._lock:
            if not self._terminating:
                self._processes[process] = pgid
                if job is not None:
                    self._jobs[process] = job
                return
        # The context is already unwinding: a late child must not outlive it,
        # even if it ignores the first terminate.
        _drain_process_tree(process, pgid, timeout=5.0, job=job)

    def terminate_all(self, timeout: float = 5.0) -> None:
        """Terminate every tracked child still running.

        Args:
            timeout: Seconds to wait per child for graceful exits before killing.
        """
        with self._lock:
            self._terminating = True
            entries = list(self._processes.items())
        for process, pgid in entries:
            # Drain a dead leader too when its detached group still has
            # members (its descendants outlived it) or when a job still owns
            # its tree: both stay valid after the leader exits. The job is
            # popped so a repeated terminate_all never closes it twice.
            job = self._jobs.pop(process, None)
            if (
                process.poll() is None
                or job is not None
                or (pgid is not None and _process_group_exists(pgid))
            ):
                _drain_process_tree(process, pgid, timeout, job=job)


def _interrupt_main_thread():
    """Deliver a SIGINT to the main thread to break it out of a blocking call.

    A real signal is required on POSIX so the main thread's blocking C call
    (e.g. a lock wait or a server loop) returns with EINTR and runs the SIGINT
    handler; `interrupt_main` alone only sets a pending flag there. On Windows
    `interrupt_main` sets the SIGINT event that blocking waits monitor.
    """
    if sys.platform == "win32":
        interrupt_main()
    else:
        main_ident = threading.main_thread().ident
        if main_ident is not None:
            signal.pthread_kill(main_ident, signal.SIGINT)


@contextlib.contextmanager
def run_concurrently_context(
    *fns: Callable[..., Any] | tuple[Callable[..., Any], ...],
    interrupt_on_failure: bool = True,
) -> Generator[list[futures.Future], None, None]:
    """Run functions concurrently in a thread pool.

    If a function fails while the with-body is still executing, the main
    thread is interrupted so the failure propagates promptly instead of being
    swallowed while the body blocks (e.g. a fatal frontend preflight error
    raising SystemExit while the backend serves on the main thread).

    When the with-body unwinds - normally, on KeyboardInterrupt, or on
    failure - child processes the tasks launched with new_process(...,
    run_managed=True) are terminated: the run is over, and a surviving child
    (e.g. the frontend dev server) would otherwise block the exit waiting on
    its output. Children not opted in are never touched.

    Args:
        *fns: The functions to run.
        interrupt_on_failure: Interrupt the main thread with SIGINT when a
            task fails during the body. Disable when the body already blocks
            on a task's result() (which propagates task failures itself) and
            the caller installs its own SIGINT handling, so the internal
            wake-up cannot be mistaken for a real interrupt.

    Yields:
        The futures for the functions.
    """
    # If no functions are provided, yield an empty list and return.
    if not fns:
        yield []
        return

    # Convert the functions to tuples.
    fns = tuple(fn if isinstance(fn, tuple) else (fn,) for fn in fns)

    in_body = True
    interrupt_lock = threading.Lock()
    interrupt_sent = False

    def wake_main_thread(task: futures.Future):
        """Interrupt the main thread once when a task fails during the body.

        Args:
            task: The completed future to inspect.
        """
        nonlocal interrupt_sent
        if task.cancelled() or task.exception() is None:
            return
        if threading.current_thread() is threading.main_thread():
            # Invoked inline on an already-failed task; the main thread is not
            # blocked, so the pre-yield failure check below surfaces the error.
            return
        with interrupt_lock:
            if in_body and not interrupt_sent:
                interrupt_sent = True
                _interrupt_main_thread()

    def raise_first_failure(tasks: list[futures.Future]):
        """Re-raise the first exception found among the completed tasks.

        Args:
            tasks: The futures to inspect.
        """
        for task in tasks:
            if (
                task.done()
                and not task.cancelled()
                and (exc := task.exception()) is not None
            ):
                raise exc from None

    # Run the functions concurrently.
    registry = _RunChildRegistry()
    executor = None

    def _run_in_registry(fn: tuple[Callable[..., Any], ...]) -> Any:
        _active_registry.registry = registry
        try:
            return fn[0](*fn[1:])
        finally:
            _active_registry.registry = None

    try:
        executor = futures.ThreadPoolExecutor(max_workers=len(fns))
        # Submit the tasks.
        tasks = [executor.submit(_run_in_registry, fn) for fn in fns]
        if interrupt_on_failure:
            for task in tasks:
                task.add_done_callback(wake_main_thread)

        try:
            try:
                # Don't enter (and block in) the body if a task has already
                # failed.
                raise_first_failure(tasks)

                # Yield control back to the main thread while tasks are running.
                yield tasks
            finally:
                # Whether the pre-check or the body raised, stop interrupting
                # the main thread: tasks outlive this context (shutdown below
                # does not wait).
                with interrupt_lock:
                    in_body = False
                # Tear down child processes (e.g. the frontend dev server
                # tree) so tasks blocked streaming their output unblock;
                # otherwise this exit hangs forever when a signal (e.g.
                # SIGTERM with no TTY) stops the body but leaves the
                # children running.
                registry.terminate_all()

            # Get the results in the order completed to check any exceptions.
            for task in futures.as_completed(tasks):
                # if task throws something, we let it bubble up immediately
                task.result()
        except KeyboardInterrupt:
            # Raised by wake_main_thread for a failed task, or a real Ctrl+C;
            # surface the task's own error when there is one.
            raise_first_failure(tasks)
            raise
    finally:
        # Tear down run-managed children even when the run was interrupted
        # during task submission, before the body's own finally could run.
        registry.terminate_all()
        # Shutdown the executor
        if executor:
            executor.shutdown(wait=False)


def run_concurrently(*fns: Callable | tuple) -> None:
    """Run functions concurrently in a thread pool.

    Args:
        *fns: The functions to run.
    """
    with run_concurrently_context(*fns):
        pass


def stream_logs(
    message: str,
    process: subprocess.Popen,
    progress: Progress | None = None,
    suppress_errors: bool = False,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
):
    """Stream the logs for a process.

    Args:
        message: The message to display.
        process: The process.
        progress: The ongoing progress bar if one is being used.
        suppress_errors: If True, do not exit if errors are encountered (for fallback).
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.

    Yields:
        The lines of the process output.

    Raises:
        SystemExit: If the process failed.
        ValueError: If the process stdout pipe is closed, but the process remains running.
    """
    from reflex.utils import telemetry

    # Store the tail of the logs.
    logs = collections.deque(maxlen=512)
    with process:
        logger.debug(message, extra={"progress": progress})
        if process.stdout is None:
            return
        try:
            # Resolved once: record allocation per output line is wasted
            # work when debug logging is off.
            debug_enabled = logger.isEnabledFor(logging.DEBUG)
            debug_extra = {"end": "", "progress": progress}
            for line in process.stdout:
                if debug_enabled:
                    logger.debug(line, extra=debug_extra)
                logs.append(line)
                yield line
        except ValueError:
            # The stream we were reading has been closed,
            if process.poll() is None:
                # But if the process is still running that is weird.
                raise
            # If the process exited, break out of the loop for post processing.

    # A child torn down by the user's own interrupt is not a failure.
    if constants.IS_WINDOWS:
        # Windows has no POSIX signal exit codes. os.kill(pid, SIGTERM) calls
        # TerminateProcess with the signal number, so SIGTERM surfaces as a
        # bare 15, and Node reports Ctrl+C as 130 by convention. -15 and 143
        # are ordinary application exit codes here and must stay failures.
        # https://github.com/reflex-dev/reflex/issues/2335
        accepted_return_codes = {0, -2, 15, 130}
    else:
        # On POSIX each signal shows up two ways: negative when Popen saw it
        # directly, 128+N when a shell wrapper such as react router reported
        # it (130 for SIGINT, 143 for SIGTERM).
        interrupt_signals = (int(signal.SIGINT), int(signal.SIGTERM))
        accepted_return_codes = {
            0,
            *(-sig for sig in interrupt_signals),
            *(128 + sig for sig in interrupt_signals),
        }
    if process.returncode not in accepted_return_codes and not suppress_errors:
        logger.error(f"{message} failed with exit code {process.returncode}")
        if "".join(logs).count("CERT_HAS_EXPIRED") > 0:
            bunfig = prerequisites.get_web_dir() / constants.Bun.CONFIG_PATH
            npm_registry_line = next(
                (
                    line
                    for line in bunfig.read_text().splitlines()
                    if line.startswith("registry")
                ),
                None,
            )
            if not npm_registry_line or "=" not in npm_registry_line:
                npm_registry = get_npm_registry()
            else:
                npm_registry = npm_registry_line.split("=")[1].strip()
            logger.error(
                f"Failed to fetch securely from [bold]{escape(npm_registry)}[/bold]. Please check your network connection. "
                "You can try running the command again or changing the registry by setting the "
                "NPM_CONFIG_REGISTRY environment variable. If TLS is the issue, and you know what "
                "you are doing, you can disable it by setting the SSL_NO_VERIFY environment variable.",
                extra={"rich": True},
            )
            raise SystemExit(1)
        for set_of_logs in (*prior_logs, tuple(logs)):
            for line in set_of_logs:
                logger.error(line, extra={"end": ""})
            logger.error("\n\n")
        if analytics_enabled:
            telemetry.send("error", context=message)
        logger.error(
            "Run with [bold]--loglevel debug [/bold] for the full log.",
            extra={"rich": True},
        )
        raise SystemExit(1)


def show_logs(message: str, process: subprocess.Popen):
    """Show the logs for a process.

    Args:
        message: The message to display.
        process: The process.
    """
    for _ in stream_logs(message, process):
        pass


def show_status(
    message: str,
    process: subprocess.Popen,
    suppress_errors: bool = False,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
) -> list[str]:
    """Show the status of a process.

    Args:
        message: The initial message to display.
        process: The process.
        suppress_errors: If True, do not exit if errors are encountered (for fallback).
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.

    Returns:
        The lines of the process output.
    """
    lines = []

    with console.status(message) as status:
        for line in stream_logs(
            message,
            process,
            suppress_errors=suppress_errors,
            analytics_enabled=analytics_enabled,
            prior_logs=prior_logs,
        ):
            status.update(f"{message} {line}")
            lines.append(line)
        return lines


def show_progress(message: str, process: subprocess.Popen, checkpoints: list[str]):
    """Show a progress bar for a process.

    Args:
        message: The message to display.
        process: The process.
        checkpoints: The checkpoints to advance the progress bar.
    """
    # Iterate over the process output.
    with console.progress() as progress:
        task = progress.add_task(f"{message}: ", total=len(checkpoints))
        for line in stream_logs(message, process, progress=progress):
            # Check for special strings and update the progress bar.
            while checkpoints:
                special_string = checkpoints[0]
                if special_string in line:
                    progress.update(task, advance=1)
                    checkpoints.pop(0)
                    continue
                break


def atexit_handler():
    """Display a custom message with the current time when exiting an app."""
    logger.info("Reflex app stopped.")


def get_command_with_loglevel(command: list[str]) -> list[str]:
    """Add the right loglevel flag to the designated command.
     npm uses --loglevel <level>, Bun doesn't use the --loglevel flag and
     runs in debug mode by default.

    Args:
        command:The command to add loglevel flag.

    Returns:
        The updated command list
    """
    npm_path = path_ops.get_npm_path()
    npm_path = str(npm_path) if npm_path else None

    if command[0] == npm_path:
        return [*command, "--loglevel", "silly"]
    return command


def run_process_with_fallbacks(
    args: list[str],
    *,
    show_status_message: str,
    fallbacks: str | Sequence[str] | Sequence[Sequence[str]] | None = None,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
    **kwargs,
):
    """Run subprocess and retry using fallback command if initial command fails.

    Args:
        args: A string, or a sequence of program arguments.
        show_status_message: The status message to be displayed in the console.
        fallbacks: The fallback command to run if the initial command fails.
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.
        **kwargs: Kwargs to pass to new_process function.
    """
    process = new_process(get_command_with_loglevel(args), **kwargs)
    if not fallbacks:
        # No fallback given, or this _is_ the fallback command.
        show_status(
            show_status_message,
            process,
            analytics_enabled=analytics_enabled,
            prior_logs=prior_logs,
        )
    else:
        # Suppress errors for initial command, because we will try to fallback
        logs = show_status(show_status_message, process, suppress_errors=True)

        current_fallback = fallbacks[0] if not isinstance(fallbacks, str) else fallbacks
        next_fallbacks = fallbacks[1:] if not isinstance(fallbacks, str) else None

        if process.returncode != 0:
            # retry with fallback command.
            fallback_with_args = (
                [current_fallback, *args[1:]]
                if isinstance(current_fallback, str)
                else [*current_fallback, *args[1:]]
            )
            logger.warning(
                f"There was an error running command: {args}. Falling back to: {fallback_with_args}."
            )
            run_process_with_fallbacks(
                fallback_with_args,
                show_status_message=show_status_message,
                fallbacks=next_fallbacks,
                analytics_enabled=analytics_enabled,
                prior_logs=(*prior_logs, tuple(logs)),
                **kwargs,
            )


def execute_command_and_return_output(command: str) -> str | None:
    """Execute a command and return the output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    try:
        return subprocess.check_output(command, shell=True).decode().strip()
    except subprocess.SubprocessError as err:
        logger.error(
            f"The command `{command}` failed with error: {err}. This will return None."
        )
        return None
