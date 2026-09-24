"""Memory of a reflex app: compile peaks, idle and per-session footprints, leaks and a 512 MiB box.

The playground (``examples/playground``) runs as a production backend,
``reflex run --env prod --backend-only`` with one granian worker, a fresh one
per sample, as in :mod:`reflex_bench.suites.events`:

- ``memory.compile.peak``: the peak of ``reflex compile`` or ``reflex export
  --env prod`` over the whole process tree, bun, node and vite included.
- ``memory.idle``: the PSS of the idle server tree.
- ``memory.dev.idle``: the same for ``reflex run --env dev``, the backend and
  the vite dev server, once the page answers HTTP (no browser, so vite has
  transformed only what that request needed); the dev server's node, bun and
  esbuild processes are split from the python ones.
- ``memory.per_session``: the bytes each connected session adds, fitted over a
  sweep of held sessions, and what is left after they disconnect and after
  their states expire.
- ``memory.leak``: the bytes each event adds over a long closed-loop run, with
  a gate that fails the sample on a leak.
- ``memory.boot_512mb``: compile, boot and serve under a 512 MiB limit.
- ``memory.boot.min_limit``: the smallest limit that booting and serving pass.

Memory is measured over the whole process tree in untimed samples. Peaks come
from a cgroup v2 scope's ``memory.peak`` where the host can start scopes, else
from sampled PSS; steady state is the summed PSS of the tree
(``smaps_rollup``). ``memory_method`` in the dims names the collector of the
values, so cgroup and PSS numbers never share a series. A limit can only be
enforced by a scope, so the limit ids fail without one.

``memory.compile.peak`` is the scorecard's compile peak, not the peak that a
timed compile sample (``lifecycle.compile``) records as a by-product at
``--loglevel debug``: it runs in its own untimed pass at the default log level
and covers ``export``. Peaks per phase of one command (Python, bun, vite) would
need ``memory.peak`` resets timed by live ``[timing]`` parsing and Linux 6.12,
so there are none.

``memory.per_session`` runs its server with ``REFLEX_REDIS_TOKEN_EXPIRATION``
set to ``expiry_s``, sized from the sweep it is about to run (its settling
and reading time plus an allowance per hold and a margin, about 23 s for 500
sessions) unless the parameter is given: no state manager frees a state when
its session disconnects, so the residual drops only after the expiration, and
only where the manager expires states (reflex 0.9 memory and disk managers,
the 0.8 disk manager; the 0.8 memory manager keeps every state). Its sweep
holds 0, 50, 100, 250 and 500 sessions (and 1000 in ``all``), so the slope's t
interval has at least three degrees of freedom. The tree's PSS is flat within
0.2 MiB from the moment a hold is ready (measured at every level, against
steps of 8 to 47 MiB), so each level settles for a second and is read three
times half a second apart. The echo server's floor is the same sweep, measured
once per instance while the first sample's states expire.
"""

from __future__ import annotations

import contextlib
import dataclasses
import itertools
import math
import shutil
import statistics
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

from packaging.version import Version

from reflex_bench.collectors import SamplingLoop
from reflex_bench.collectors.cgroup import CgroupReading, CgroupScope
from reflex_bench.collectors.pss import METHOD as PSS_METHOD
from reflex_bench.collectors.pss import PssReading, tree_pss
from reflex_bench.collectors.pss import available as pss_available
from reflex_bench.context import Context
from reflex_bench.drivers.app_process import (
    TAIL_LINES,
    AppProcess,
    AppStartError,
    run_cli,
)
from reflex_bench.drivers.echo_server import EchoProcess
from reflex_bench.drivers.events import (
    Endpoint,
    LoadError,
    LoadPlan,
    LoadResult,
    LoadRunner,
    SessionHold,
    hold_sessions,
    raise_fd_limit,
)
from reflex_bench.registry import Metric, SampleResult, benchmark
from reflex_bench.report.format import format_value
from reflex_bench.stats import SlopeFit, linear_slope_ci
from reflex_bench.suites.events import (
    BENCH_STATE,
    MANAGERS,
    SEQ_VAR,
    app_env,
    bench_shape,
    checked_load,
    prepare_app,
)
from reflex_bench.suites.events import server_env as manager_env

MIB = 1024**2
CGROUP = "cgroup"
COMPILE_TIMEOUT_S = 600.0
HOOK_TIMEOUT_S = 300.0
# Each of the start and the first /ping; a normal start takes 1 to 3 s.
START_TIMEOUT_S = 120.0
SETUP_TIMEOUT_S = 900.0
# Reads of a settled tree: the median of three, half a second apart.
READS = 3
READ_INTERVAL_S = 0.5
SETTLE_S = 1.0
# Session counts of a sweep below its largest one.
SWEEP_STEPS = (50, 100, 250, 500)
# Time allowed to each hold when the expiration is sized; a hold of up to 250
# sessions is ready in under a second.
HOLD_S = 2.0
# Slack of the sized expiration over the sweep, and after the expiration
# before the residual is read.
EXPIRY_MARGIN_S = 5.0
# A leak window is sized from a closed-loop probe, with room for a slower run.
PROBE_S = 5.0
DURATION_MARGIN = 1.1
LEAK_SAMPLES = 100
MIN_HALF_SAMPLES = 3
GROWTH_SAMPLES = 5
TIMELINE_POINTS = 500
BOOT_TIMEOUT_S = 60.0
LIMIT_COMPILE_TIMEOUT_S = 240.0
SERVE_SESSIONS = 5
SERVE_S = 5.0
MIN_LIMIT_MB = 64
MAX_LIMIT_MB = 1024
LIMIT_STEP_MB = 32
ALLOCATORS = {
    "default": {},
    "mimalloc": {"PYTHONMALLOC": "mimalloc"},
    "arena2": {"MALLOC_ARENA_MAX": "2"},
}
MIMALLOC_PYTHON = (3, 13)
# Name prefixes of the frontend dev server's processes (vite's node shows as
# node-MainThread); everything else is the backend.
FRONTEND_COMMANDS = ("node", "bun", "esbuild")

_T = TypeVar("_T")


def _bytes(description: str) -> Metric:
    """Declare a memory metric.

    Args:
        description: What it measures.

    Returns:
        A metric in bytes, lower is better.
    """
    return Metric(unit="B", direction="lower", description=description)


class LeakDetected(RuntimeError):  # noqa: N818 - the name states the verdict
    """Memory kept growing with the events: the slope is past the tolerance and does not flatten."""


class MemoryLimitExceeded(RuntimeError):  # noqa: N818 - the name states the verdict
    """A phase failed under its memory limit, or the kernel had to kill or reclaim to keep it."""


class _Started:
    """Stops what one sample started, newest first, from any thread.

    ``conclude`` may run while a timed-out ``sample`` goes on starting things on
    its abandoned thread; whatever it starts after the stop is stopped at once.
    """

    def __init__(self) -> None:
        """Hold nothing yet."""
        self._lock = threading.Lock()
        self._stops: list[Callable[[], object]] = []
        self._stopped = False

    def add(self, stop: Callable[[], object]) -> None:
        """Register how to stop something just created or started.

        Args:
            stop: Stops it; must be safe to call again.

        Raises:
            RuntimeError: When the sample was stopped already; ``stop`` has run.
        """
        with self._lock:
            if not self._stopped:
                self._stops.append(stop)
                return
        stop()
        msg = "the sample was stopped"
        raise RuntimeError(msg)

    def stop(self) -> None:
        """Stop everything registered, newest first; a stop that raises does not skip the others."""
        with self._lock:
            self._stopped = True
            stops, self._stops = self._stops, []
        # An exit stack runs its callbacks last in, first out, each one even
        # after another raised, and raises the last error at the end.
        with contextlib.ExitStack() as stack:
            for stop in stops:
                stack.callback(stop)


def app_dir(ctx: Context) -> Path:
    """Locate the compiled app.

    Args:
        ctx: The benchmark context.

    Returns:
        The app in the cache directory.
    """
    return ctx.cache_dir / "app"


def states_dir(ctx: Context) -> Path:
    """Locate the disk state manager's directory.

    Args:
        ctx: The benchmark context.

    Returns:
        A directory in the cache directory, emptied before every sample.
    """
    return ctx.cache_dir / "states"


def allocator_env(allocator: str, python_version: str) -> dict[str, str]:
    """Choose the environment of an allocator variant.

    Args:
        allocator: ``default``, ``mimalloc`` (``PYTHONMALLOC=mimalloc``) or
            ``arena2`` (``MALLOC_ARENA_MAX=2``).
        python_version: The subject's Python version.

    Returns:
        The variables to set.

    Raises:
        ValueError: On an unknown allocator, or mimalloc before Python 3.13.
    """
    if allocator not in ALLOCATORS:
        msg = f"unknown allocator {allocator!r}; choose from {', '.join(ALLOCATORS)}"
        raise ValueError(msg)
    if (
        allocator == "mimalloc"
        and Version(python_version).release[:2] < MIMALLOC_PYTHON
    ):
        msg = f"PYTHONMALLOC=mimalloc needs Python 3.13 or later; the subject runs Python {python_version}"
        raise ValueError(msg)
    return ALLOCATORS[allocator]


def server_env(ctx: Context, **extra: str) -> dict[str, str]:
    """Build the environment of the playground backend.

    Args:
        ctx: The benchmark context.
        **extra: More variables.

    Returns:
        The app's environment with the state manager, one granian worker, the
        states directory, the allocator variant and ``extra``.
    """
    env = manager_env(app_env(ctx), ctx.params["manager"], states_dir(ctx))
    # "default" is the interpreter's allocator, whatever the harness's shell sets.
    for variables in ALLOCATORS.values():
        for name in variables:
            env.pop(name, None)
    env.update(
        allocator_env(
            ctx.params.get("allocator", "default"), ctx.subject.python_version
        )
    )
    env.update(extra)
    return env


def new_scope() -> CgroupScope | None:
    """Start a scope when the host can.

    Returns:
        A scope without a limit, or ``None`` where scopes are unavailable.
    """
    return CgroupScope() if CgroupScope.available() is None else None


def require_pss() -> None:
    """Make sure the PSS of processes can be read.

    Raises:
        RuntimeError: Where it cannot (not Linux), with the reason.
    """
    if (reason := pss_available()) is not None:
        msg = f"memory benchmarks read PSS, which this host cannot: {reason}"
        raise RuntimeError(msg)


def start_server(
    ctx: Context,
    started: _Started,
    env: dict[str, str],
    *,
    scope: CgroupScope | None,
    dev: bool = False,
) -> AppProcess:
    """Start the playground until it answers HTTP.

    Args:
        ctx: The benchmark context.
        started: Stops the server in ``conclude``.
        env: Its environment.
        scope: The cgroup scope to run it in, if any.
        dev: Start ``reflex run --env dev``, backend and frontend dev server,
            until the page answers HTTP; else the production backend alone,
            until ``/ping`` answers.

    Returns:
        The server.
    """
    app = AppProcess(
        ctx.subject.python,
        app_dir(ctx),
        mode="dev" if dev else "prod",
        backend_only=not dev,
        reflex_version=ctx.subject.reflex_version,
        env=env,
        scope=scope,
        start_timeout=START_TIMEOUT_S,
    )
    started.add(app.stop)
    app.start()
    app.wait_http_ready(timeout=START_TIMEOUT_S)
    return app


def run_owned(
    started: _Started,
    plan: LoadPlan,
    on_window: Callable[[str], None] | None = None,
) -> LoadResult:
    """Run a load that ``conclude`` can stop.

    Args:
        started: Stops the load in ``conclude``.
        plan: The load plan.
        on_window: Called at the edges of the measured window.

    Returns:
        The result.
    """
    runner = LoadRunner(plan)
    started.add(runner.stop)
    return runner.run(on_window)


def settled_pss(pid: int) -> PssReading:
    """Read the PSS of a process tree a few times, a second apart, and take the medians.

    Args:
        pid: The root of the tree.

    Returns:
        The median of each sum; ``uss_bytes`` and ``processes`` are those of the
        read with the median PSS.

    Raises:
        RuntimeError: When the tree is gone.
    """
    readings: list[PssReading] = []
    for index in range(READS):
        if index:
            time.sleep(READ_INTERVAL_S)
        reading = tree_pss(pid)
        if not reading.processes:
            msg = f"the process tree of pid {pid} is gone"
            raise RuntimeError(msg)
        readings.append(reading)
    middle = sorted(readings, key=lambda reading: reading.pss_bytes)[READS // 2]
    return dataclasses.replace(
        middle,
        pss_anon_bytes=int(statistics.median(r.pss_anon_bytes for r in readings)),
        pss_file_bytes=int(statistics.median(r.pss_file_bytes for r in readings)),
    )


def largest_uss(reading: PssReading) -> int:
    """Find the unique memory of the command holding the most: the server's python processes.

    Args:
        reading: The tree's memory.

    Returns:
        The largest USS summed per command name, in bytes.
    """
    return max(reading.uss_bytes.values(), default=0)


def split_uss(uss_bytes: Mapping[str, int]) -> tuple[int, int]:
    """Split the unique memory per command between the backend and the frontend dev server.

    Args:
        uss_bytes: USS summed per command name.

    Returns:
        The backend's and the frontend's USS, in bytes.
    """
    frontend = sum(
        size for name, size in uss_bytes.items() if name.startswith(FRONTEND_COMMANDS)
    )
    return sum(uss_bytes.values()) - frontend, frontend


def cgroup_extra(reading: CgroupReading) -> dict[str, int]:
    """Describe what a scope holds while its server runs.

    Args:
        reading: The scope's counters.

    Returns:
        ``memory.current``, ``anon`` and ``file``, and the peak.
    """
    return {
        "memory_current_bytes": reading.memory_current_bytes,
        "anon_bytes": reading.anon_bytes,
        "file_bytes": reading.file_bytes,
        "memory_peak_bytes": reading.memory_peak_bytes,
    }


def sessions_sweep(largest: int) -> tuple[int, ...]:
    """Choose the session counts of a sweep.

    Args:
        largest: The last count.

    Returns:
        0, the steps 50, 100, 250 and 500 below ``largest``, and ``largest``;
        with half of ``largest`` added when fewer than three counts are left
        to fit.

    Raises:
        ValueError: When ``largest`` is below 2.
    """
    if largest < 2:
        msg = f"a sweep needs at least 2 sessions, got {largest}"
        raise ValueError(msg)
    counts = [0, *(count for count in SWEEP_STEPS if count < largest), largest]
    if len(counts) < 3:
        counts.insert(1, largest // 2)
    return tuple(counts)


def sweep_seconds(levels: int) -> float:
    """Bound the time from a sweep's first hold to its residual read.

    Args:
        levels: The session counts of the sweep above 0.

    Returns:
        The seconds each level and the disconnect settle and read, plus
        ``HOLD_S`` for each level's hold.
    """
    return (levels + 1) * (SETTLE_S + (READS - 1) * READ_INTERVAL_S) + levels * HOLD_S


@dataclasses.dataclass
class _Sweep:
    """What a session sweep measured.

    Attributes:
        levels: The tree's PSS at each session count.
        holds: The holds keeping the sessions.
        first_hold: When the first hold started (``time.monotonic``).
        last_ready: When the last hold's sessions were primed.
    """

    levels: list[dict[str, Any]]
    holds: list[SessionHold]
    first_hold: float
    last_ready: float

    def fit(self) -> SlopeFit:
        """Fit the PSS against the session count.

        Returns:
            The slope in bytes per session, with its interval.
        """
        return linear_slope_ci(
            [level["sessions"] for level in self.levels],
            [level["pss"] for level in self.levels],
        )

    def close(self) -> list[str]:
        """Close every hold.

        Returns:
            Why sessions failed while they were held.
        """
        return [error for hold in self.holds for error in hold.close()]


def sweep_sessions(
    endpoint: Endpoint, pid: int, counts: Sequence[int], started: _Started
) -> _Sweep:
    """Hold more and more sessions against a server and read its settled PSS at each count.

    Args:
        endpoint: Where the sessions connect.
        pid: The root of the server's process tree.
        counts: The session counts, increasing from 0.
        started: Stops the holds in ``conclude``.

    Returns:
        The levels and the holds, still open.
    """
    levels: list[dict[str, Any]] = []
    holds: list[SessionHold] = []
    first_hold = last_ready = time.monotonic()
    held = 0
    for count in counts:
        if count > held:
            if not holds:
                first_hold = time.monotonic()
            hold = hold_sessions(endpoint, count - held)
            started.add(hold.kill)
            holds.append(hold)
            hold.ready()
            last_ready = time.monotonic()
            held = count
        time.sleep(SETTLE_S)
        reading = settled_pss(pid)
        levels.append({
            "sessions": count,
            "pss": reading.pss_bytes,
            "pss_anon": reading.pss_anon_bytes,
            "uss_bytes": reading.uss_bytes,
        })
    return _Sweep(levels, holds, first_hold, last_ready)


def events_at(per_second: Sequence[int], elapsed: Iterable[float]) -> list[float]:
    """Count the events answered by given times since the start of a window.

    Args:
        per_second: Answers per second of the window, as
            :attr:`~reflex_bench.drivers.events.LoadResult.answered_per_second`.
        elapsed: Seconds since the window started.

    Returns:
        The answered events at each time, linear within a second.
    """
    cumulative = list(itertools.accumulate(per_second, initial=0))
    counts = []
    for seconds in elapsed:
        whole = max(0, int(seconds))
        if whole >= len(per_second):
            counts.append(float(cumulative[-1]))
        else:
            counts.append(
                cumulative[whole] + max(0.0, seconds - whole) * per_second[whole]
            )
    return counts


@dataclasses.dataclass(frozen=True)
class LeakFit:
    """The anonymous memory of a server against the events it answered.

    Attributes:
        fit: The slope over the measured window, in bytes per event.
        first: The slope over its first half.
        second: The slope over its second half.
        growth: The median of the last samples minus that of the first ones.
    """

    fit: SlopeFit
    first: SlopeFit
    second: SlopeFit
    growth: float

    def verdict(self, tolerance: float) -> str | None:
        """Decide whether the memory leaks.

        Args:
            tolerance: Bytes per event the upper end of the slope's interval may
                reach.

        Returns:
            Why it leaks: the interval's upper end is past the tolerance *and*
            each half grows on its own (its interval is above zero). Heap
            warm-up flattens out and an allocator step lifts one half only; a
            leak grows through both. Else ``None``.
        """
        if not (
            self.fit.ci_hi > tolerance
            and self.first.ci_lo > 0
            and self.second.ci_lo > 0
        ):
            return None
        return (
            f"memory grows by {self.fit.slope:.1f} B per event (95 % CI"
            f" {self.fit.ci_lo:.1f} to {self.fit.ci_hi:.1f}), over the tolerance of"
            f" {tolerance:g} B, and keeps growing: {self.second.slope:.1f} B per event"
            f" in the second half after {self.first.slope:.1f} in the first;"
            f" growth {format_value(self.growth, 'B')} over {self.fit.n} samples"
        )


def fit_leak(events: Sequence[float], anon: Sequence[float]) -> LeakFit:
    """Fit memory against events over a window, and over each of its halves.

    Args:
        events: The answered events at each sample.
        anon: The anonymous PSS at each sample.

    Returns:
        The fits and the growth.

    Raises:
        ValueError: With fewer than six samples.
    """
    count = len(events)
    if count < 2 * MIN_HALF_SAMPLES:
        msg = f"a leak fit needs at least {2 * MIN_HALF_SAMPLES} samples in the window, got {count}"
        raise ValueError(msg)
    half = count // 2
    edge = min(GROWTH_SAMPLES, half)
    return LeakFit(
        fit=linear_slope_ci(events, anon),
        first=linear_slope_ci(events[:half], anon[:half]),
        second=linear_slope_ci(events[half:], anon[half:]),
        growth=statistics.median(anon[-edge:]) - statistics.median(anon[:edge]),
    )


def thin(points: Sequence[_T], limit: int) -> list[_T]:
    """Keep evenly spaced points, the last one included.

    Args:
        points: The points.
        limit: The most to keep.

    Returns:
        At most ``limit`` points.
    """
    if len(points) <= limit:
        return list(points)
    step = (len(points) - 1) / (limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def complete_load(result: LoadResult) -> LoadResult:
    """Make sure a load measures the server and every event of it was answered.

    Args:
        result: The result.

    Returns:
        The result.

    Raises:
        LoadError: On unanswered events, whose count would be wrong.
    """
    checked_load(result)
    if result.unanswered:
        msg = f"{result.unanswered} of {result.sent} events were not answered, so the event count is wrong"
        raise LoadError(msg)
    return result


def read_or_none(scope: CgroupScope) -> CgroupReading | None:
    """Read a scope that may have ended.

    Args:
        scope: The scope.

    Returns:
        Its counters, or ``None`` when its cgroup is gone or was never found.
    """
    try:
        return scope.read()
    except (OSError, RuntimeError):
        return None


def limit_error(
    phase: str,
    limit_mb: int,
    reading: CgroupReading | None,
    problem: str | None,
    tail: Sequence[str],
) -> MemoryLimitExceeded:
    """Describe a phase that failed under a limit.

    Args:
        phase: ``compile``, ``boot`` or ``serve``.
        limit_mb: The limit, in MiB.
        reading: The scope's counters, read before its tree stopped; ``None``
            when the scope ended with its tree.
        problem: What went wrong besides the counters, if anything.
        tail: The phase's output.

    Returns:
        The error, naming the phase, the counters and the peak, with the
        output's tail.
    """
    what = [problem] if problem else []
    if reading is None:
        what.append("memory.events unreadable: the scope ended with its tree")
        peak = "peak unknown"
    else:
        if reading.oom or reading.oom_kill or not what:
            what.append(f"oom={reading.oom}, oom_kill={reading.oom_kill}")
        peak = f"peak {reading.memory_peak_bytes / MIB:.1f} MiB"
    lines = "\n".join(tail[-TAIL_LINES:])
    return MemoryLimitExceeded(
        f"phase {phase} under MemoryMax={limit_mb}M: {'; '.join(what)}; {peak};"
        f" log tail:\n{lines}"
    )


def limit_check(
    phase: str,
    limit_mb: int,
    reading: CgroupReading | None,
    problem: str | None,
    tail: Sequence[str],
) -> CgroupReading:
    """Pass a phase that ran under a limit.

    Args:
        phase: ``compile``, ``boot`` or ``serve``.
        limit_mb: The limit, in MiB.
        reading: The scope's counters, read before its tree stopped; ``None``
            when the scope ended with its tree.
        problem: What went wrong besides the counters, if anything.
        tail: The phase's output.

    Returns:
        The reading of a phase that passed.

    Raises:
        MemoryLimitExceeded: When the phase failed, the scope could not be read,
            or ``memory.events`` counts an OOM or an OOM kill.
    """
    if (
        reading is not None
        and problem is None
        and not reading.oom
        and not reading.oom_kill
    ):
        return reading
    raise limit_error(phase, limit_mb, reading, problem, tail)


def boot_and_serve(
    ctx: Context, started: _Started, limit_mb: int
) -> tuple[CgroupReading, CgroupReading, LoadResult]:
    """Boot the server under a limit and serve a short closed-loop load, in one scope.

    The scope is read after the boot and after the load, before the server
    stops. The peak is reset between the two where the kernel can (Linux 6.12
    and later; ``peak_reset`` in the serve reading says so); elsewhere the serve
    phase's peak covers the boot too.

    Args:
        ctx: The benchmark context.
        started: Stops the server and the load in ``conclude``.
        limit_mb: ``MemoryMax`` of the scope, in MiB; swap is off.

    Returns:
        The counters after the boot and after the load, and the load.

    Raises:
        MemoryLimitExceeded: When a phase fails under the limit.
    """
    scope = CgroupScope(limit_bytes=limit_mb * MIB, swap_max=0)
    app = AppProcess(
        ctx.subject.python,
        app_dir(ctx),
        mode="prod",
        backend_only=True,
        reflex_version=ctx.subject.reflex_version,
        env=server_env(ctx),
        scope=scope,
        start_timeout=BOOT_TIMEOUT_S,
    )
    started.add(app.stop)
    try:
        try:
            app.start()
        except AppStartError as exc:
            # start() stopped the tree, and the scope ended with it.
            problem = str(exc).partition("\n")[0]
            error = limit_error("boot", limit_mb, None, problem, exc.lines)
            raise error from exc
        try:
            app.wait_http_ready(timeout=BOOT_TIMEOUT_S)
        except AppStartError as exc:
            problem = str(exc).partition("\n")[0]
            error = limit_error(
                "boot", limit_mb, read_or_none(scope), problem, exc.lines
            )
            raise error from exc
        boot = limit_check("boot", limit_mb, read_or_none(scope), None, app.logs())
        scope.reset_peak()
        plan = LoadPlan(
            endpoint=Endpoint(app.backend_url),
            shape=bench_shape("set_seq"),
            sessions=SERVE_SESSIONS,
            mode="closed",
            rate=None,
            warmup_s=0.0,
            duration_s=SERVE_S,
        )
        try:
            load = run_owned(started, plan)
        except LoadError as exc:
            problem = str(exc).partition("\n")[0]
            error = limit_error(
                "serve", limit_mb, read_or_none(scope), problem, app.logs()
            )
            raise error from exc
        serve = read_or_none(scope)
        problem = None
        if not app.is_running():
            problem = "the server exited"
        else:
            try:
                complete_load(load)
            except LoadError as exc:
                problem = str(exc)
        serve = limit_check("serve", limit_mb, serve, problem, app.logs())
    finally:
        app.stop()
    return boot, serve, load


class _Playground:
    """Hooks every memory benchmark shares.

    ``setup_cache`` copies and compiles the playground, ``setup`` names the
    memory method in the dims, ``prepare`` empties the states directory, and
    ``conclude`` stops whatever the sample started, also after a failure or a
    timeout.
    """

    started: _Started | None = None

    def memory_method(self) -> str:
        """Name the collector of the benchmark's values.

        Returns:
            ``pss_sampling``: the tree's summed PSS.
        """
        return PSS_METHOD

    def setup_cache(self, ctx: Context) -> None:
        """Copy the playground into the cache directory and compile it once.

        Args:
            ctx: The benchmark context.
        """
        prepare_app(ctx)

    def setup(self, ctx: Context) -> None:
        """Record the memory method, and an allocator variant, in the dims.

        Args:
            ctx: The benchmark context.
        """
        ctx.dims["memory_method"] = self.memory_method()
        allocator = ctx.params.get("allocator", "default")
        if allocator != "default":
            ctx.dims["allocator"] = allocator

    def prepare(self, ctx: Context) -> None:
        """Empty the states directory, so the disk manager starts clean.

        Args:
            ctx: The benchmark context.
        """
        shutil.rmtree(states_dir(ctx), ignore_errors=True)
        self.started = _Started()

    def conclude(self, ctx: Context) -> None:
        """Stop what the sample started: loads, held sessions and servers.

        Args:
            ctx: The benchmark context.
        """
        started, self.started = self.started, None
        if started is not None:
            started.stop()


@benchmark(
    id="memory.compile.peak",
    suites=("daily",),
    kind="peakmem",
    params={"command": ("compile", "export")},
    metrics={"peak_mem": _bytes("peak memory of the command's whole process tree")},
    warmup=1,
    timeout=COMPILE_TIMEOUT_S + 60,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=6,
)
class CompilePeak(_Playground):
    """Peak memory of `reflex compile` or `reflex export --env prod` on the compiled playground, whole tree."""

    def memory_method(self) -> str:
        """Name the collector of the peak.

        Returns:
            ``cgroup`` where the host starts scopes, else ``pss_sampling``.
        """
        return CGROUP if CgroupScope.available() is None else PSS_METHOD

    def prepare(self, ctx: Context) -> None:
        """Remove the previous export's zips.

        Args:
            ctx: The benchmark context.
        """
        super().prepare(ctx)
        shutil.rmtree(ctx.workdir / "export", ignore_errors=True)
        (ctx.workdir / "export").mkdir()

    def sample(self, ctx: Context) -> SampleResult:
        """Run the command in a scope when the host has one, else sampling PSS.

        Args:
            ctx: The benchmark context.

        Returns:
            The peak, with whether the scope's peak was reset or the USS per
            command at the sampled peak.
        """
        args = ["compile"]
        if ctx.params["command"] == "export":
            args = [
                "export",
                "--env",
                "prod",
                "--zip-dest-dir",
                str(ctx.workdir / "export"),
            ]
        scope = new_scope()
        result = run_cli(
            ctx.subject.python,
            args,
            cwd=app_dir(ctx),
            env=app_env(ctx),
            timeout=COMPILE_TIMEOUT_S,
            scope=scope,
            sample_memory=scope is None,
        ).check()
        extra: dict[str, Any] = {
            "memory_method": result.memory_method,
            "returncode": result.returncode,
        }
        if result.cgroup is not None:
            peak = result.cgroup.memory_peak_bytes
            extra["peak_reset"] = result.cgroup.peak_reset
        else:
            assert result.pss is not None
            peak = result.pss.peak_bytes
            extra.update(
                uss_bytes=result.pss.peak.uss_bytes if result.pss.peak else {},
                pss_samples=result.pss.samples,
            )
        return SampleResult({"peak_mem": peak}, extra=extra)


@benchmark(
    id="memory.idle",
    suites=("smoke", "daily"),
    kind="track",
    params={"manager": MANAGERS},
    hidden_params={"idle_s": 5, "allocator": "default"},
    suite_params={"smoke": {"manager": ["memory"]}},
    metrics={
        "pss": _bytes("summed PSS of the idle server tree"),
        "pss_anon": _bytes("its anonymous part"),
        "pss_file": _bytes("its file-backed part"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=9,
)
class Idle(_Playground):
    """PSS of the idle server tree, the median of three reads a second apart; the production backend, or the dev server with ``mode=dev``."""

    def sample(self, ctx: Context) -> SampleResult:
        """Start the server, let it idle, and read its tree.

        Args:
            ctx: The benchmark context.

        Returns:
            The tree's PSS, with the USS per command, split between the backend
            and the frontend dev server, and, with a scope, the cgroup's view of
            the same server.
        """
        require_pss()
        started = self.started
        assert started is not None
        scope = new_scope()
        dev = ctx.params.get("mode") == "dev"
        app = start_server(ctx, started, server_env(ctx), scope=scope, dev=dev)
        time.sleep(float(ctx.params["idle_s"]))
        reading = settled_pss(app.pid)
        backend, frontend = split_uss(reading.uss_bytes)
        extra: dict[str, Any] = {
            "memory_method": PSS_METHOD,
            "uss_bytes": reading.uss_bytes,
            "backend_uss_bytes": backend,
            "frontend_uss_bytes": frontend,
            "processes": reading.processes,
        }
        if scope is not None:
            extra.update(cgroup_extra(scope.read()))
        return SampleResult(
            {
                "pss": reading.pss_bytes,
                "pss_anon": reading.pss_anon_bytes,
                "pss_file": reading.pss_file_bytes,
            },
            extra=extra,
        )


# The allocator variants of the idle footprint, run with --suite all.
benchmark(
    id="memory.idle.allocator",
    kind="track",
    params={"allocator": ("mimalloc", "arena2")},
    hidden_params={"idle_s": 5, "manager": "memory"},
    metrics={
        "pss": _bytes("summed PSS of the idle server tree"),
        "pss_anon": _bytes("its anonymous part"),
        "pss_file": _bytes("its file-backed part"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=9,
)(Idle)


# The dev server: what `reflex run` holds while a developer works.
benchmark(
    id="memory.dev.idle",
    suites=("daily",),
    kind="track",
    params={"manager": ("memory",)},
    hidden_params={"idle_s": 10, "allocator": "default", "mode": "dev"},
    metrics={
        "pss": _bytes("summed PSS of the idle dev server tree, backend and vite"),
        "pss_anon": _bytes("its anonymous part"),
        "pss_file": _bytes("its file-backed part"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=25,
)(Idle)


@benchmark(
    id="memory.per_session",
    suites=("daily",),
    kind="track",
    params={"manager": MANAGERS, "max_sessions": (1000,)},
    hidden_params={"expiry_s": 0, "allocator": "default"},
    suite_params={"daily": {"max_sessions": [500]}},
    metrics={
        "bytes_per_session": _bytes("slope of the server's PSS over held sessions"),
        "bytes_per_session_ci_hi": _bytes("upper end of the slope's 95 % interval"),
        "residual_after_disconnect": _bytes(
            "PSS over the idle baseline once every session disconnected"
        ),
        "residual_after_expiry": _bytes(
            "PSS over the idle baseline once the sessions' states expired"
        ),
    },
    timeout=600,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=40,
)
class PerSession(_Playground):
    """Bytes per connected session over a sweep of held sessions (0, 50, 100, 250, 500 and 1000), and the residual after disconnect and after expiry."""

    floor: _Sweep | None = None

    def sample(self, ctx: Context) -> SampleResult:
        """Sweep held sessions, disconnect them, wait for their expiry; the echo server's floor meanwhile, once.

        Args:
            ctx: The benchmark context.

        Returns:
            The slope and the residuals, with the levels, the fit and the echo
            server's bytes per session.

        Raises:
            LoadError: When sessions failed while held.
            RuntimeError: When the sweep outlasted the token expiration.
        """
        require_pss()
        started = self.started
        assert started is not None
        counts = sessions_sweep(int(ctx.params["max_sessions"]))
        # 0 sizes the expiration from the sweep: the states must outlive it.
        expiry_s = float(ctx.params["expiry_s"]) or float(
            math.ceil(sweep_seconds(len(counts) - 1) + EXPIRY_MARGIN_S)
        )
        raise_fd_limit(counts[-1])
        scope = new_scope()
        env = server_env(ctx, REFLEX_REDIS_TOKEN_EXPIRATION=f"{expiry_s:g}")
        app = start_server(ctx, started, env, scope=scope)
        sweep = sweep_sessions(Endpoint(app.backend_url), app.pid, counts, started)
        if errors := sweep.close():
            msg = f"{len(errors)} sessions failed while held: {errors[0]}"
            raise LoadError(msg)
        time.sleep(SETTLE_S)
        residual = settled_pss(app.pid)
        if (took := time.monotonic() - sweep.first_hold) >= expiry_s:
            msg = (
                f"the sweep and the disconnect took {took:.0f} s, not less than the token"
                f" expiration of {expiry_s:g} s, so states may have expired before they"
                " were measured; raise --param expiry_s"
            )
            raise RuntimeError(msg)
        expires_at = sweep.last_ready + expiry_s + EXPIRY_MARGIN_S
        # The transport's own cost, while the states expire; it does not
        # depend on the subject, so one sweep serves every sample.
        floor = self.floor
        if floor is None:
            echo = EchoProcess(delta_key=BENCH_STATE, seq_var=SEQ_VAR)
            started.add(echo.stop)
            echo_url = echo.start()
            floor = sweep_sessions(Endpoint(echo_url), echo.pid, counts, started)
            if errors := floor.close():
                msg = f"{len(errors)} sessions failed while held by the echo server: {errors[0]}"
                raise LoadError(msg)
            echo.stop()
            self.floor = floor
        time.sleep(max(0.0, expires_at - time.monotonic()))
        expired = settled_pss(app.pid)
        baseline = sweep.levels[0]["pss"]
        fit, floor_fit = sweep.fit(), floor.fit()
        extra: dict[str, Any] = {
            "memory_method": PSS_METHOD,
            "expiry_s": expiry_s,
            "sweep_s": took,
            "levels": sweep.levels,
            "r2": fit.r2,
            "ci_lo": fit.ci_lo,
            "ci_hi": fit.ci_hi,
            "residual_pss": residual.pss_bytes,
            "expired_pss": expired.pss_bytes,
            "baseline_bytes_per_session": floor_fit.slope,
            "baseline_ci": [floor_fit.ci_lo, floor_fit.ci_hi],
            "baseline_levels": floor.levels,
        }
        if scope is not None:
            extra.update(cgroup_extra(scope.read()))
        return SampleResult(
            {
                "bytes_per_session": fit.slope,
                "bytes_per_session_ci_hi": fit.ci_hi,
                "residual_after_disconnect": residual.pss_bytes - baseline,
                "residual_after_expiry": expired.pss_bytes - baseline,
            },
            extra=extra,
        )


@benchmark(
    id="memory.leak",
    suites=("daily",),
    kind="track",
    params={"manager": MANAGERS, "events": (100_000,)},
    hidden_params={
        "sessions": 10,
        "warmup_events": 5000,
        "event": "set_seq",
        "tolerance_bytes_per_event": 100,
        "allocator": "default",
    },
    suite_params={"daily": {"events": [50_000]}},
    metrics={
        "passed": Metric(
            unit="1",
            direction="higher",
            assume="exact",
            description="1 when the leak gate passes; a failure is the 0",
        ),
        "bytes_per_event_ci_hi": _bytes(
            "upper end of the 95 % interval of the anonymous PSS slope over answered events"
        ),
    },
    timeout=900,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=45,
)
class Leak(_Playground):
    """Anonymous PSS against answered events over a closed-loop run; fails on a slope that does not flatten."""

    def sample(self, ctx: Context) -> SampleResult:
        """Probe the rate, run the load while sampling the tree, fit and judge.

        Args:
            ctx: The benchmark context.

        Returns:
            The gate outcome and the slope's upper end, with the slope, the
            growth, the downsampled timeline and the load.

        Raises:
            LeakDetected: When the memory keeps growing with the events.
            LoadError: When the probe answered nothing.
        """
        require_pss()
        started = self.started
        assert started is not None
        params = ctx.params
        scope = new_scope()
        app = start_server(ctx, started, server_env(ctx), scope=scope)
        shape = bench_shape(params["event"])

        def plan(warmup_s: float, duration_s: float) -> LoadPlan:
            return LoadPlan(
                endpoint=Endpoint(app.backend_url),
                shape=shape,
                sessions=int(params["sessions"]),
                mode="closed",
                rate=None,
                warmup_s=warmup_s,
                duration_s=duration_s,
            )

        rate = complete_load(run_owned(started, plan(1.0, PROBE_S))).answered_rate
        warmup_s = math.ceil(params["warmup_events"] / rate)
        duration_s = math.ceil(params["events"] / rate * DURATION_MARGIN)
        points: list[tuple[float, int, int]] = []

        def read() -> None:
            reading = tree_pss(app.pid)
            if not reading.processes:
                msg = f"the process tree of pid {app.pid} is gone"
                raise RuntimeError(msg)
            points.append((
                time.perf_counter(),
                reading.pss_anon_bytes,
                largest_uss(reading),
            ))

        window: dict[str, float] = {}
        sampler = SamplingLoop(
            read, min(1.0, max(0.1, duration_s / LEAK_SAMPLES)), "memory timeline"
        )
        sampler.start()
        try:
            result = run_owned(
                started,
                plan(warmup_s, duration_s),
                lambda edge: window.__setitem__(edge, time.perf_counter()),
            )
        finally:
            sampler.stop()
        complete_load(result)
        start = window["start"]
        measured = [p for p in points if start <= p[0] <= window["end"]]
        events = events_at(result.answered_per_second, (p[0] - start for p in measured))
        anon = [float(p[1]) for p in measured]
        leak = fit_leak(events, anon)
        if (
            reason := leak.verdict(float(params["tolerance_bytes_per_event"]))
        ) is not None:
            raise LeakDetected(reason)
        extra: dict[str, Any] = {
            "memory_method": PSS_METHOD,
            "sessions": result.sessions,
            "event": params["event"],
            "probe_rate": rate,
            "warmup_s": warmup_s,
            "events_measured": result.answered,
            "samples": len(measured),
            "unanswered": result.unanswered,
            "slope_bytes_per_event": leak.fit.slope,
            "ci_lo": leak.fit.ci_lo,
            "ci_hi": leak.fit.ci_hi,
            "r2": leak.fit.r2,
            "first_half_slope": leak.first.slope,
            "second_half_slope": leak.second.slope,
            "growth_bytes": leak.growth,
            "tolerance_bytes_per_event": params["tolerance_bytes_per_event"],
            "timeline": thin(
                [
                    [round(count), point[1], point[2]]
                    for count, point in zip(events, measured, strict=True)
                ],
                TIMELINE_POINTS,
            ),
            "generator": result.summary(),
        }
        if scope is not None:
            extra.update(cgroup_extra(scope.read()))
        return SampleResult(
            {"passed": 1, "bytes_per_event_ci_hi": leak.fit.ci_hi}, extra=extra
        )


@benchmark(
    id="memory.boot_512mb",
    suites=("daily",),
    kind="peakmem",
    params={"manager": MANAGERS},
    hidden_params={"limit_mb": 512},
    suite_params={"daily": {"manager": ["memory"]}},
    metrics={
        "passed": Metric(
            unit="1",
            direction="higher",
            assume="exact",
            description="1 when compile, boot and serve fit the limit; a failure is the 0",
        ),
        "peak_compile": _bytes("memory.peak of `reflex compile` under the limit"),
        "peak_boot": _bytes("memory.peak of the server until /ping answers"),
        "peak_serve": _bytes("memory.peak of the server through a short load"),
    },
    timeout=600,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=15,
)
class Boot512(_Playground):
    """Compile, boot and serve the playground each under MemoryMax=512M with swap off; any OOM fails the sample."""

    def memory_method(self) -> str:
        """Name the collector: limits need a scope.

        Returns:
            ``cgroup``.
        """
        return CGROUP

    def sample(self, ctx: Context) -> SampleResult:
        """Run the three phases, reading each scope before its tree stops.

        Args:
            ctx: The benchmark context.

        Returns:
            ``passed`` and the peak of each phase.
        """
        started = self.started
        assert started is not None
        limit_mb = int(ctx.params["limit_mb"])
        # Without scopes this raises: a limit cannot be enforced otherwise.
        scope = CgroupScope(limit_bytes=limit_mb * MIB, swap_max=0)
        compiled = run_cli(
            ctx.subject.python,
            ["compile"],
            cwd=app_dir(ctx),
            env=app_env(ctx),
            timeout=LIMIT_COMPILE_TIMEOUT_S,
            scope=scope,
        )
        problem = None
        if compiled.timed_out:
            problem = f"reflex compile timed out after {compiled.timeout_s:g} s"
        elif compiled.returncode:
            problem = f"reflex compile exited with code {compiled.returncode}"
        compile_reading = limit_check(
            "compile", limit_mb, compiled.cgroup, problem, compiled.lines
        )
        boot, serve, load = boot_and_serve(ctx, started, limit_mb)
        phases = {"compile": compile_reading, "boot": boot, "serve": serve}
        return SampleResult(
            {
                "passed": 1,
                **{f"peak_{name}": r.memory_peak_bytes for name, r in phases.items()},
            },
            extra={
                "memory_method": CGROUP,
                "limit_mb": limit_mb,
                "phases": {
                    name: {**cgroup_extra(r), "oom": r.oom, "oom_kill": r.oom_kill}
                    for name, r in phases.items()
                },
                "peak_reset": serve.peak_reset,
                "generator": load.summary(),
            },
        )


@benchmark(
    id="memory.boot.min_limit",
    kind="track",
    params={"manager": ("memory",)},
    metrics={
        "min_limit": _bytes(
            "the smallest MemoryMax, in 32 MiB steps, that boot and serve pass"
        ),
    },
    timeout=600,
    setup_timeout=SETUP_TIMEOUT_S,
    estimate=45,
)
class MinLimit(_Playground):
    """Bisect the smallest MemoryMax (64 to 1024 MiB, 32 MiB steps) that booting and serving the playground pass."""

    def memory_method(self) -> str:
        """Name the collector: limits need a scope.

        Returns:
            ``cgroup``.
        """
        return CGROUP

    def sample(self, ctx: Context) -> SampleResult:
        """Check the largest limit, then bisect below it.

        Args:
            ctx: The benchmark context.

        Returns:
            The smallest passing limit, with every step.

        Raises:
            MemoryLimitExceeded: When even the largest limit fails.
        """
        started = self.started
        assert started is not None
        limits = list(range(MIN_LIMIT_MB, MAX_LIMIT_MB + 1, LIMIT_STEP_MB))
        steps: list[dict[str, Any]] = []

        def passes(index: int) -> bool:
            try:
                _, serve, _ = boot_and_serve(ctx, started, limits[index])
            except MemoryLimitExceeded as exc:
                steps.append({
                    "limit_mb": limits[index],
                    "passed": False,
                    "error": str(exc),
                })
                return False
            steps.append({
                "limit_mb": limits[index],
                "passed": True,
                "peak": serve.memory_peak_bytes,
            })
            return True

        if not passes(len(limits) - 1):
            msg = (
                f"boot and serve fail even under {limits[-1]} MiB: {steps[-1]['error']}"
            )
            raise MemoryLimitExceeded(msg)
        failing, passing = -1, len(limits) - 1
        while passing - failing > 1:
            middle = (failing + passing) // 2
            if passes(middle):
                passing = middle
            else:
                failing = middle
        return SampleResult(
            {"min_limit": limits[passing] * MIB},
            extra={"memory_method": CGROUP, "steps": steps},
        )
