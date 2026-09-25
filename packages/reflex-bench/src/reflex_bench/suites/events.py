"""Event throughput and latency: how many events a reflex app answers, and how fast.

Each benchmark instance starts the playground (``examples/playground``) once, as
a production backend (``reflex run --env prod --backend-only`` with one granian
worker), and each sample drives it for a few seconds with the socket.io
generator of :mod:`reflex_bench.drivers.events`:

- ``events.<shape>.capacity``: closed loop, the most events per second.
- ``events.<shape>.latency``: open loop at a fixed rate (half the capacity a
  closed-loop probe measures, unless ``--param rate=`` fixes it), the response
  times a user sees.
- ``events.simple.knee``: open-loop steps from 10 % to 110 % of the probed
  capacity; the knee is the highest rate the backend still keeps up with.
- ``events.sessions.at_1hz``: many sessions sending one event per second.
- ``events.shared_contention.*``: capacity and latency with every session
  linked to one ``rx.SharedState`` token, so each event is fanned out to all
  the others.
- ``events.shared_fanout.broadcast``: one of the linked sessions sends, and an
  event is answered once every linked session received its delta.

CI minutes are scarce, so ``smoke`` runs two points only: the simple shape
with the memory manager and 10 sessions, its latency at 500 events per second.
``daily`` adds the shared state at the same point and two fan-out sizes.
Everything else runs with ``--suite all`` or by name.

The shapes are the playground's ``BenchState.set_seq*`` handlers, and
``BoardState.set_seq_shared`` for the shared state. The state manager is a
parameter; ``redis`` joins ``memory`` and ``disk`` when ``REFLEX_REDIS_URL`` is
set in the harness's environment. On Linux with four CPUs or more, the server
runs on the lower half of the physical cores (not CPU 0) and the generator on
the upper half, so no core is shared through SMT.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import threading
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple

import psutil

from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.context import Context, git
from reflex_bench.drivers.app_process import AppProcess, cache_env, run_cli
from reflex_bench.drivers.echo_server import EchoProcess
from reflex_bench.drivers.events import (
    Endpoint,
    EventShape,
    GeneratorSaturated,
    LinkEvent,
    LoadError,
    LoadPlan,
    LoadResult,
    LoadRunner,
    Mode,
    raise_fd_limit,
    seq_payload,
)
from reflex_bench.fixtures import describe_playground
from reflex_bench.registry import Metric, SampleResult, benchmark

PLAYGROUND = Path(__file__).resolve().parents[5] / "examples" / "playground"
# Prints the full names of the playground's states, which depend on the subject:
# a shared state sits under an internal parent state.
STATES_SCRIPT = (
    "from playground.state import BenchState, BoardState;"
    " print(BenchState.get_full_name(), BoardState.get_full_name())"
)
STATES_TIMEOUT_S = 60.0
SEQ_VAR = "last_seq_rx_state_"
CLIENT_VAR = "last_client_rx_state_"
SESSIONS = (1, 10, 50, 200)
AT_1HZ_SESSIONS = (50, 200, 1000)
# Sessions linked to one board in the fan-out, the sender included.
LINKED = (1, 5, 25, 100)
# The one point of the grid smoke and daily run, and its latency's offered rate.
CHEAP = {"manager": ("memory",), "sessions": (10,)}
CHEAP_LATENCY = {**CHEAP, "rate": (500,)}
# Daily's shared state points: the contention's rate follows its own capacity.
CHEAP_CONTENTION_LATENCY = {**CHEAP, "rate": ("auto",)}
CHEAP_FANOUT = {"manager": ("memory",), "linked": (5, 25)}
KNEE_SHARES = (0.10, 0.50, 0.70, 0.80, 0.90, 0.95, 1.00, 1.10)
# A step keeps up when it answers 99 % of the offered rate, leaves nothing
# unanswered and keeps its p99 within 3x the p99 of the 10 % step.
KNEE_ANSWERED_SHARE = 0.99
KNEE_P99_FACTOR = 3.0
LATENCY_SHARE = 0.5
UNDERPOWERED_P99 = 10_000
CALIBRATION_SESSIONS = 10
# The calibration offers a multiple of the highest fixed rate the suite uses:
# at_1hz with 1000 sessions, or the latency point of smoke and daily. The rates
# relative to a probed capacity (the knee, rate=auto) are covered by the
# self-check of each load.
CALIBRATION_FACTOR = 3
CALIBRATION_RATE = CALIBRATION_FACTOR * float(
    max(*AT_1HZ_SESSIONS, *CHEAP_LATENCY["rate"])
)
COMPILE_TIMEOUT_S = 600.0
HOOK_TIMEOUT_S = 600.0
SYSFS_CPU = Path("/sys/devices/system/cpu")


class Window(NamedTuple):
    """How long one load runs.

    Attributes:
        warmup_s: Seconds of load before the measured window.
        duration_s: The measured window.
    """

    warmup_s: float
    duration_s: float


# Seconds, not minutes: at a few thousand events per second a window still
# answers thousands of events, and CI minutes are scarce.
CAPACITY_WINDOW = Window(1.0, 3.0)
LATENCY_WINDOW = Window(1.0, 5.0)
FANOUT_WINDOW = Window(1.0, 3.0)
PROBE_WINDOW = Window(1.0, 2.0)
KNEE_WINDOW = Window(1.0, 4.0)
AT_1HZ_WINDOW = Window(3.0, 10.0)
CALIBRATION_CLOSED_WINDOW = Window(1.0, 3.0)
CALIBRATION_STEP_WINDOW = Window(1.0, 2.0)


class PlaygroundStates(NamedTuple):
    """The full names of the playground's states in one subject.

    Attributes:
        bench: ``BenchState``.
        board: ``BoardState``, the shared state.
    """

    bench: str
    board: str


# The echo server echoes whatever state an event names.
ECHO_STATES = PlaygroundStates(bench="bench_state", board="board_state")


def playground_states(ctx: Context) -> PlaygroundStates:
    """Ask the subject's interpreter for the full names of the playground's states.

    Args:
        ctx: The benchmark context, after ``prepare_app``.

    Returns:
        The names.

    Raises:
        RuntimeError: When the subject cannot import the playground's states.
    """
    result = subprocess.run(
        [str(ctx.subject.python), "-c", STATES_SCRIPT],
        cwd=ctx.cache_dir / "app",
        env=app_env(ctx),
        capture_output=True,
        text=True,
        timeout=STATES_TIMEOUT_S,
        check=False,
    )
    if result.returncode:
        problem = (result.stderr.strip().splitlines() or ["no output"])[-1]
        msg = f"the subject cannot import the playground's states: {problem}"
        raise RuntimeError(msg)
    bench, board = result.stdout.split()[-2:]
    return PlaygroundStates(bench=bench, board=board)


def bench_shape(
    states: PlaygroundStates, handler: str, *, ordered: bool = True
) -> EventShape:
    """Describe a ``BenchState`` handler of the playground.

    Args:
        states: The subject's state names.
        handler: The handler's name.
        ordered: Whether a session's events are answered in the order sent.

    Returns:
        The event shape: payload ``{"seq": n}``, echoed as ``last_seq``.
    """
    return EventShape(
        name=f"{states.bench}.{handler}",
        payload=seq_payload,
        delta_key=states.bench,
        seq_var=SEQ_VAR,
        ordered=ordered,
    )


def board_shape(
    states: PlaygroundStates, *, client_var: str | None = None
) -> EventShape:
    """Describe ``BoardState.set_seq_shared``, whose delta reaches every linked session.

    Args:
        states: The subject's state names.
        client_var: The var echoing the sender's index, when only the session's
            own events count as answered.

    Returns:
        The event shape: payload ``{"seq": n}``, echoed as ``last_seq``.
    """
    return EventShape(
        name=f"{states.board}.set_seq_shared",
        payload=seq_payload,
        delta_key=states.board,
        seq_var=SEQ_VAR,
        client_var=client_var,
    )


ShapeOf = Callable[[PlaygroundStates], EventShape]

# The wire suite measures one unlinked session per shape, so the shared shapes
# are kept apart.
SHAPES: dict[str, ShapeOf] = {
    "simple": partial(bench_shape, handler="set_seq"),
    "complex": partial(bench_shape, handler="set_seq_complex"),
    "cross": partial(bench_shape, handler="set_seq_cross"),
    # Background tasks take the state lock in whatever order they get to it.
    "background": partial(bench_shape, handler="set_seq_background", ordered=False),
}
SHARED_SHAPES: dict[str, ShapeOf] = {
    # One session sends; its event is answered once every linked session has the delta.
    "shared_fanout": board_shape,
    # Every session sends and receives the others' deltas; only its own echo answers.
    "shared_contention": partial(board_shape, client_var=CLIENT_VAR),
}


def join_link(board: str) -> LinkEvent:
    """Link a load's sessions to a fresh board, so no board keeps an earlier load's clients.

    Args:
        board: The full name of ``BoardState``.

    Returns:
        The ``BoardState.join`` event with a token reflex accepts (no underscore).
    """
    return LinkEvent(
        name=f"{board}.join",
        payload={"token": uuid.uuid4().hex},
        delta_key=board,
    )


def managers(environ: Mapping[str, str]) -> tuple[str, ...]:
    """Choose the state managers to measure.

    Args:
        environ: The harness's environment.

    Returns:
        ``memory`` and ``disk``, and ``redis`` when ``REFLEX_REDIS_URL`` is set.
    """
    return ("memory", "disk", *(("redis",) if environ.get("REFLEX_REDIS_URL") else ()))


MANAGERS = managers(os.environ)

THROUGHPUT = Metric(
    unit="ev/s", direction="higher", description="answered events per second"
)
CPU_PER_EVENT = Metric(
    unit="s",
    direction="lower",
    description="server CPU per answered event, over the measured window",
)
UNANSWERED = Metric(
    unit="1",
    direction="lower",
    assume="exact",
    description="events without an answer by the end of the drain",
)


def _latency(what: str) -> Metric:
    """Declare a response time metric.

    Args:
        what: Which percentile.

    Returns:
        The metric.
    """
    return Metric(
        unit="s",
        direction="lower",
        description=f"{what} of answer time minus planned send time",
    )


def server_env(
    env: Mapping[str, str], manager: str, states_dir: Path
) -> dict[str, str]:
    """Build the environment of the playground backend.

    Args:
        env: The benchmark's environment, ``ctx.env``.
        manager: The state manager: ``memory``, ``disk`` or ``redis``.
        states_dir: Where the disk state manager writes.

    Returns:
        The environment: the manager, one granian worker (reflex starts more
        with redis), and ``REFLEX_REDIS_URL`` only for redis, since reflex uses
        redis whenever a URL is configured.
    """
    result = {
        **env,
        **cache_env(states_dir=states_dir),
        "REFLEX_STATE_MANAGER_MODE": manager,
        "GRANIAN_WORKERS": "1",
    }
    if manager != "redis":
        result.pop("REFLEX_REDIS_URL", None)
    return result


def cpu_cores(allowed: Iterable[int], sysfs: Path) -> list[list[int]] | None:
    """Group CPUs by physical core, from the kernel's topology.

    Args:
        allowed: The CPUs the harness may use.
        sysfs: The ``cpu`` directory of sysfs.

    Returns:
        The allowed CPUs of each core, by lowest CPU, or ``None`` when the
        topology of any CPU cannot be read.
    """
    wanted = set(allowed)
    cores: dict[int, list[int]] = {}
    for cpu in sorted(wanted):
        try:
            listing = (
                sysfs / f"cpu{cpu}" / "topology" / "thread_siblings_list"
            ).read_text()
        except OSError:
            return None
        siblings: list[int] = []
        for part in listing.strip().split(","):
            first, _, last = part.partition("-")
            siblings.extend(range(int(first), int(last or first) + 1))
        cores.setdefault(min(siblings), []).append(cpu)
    return list(cores.values())


def split_cpus(
    allowed: Sequence[int], cores: Sequence[Sequence[int]] | None
) -> dict[str, list[int]] | None:
    """Split CPUs between the server and the generator, whole cores to each side.

    Args:
        allowed: The CPUs the harness may use.
        cores: The allowed CPUs of each physical core, or ``None`` to treat
            every CPU as its own core.

    Returns:
        ``{"server": the lower half of the cores minus CPU 0, "generator":
        the upper half}``, or ``None`` with fewer than four CPUs or when CPU 0
        is the whole lower half.
    """
    cpus = sorted(allowed)
    if len(cpus) < 4:
        return None
    if cores is None:
        cores = [[cpu] for cpu in cpus]
    half = len(cores) // 2
    server = sorted(cpu for core in cores[:half] for cpu in core if cpu != 0)
    if not server:
        return None
    return {
        "server": server,
        "generator": sorted(cpu for core in cores[half:] for cpu in core),
    }


def pinning() -> dict[str, list[int]] | None:
    """Split this machine's CPUs between the server and the generator.

    Returns:
        The split, or ``None`` where CPU affinity is not available (not Linux).
    """
    if not hasattr(os, "sched_getaffinity"):
        return None
    allowed = sorted(os.sched_getaffinity(0))
    return split_cpus(allowed, cpu_cores(allowed, SYSFS_CPU))


def generator_processes(sessions: int, cpus: Sequence[int] | None) -> int:
    """Choose how many generator processes carry the sessions.

    Args:
        sessions: The number of sessions.
        cpus: The generator's CPUs, or ``None`` without pinning.

    Returns:
        1 up to 10 sessions, else one per generator CPU (half the machine
        without pinning), at most 4.
    """
    if sessions <= 10:
        return 1
    available = len(cpus) if cpus else (os.cpu_count() or 2) // 2
    return max(1, min(4, available, sessions))


def find_knee(steps: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    """Find the highest offered rate the server keeps up with.

    Args:
        steps: The open-loop steps by increasing rate, the first at low load;
            each with ``offered`` and ``achieved`` (answered) rates, ``p99``
            response time and ``unanswered`` count.

    Returns:
        The knee (``0`` when no step keeps up) and the low-load p99.

    Raises:
        ValueError: When the low-load step answered nothing.
    """
    low_load_p99 = steps[0]["p99"]
    if low_load_p99 is None:
        msg = "the low-load step answered no event"
        raise ValueError(msg)
    keeping_up = [
        step["offered"]
        for step in steps
        if step["achieved"] >= KNEE_ANSWERED_SHARE * step["offered"]
        and step["unanswered"] == 0
        and step["p99"] is not None
        and step["p99"] <= KNEE_P99_FACTOR * low_load_p99
    ]
    return max(keeping_up, default=0.0), low_load_p99


def cpu_per_event(cpu_s: float, result: LoadResult) -> float:
    """Divide the server's CPU time by the events it answered in the same window.

    Answers that arrive in the drain after the window are left out, as the CPU
    time does not cover the drain.

    Args:
        cpu_s: CPU seconds of the server tree in the measured window.
        result: The load result, whose answers per second of the window count.

    Returns:
        Seconds of CPU per event.

    Raises:
        ValueError: Without answered events, or when the CPU time went back.
    """
    answered = sum(result.answered_per_second)
    if answered <= 0:
        msg = "no answered event to divide the CPU time by"
        raise ValueError(msg)
    if cpu_s < 0:
        msg = (
            f"the server's CPU time went back by {-cpu_s:.3f} s: a process of its"
            " tree was reaped outside it"
        )
        raise ValueError(msg)
    return cpu_s / answered


def tree_cpu_s(processes: Iterable[psutil.Process]) -> float:
    """Sum the CPU time of a process tree, with the children its processes reaped.

    A process that exits stops reporting its own time, but its parent's
    ``children_user``/``children_system`` gain it once reaped, so the sum keeps
    growing while the tree reaps its own processes.

    Args:
        processes: The tree's processes still running.

    Returns:
        Seconds of user and system time.
    """
    total = 0.0
    for proc in processes:
        with contextlib.suppress(psutil.NoSuchProcess):
            times = proc.cpu_times()
            total += (
                times.user + times.system + times.children_user + times.children_system
            )
    return total


def copy_tracked(source: Path, target: Path) -> None:
    """Copy the files git tracks in a directory, so build output never comes along.

    Args:
        source: The directory, inside a git checkout.
        target: Where to copy them; replaced.

    Raises:
        RuntimeError: When git cannot list the files.
    """
    listing = git(source, "ls-files", "-z")
    if not listing:
        msg = f"git lists no files in {source}"
        raise RuntimeError(msg)
    shutil.rmtree(target, ignore_errors=True)
    for relative in filter(None, listing.split("\0")):
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, path)


def app_env(ctx: Context) -> dict[str, str]:
    """Build the environment of the playground's compile and runs.

    Args:
        ctx: The benchmark context.

    Returns:
        ``ctx.env`` with the ``.web`` directory in the cache directory, next
        to the copied app, so recopying the app keeps the compiled frontend.
    """
    return {**ctx.env, **cache_env(web_dir=ctx.cache_dir / "web")}


def prepare_app(ctx: Context) -> None:
    """Copy the playground into the cache directory and compile it once.

    Args:
        ctx: The benchmark context.

    Raises:
        RuntimeError: Outside a reflex checkout, where the playground is missing.
    """
    if not PLAYGROUND.is_dir():
        msg = f"the playground app is missing: {PLAYGROUND}"
        raise RuntimeError(msg)
    app = ctx.cache_dir / "app"
    copy_tracked(PLAYGROUND, app)
    run_cli(
        ctx.subject.python,
        ["compile"],
        cwd=app,
        env=app_env(ctx),
        timeout=COMPILE_TIMEOUT_S,
    ).check()


def checked_load(result: LoadResult) -> LoadResult:
    """Make sure a load result measures the server.

    Args:
        result: The result.

    Returns:
        The result.

    Raises:
        LoadError: When sessions failed or nothing was answered.
        GeneratorSaturated: When the generator did not keep up.
    """
    if errors := result.session_errors:
        msg = f"{len(errors)} of {result.sessions} sessions failed: {errors[0]}"
        raise LoadError(msg)
    if (reason := result.check()) is not None:
        raise GeneratorSaturated(reason, result)
    if not result.answered:
        msg = "the server answered no event"
        raise LoadError(msg)
    return result


class _Backend:
    """What one benchmark instance starts: a server, and the loads run against it.

    :meth:`stop_load` ends a running load and :meth:`stop` also the server, both
    from any thread, as ``conclude`` and ``cleanup`` must after a timed-out
    ``sample``; a load started after :meth:`stop` raises.
    """

    def __init__(
        self,
        ctx: Context,
        shape: EventShape,
        *,
        sessions: int,
        linked: bool = False,
    ) -> None:
        """Plan the backend; nothing starts yet.

        Args:
            ctx: The benchmark context.
            shape: The event the sessions send.
            sessions: The number of sessions of every load.
            linked: Whether every load first links its sessions to a fresh board,
                the state of ``shape``.
        """
        self.ctx = ctx
        self.shape = shape
        self.sessions = sessions
        self.linked = linked
        self.pinning = pinning()
        self.url: str | None = None
        self._lock = threading.Lock()
        self._stopped = False
        self._server: AppProcess | EchoProcess | None = None
        self._scope: CgroupScope | None = None
        self._runner: LoadRunner | None = None

    @property
    def cpu_method(self) -> str:
        """How the server's CPU time is read.

        Returns:
            ``cgroup`` (the scope's ``cpu.stat``) or ``psutil`` (the tree's CPU times).
        """
        return "psutil" if self._scope is None else "cgroup"

    def _own(self, server: AppProcess | EchoProcess) -> None:
        """Keep a server so :meth:`stop` stops it.

        Args:
            server: The server, not started yet.

        Raises:
            LoadError: When the backend was stopped.
        """
        with self._lock:
            if self._stopped:
                msg = "the backend was stopped"
                raise LoadError(msg)
            self._server = server

    def start_app(self) -> None:
        """Start the playground backend and pin it to the server CPUs."""
        ctx = self.ctx
        raise_fd_limit(self.sessions)
        states = ctx.workdir / "states"
        shutil.rmtree(states, ignore_errors=True)
        self._scope = CgroupScope() if CgroupScope.available() is None else None
        app = AppProcess(
            ctx.subject.python,
            ctx.cache_dir / "app",
            mode="prod",
            backend_only=True,
            reflex_version=ctx.subject.reflex_version,
            env=server_env(app_env(ctx), ctx.params["manager"], states),
            scope=self._scope,
        )
        self._own(app)
        app.start()
        app.wait_http_ready()
        if self.pinning is not None:
            # Workers granian starts later inherit the affinity.
            for proc in self._tree(app.pid):
                with contextlib.suppress(psutil.Error):
                    proc.cpu_affinity(self.pinning["server"])
        self.url = app.backend_url

    def start_echo(self) -> None:
        """Start an echo server on the server CPUs instead of reflex."""
        echo = EchoProcess(
            delta_key=self.shape.delta_key,
            seq_var=self.shape.seq_var,
            cpus=None if self.pinning is None else self.pinning["server"],
        )
        self._own(echo)
        self.url = echo.start()

    @staticmethod
    def _tree(pid: int) -> list[psutil.Process]:
        """List a process and its descendants.

        Args:
            pid: The root.

        Returns:
            The processes still running.
        """
        root = psutil.Process(pid)
        return [root, *root.children(recursive=True)]

    def server_cpu_s(self) -> float:
        """Read the server tree's CPU time.

        Returns:
            Seconds, from the cgroup scope or summed over the tree's processes.
        """
        if self._scope is not None:
            return self._scope.read().cpu_s
        assert isinstance(self._server, AppProcess)
        return tree_cpu_s(self._tree(self._server.pid))

    def run(
        self, mode: Mode, rate: float | None, window: Window
    ) -> tuple[LoadResult, float | None]:
        """Run one load against the server.

        Args:
            mode: ``open``, ``closed`` or ``fanout``.
            rate: The offered rate of the open loop.
            window: How long the load runs.

        Returns:
            The result, and the reflex server's CPU seconds in the window
            (``None`` for the echo server).

        Raises:
            LoadError: When the backend was stopped or the load failed.
        """
        assert self.url is not None
        sessions = self.sessions
        generator = None if self.pinning is None else self.pinning["generator"]
        plan = LoadPlan(
            endpoint=Endpoint(self.url),
            shape=self.shape,
            sessions=sessions,
            mode=mode,
            rate=rate,
            warmup_s=window.warmup_s,
            duration_s=window.duration_s,
            processes=(
                1 if mode == "fanout" else generator_processes(sessions, generator)
            ),
            cpus=generator,
            link=join_link(self.shape.delta_key) if self.linked else None,
        )
        with self._lock:
            if self._stopped:
                msg = "the backend was stopped"
                raise LoadError(msg)
            runner = self._runner = LoadRunner(plan)
        if not isinstance(self._server, AppProcess):
            return runner.run(), None
        marks: dict[str, float] = {}
        result = runner.run(lambda edge: marks.__setitem__(edge, self.server_cpu_s()))
        return result, marks["end"] - marks["start"]

    def load(
        self, *, mode: Mode, rate: float | None, window: Window
    ) -> tuple[LoadResult, float]:
        """Run one load against the reflex server and check it.

        Args:
            mode: ``open``, ``closed`` or ``fanout``.
            rate: The offered rate of the open loop.
            window: How long the load runs.

        Returns:
            The checked result and the server's CPU seconds in the window.
        """
        result, cpu_s = self.run(mode, rate, window)
        assert cpu_s is not None
        return checked_load(result), cpu_s

    def extra(self, result: LoadResult, **more: Any) -> dict[str, Any]:
        """Describe a sample: the load result, how CPU was read and the pinning.

        Args:
            result: The load result.
            **more: Further entries.

        Returns:
            The sample's extra data.
        """
        return {
            **result.summary(),
            "histogram": result.histogram,
            "cpu_method": self.cpu_method,
            "pinning": self.pinning,
            **more,
        }

    def stop_load(self) -> None:
        """Stop the running load, if any; safe from any thread and more than once."""
        with self._lock:
            runner = self._runner
        if runner is not None:
            runner.stop()

    def stop(self) -> None:
        """Stop the running load and the server; safe from any thread and more than once."""
        with self._lock:
            self._stopped = True
            runner, server = self._runner, self._server
        if runner is not None:
            runner.stop()
        if server is not None:
            server.stop()


class _OnBackend:
    """Hooks of a benchmark whose instance keeps one backend for all its samples."""

    backend: _Backend | None = None

    def conclude(self, ctx: Context) -> None:
        """Stop a load a timed-out sample left running; the backend keeps serving.

        Args:
            ctx: The benchmark context.
        """
        if self.backend is not None:
            self.backend.stop_load()

    def cleanup(self, ctx: Context) -> None:
        """Stop the load and the backend, also after a failure or a timeout.

        Args:
            ctx: The benchmark context.
        """
        if self.backend is not None:
            self.backend.stop()
            self.backend = None


class _OnPlayground(_OnBackend):
    """Hooks of a benchmark against the playground backend.

    Attributes:
        event: The name of the event the sessions send, in ``SHAPES`` or
            ``SHARED_SHAPES``.
        linked: Whether every load first links its sessions to a fresh board.
        sessions_param: The parameter giving the number of sessions.
        probe: The mode of the closed-loop probe of ``setup``.
    """

    event: str
    linked = False
    sessions_param = "sessions"
    probe: Mode = "closed"
    capacity = 0.0

    def setup_cache(self, ctx: Context) -> None:
        """Copy and compile the playground.

        Args:
            ctx: The benchmark context.
        """
        prepare_app(ctx)

    def setup(self, ctx: Context) -> None:
        """Record the fixture, name the states, start the backend and probe its capacity with a short closed loop.

        The probe also warms the backend (imports on first use, caches), so no
        sample meets it cold.

        Args:
            ctx: The benchmark context.
        """
        ctx.fixture = describe_playground()
        self.backend = _Backend(
            ctx,
            (SHAPES | SHARED_SHAPES)[self.event](playground_states(ctx)),
            sessions=ctx.params[self.sessions_param],
            linked=self.linked,
        )
        self.backend.start_app()
        probe, _ = self.backend.load(mode=self.probe, rate=None, window=PROBE_WINDOW)
        self.capacity = probe.answered_rate


def _response(result: LoadResult, *names: str) -> dict[str, float]:
    """Pick response time percentiles of an open-loop result.

    Args:
        result: The result.
        *names: The percentiles, e.g. ``p50``.

    Returns:
        ``response_<name>`` to seconds.
    """
    assert result.response_s is not None
    return {f"response_{name}": result.response_s[name] for name in names}


def _underpowered(result: LoadResult) -> dict[str, bool]:
    """Flag a p99 taken from too few events to mean much.

    Args:
        result: The result.

    Returns:
        ``{"p99_underpowered": True}`` under 10 000 answered events, else ``{}``.
    """
    return {"p99_underpowered": True} if result.answered < UNDERPOWERED_P99 else {}


def _register(name: str, *, shared: bool = False) -> None:
    """Register the capacity and latency benchmarks of one event shape.

    Args:
        name: The shape's name in ``SHAPES`` or ``SHARED_SHAPES``, and in the
            benchmark ids.
        shared: Whether the sessions share one board; then the benchmarks join
            ``daily`` at the cheap point, at the rate their own capacity sets.
    """
    if name == "simple":
        cheap, latency_params = ("smoke", "daily"), CHEAP_LATENCY
    elif shared:
        cheap, latency_params = ("daily",), CHEAP_CONTENTION_LATENCY
    else:
        cheap, latency_params = (), CHEAP_LATENCY

    @benchmark(
        id=f"events.{name}.capacity",
        suites=cheap,
        kind="rate",
        params={"manager": MANAGERS, "sessions": SESSIONS},
        suite_params=dict.fromkeys(cheap, CHEAP),
        metrics={
            "throughput": THROUGHPUT,
            "service_p50": Metric(
                unit="s", direction="lower", description="answer time minus send time"
            ),
            "cpu_per_event": CPU_PER_EVENT,
        },
        timeout=HOOK_TIMEOUT_S,
        setup_timeout=COMPILE_TIMEOUT_S + 60,
        estimate=5,
    )
    class Capacity(_OnPlayground):
        """Closed loop, 3 s after 1 s of warmup: the most events per second the backend answers."""

        event = name
        linked = shared

        def sample(self, ctx: Context) -> SampleResult:
            """Load the backend as fast as it answers.

            Args:
                ctx: The benchmark context.

            Returns:
                The throughput, the median service time and the CPU per event.
            """
            assert self.backend is not None
            result, cpu_s = self.backend.load(
                mode="closed", rate=None, window=CAPACITY_WINDOW
            )
            assert result.service_s is not None
            return SampleResult(
                {
                    "throughput": result.answered_rate,
                    "service_p50": result.service_s["p50"],
                    "cpu_per_event": cpu_per_event(cpu_s, result),
                },
                extra=self.backend.extra(result),
            )

    @benchmark(
        id=f"events.{name}.latency",
        suites=cheap,
        kind="latency",
        params={"manager": MANAGERS, "sessions": SESSIONS, "rate": ("auto",)},
        suite_params=dict.fromkeys(cheap, latency_params),
        metrics={
            "response_p50": _latency("p50"),
            "response_p90": _latency("p90"),
            "response_p99": _latency("p99"),
            "response_max": _latency("maximum"),
            "throughput": THROUGHPUT,
            "unanswered": UNANSWERED,
            "cpu_per_event": CPU_PER_EVENT,
        },
        timeout=HOOK_TIMEOUT_S,
        setup_timeout=COMPILE_TIMEOUT_S + 60,
        estimate=7,
    )
    class Latency(_OnPlayground):
        """Open loop, 5 s after 1 s of warmup, at half the capacity (or --param rate=): the response times."""

        event = name
        linked = shared
        rate = 0.0

        def setup(self, ctx: Context) -> None:
            """Start and probe the backend, and choose the offered rate.

            Args:
                ctx: The benchmark context.
            """
            super().setup(ctx)
            rate = ctx.params["rate"]
            self.rate = LATENCY_SHARE * self.capacity if rate == "auto" else float(rate)

        def sample(self, ctx: Context) -> SampleResult:
            """Offer the rate and measure from the planned send times.

            Args:
                ctx: The benchmark context.

            Returns:
                Response time percentiles, throughput, unanswered events and
                the CPU per event.
            """
            assert self.backend is not None
            result, cpu_s = self.backend.load(
                mode="open", rate=self.rate, window=LATENCY_WINDOW
            )
            return SampleResult(
                {
                    **_response(result, "p50", "p90", "p99", "max"),
                    "throughput": result.answered_rate,
                    "unanswered": result.unanswered,
                    "cpu_per_event": cpu_per_event(cpu_s, result),
                },
                extra=self.backend.extra(
                    result, probed_capacity=self.capacity, **_underpowered(result)
                ),
            )


for _name in SHAPES:
    _register(_name)
_register("shared_contention", shared=True)


@benchmark(
    id="events.shared_fanout.broadcast",
    suites=("daily",),
    kind="latency",
    params={"manager": MANAGERS, "linked": LINKED},
    suite_params={"daily": CHEAP_FANOUT},
    metrics={
        "throughput": Metric(
            unit="ev/s",
            direction="higher",
            description="events per second received by every linked session",
        ),
        "broadcast_p50": Metric(
            unit="s",
            direction="lower",
            description="p50 of the time until the last linked session had the delta",
        ),
        "broadcast_p99": Metric(
            unit="s",
            direction="lower",
            description="p99 of the time until the last linked session had the delta",
        ),
        "fanout_spread_p50": Metric(
            unit="s",
            direction="lower",
            description="p50 of last minus first arrival of the delta over the sessions",
        ),
        "cpu_per_event": CPU_PER_EVENT,
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=COMPILE_TIMEOUT_S + 60,
    estimate=5,
)
class Fanout(_OnPlayground):
    """One of the sessions linked to a board sends, closed loop, 3 s after 1 s of warmup: the time until every linked session has the delta."""

    event = "shared_fanout"
    linked = True
    sessions_param = "linked"
    probe: Mode = "fanout"

    def sample(self, ctx: Context) -> SampleResult:
        """Send from the first linked session, one event at a time.

        Args:
            ctx: The benchmark context.

        Returns:
            The broadcast throughput and times, the spread and the CPU per event.
        """
        assert self.backend is not None
        result, cpu_s = self.backend.load(
            mode="fanout", rate=None, window=FANOUT_WINDOW
        )
        assert result.service_s is not None
        assert result.spread_s is not None
        return SampleResult(
            {
                "throughput": result.answered_rate,
                "broadcast_p50": result.service_s["p50"],
                "broadcast_p99": result.service_s["p99"],
                "fanout_spread_p50": result.spread_s["p50"],
                "cpu_per_event": cpu_per_event(cpu_s, result),
            },
            extra=self.backend.extra(result, **_underpowered(result)),
        )


@benchmark(
    id="events.simple.knee",
    kind="rate",
    params={"manager": MANAGERS, "sessions": SESSIONS},
    metrics={
        "knee_rate": Metric(
            unit="ev/s",
            direction="higher",
            description="the highest offered rate the backend keeps up with",
        ),
        "low_load_p99": _latency("p99, at 10 % of the capacity,"),
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=COMPILE_TIMEOUT_S + 60,
    estimate=50,
)
class Knee(_OnPlayground):
    """Open-loop steps from 10 % to 110 % of the capacity, 4 s after 1 s of warmup each: where the backend stops keeping up."""

    event = "simple"

    def sample(self, ctx: Context) -> SampleResult:
        """Run the steps and find the knee.

        Args:
            ctx: The benchmark context.

        Returns:
            The knee and the low-load p99, with the step table as extra data.

        Raises:
            GeneratorSaturated: When the generator falls behind at a step.
            LoadError: When sessions fail at a step.
        """
        backend = self.backend
        assert backend is not None
        steps = []
        for share in KNEE_SHARES:
            result, _ = backend.run("open", share * self.capacity, KNEE_WINDOW)
            if errors := result.session_errors:
                msg = f"{len(errors)} sessions failed at {share:.0%} of the capacity: {errors[0]}"
                raise LoadError(msg)
            if (reason := result.check()) is not None:
                reason = f"{reason} (at {share:.0%} of the capacity)"
                raise GeneratorSaturated(reason, result)
            steps.append({
                "share": share,
                "offered": result.offered_rate,
                "achieved": result.answered_rate,
                "p99": None if result.response_s is None else result.response_s["p99"],
                "unanswered": result.unanswered,
            })
        knee, low_load_p99 = find_knee(steps)
        return SampleResult(
            {"knee_rate": knee, "low_load_p99": low_load_p99},
            extra={
                "capacity": self.capacity,
                "steps": steps,
                "pinning": backend.pinning,
                **({"knee": "none"} if not knee else {}),
            },
        )


@benchmark(
    id="events.sessions.at_1hz",
    kind="latency",
    params={"manager": MANAGERS, "sessions": AT_1HZ_SESSIONS},
    metrics={
        "response_p50": _latency("p50"),
        "response_p99": _latency("p99"),
        "unanswered": UNANSWERED,
        "cpu_per_event": CPU_PER_EVENT,
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=COMPILE_TIMEOUT_S + 60,
    estimate=16,
)
class AtOneHz(_OnPlayground):
    """Many sessions sending one simple event per second, 10 s after 3 s of warmup: the cost of idle-ish users."""

    event = "simple"

    def sample(self, ctx: Context) -> SampleResult:
        """Offer one event per second per session.

        Args:
            ctx: The benchmark context.

        Returns:
            Response time percentiles, unanswered events and the CPU per event.
        """
        assert self.backend is not None
        result, cpu_s = self.backend.load(
            mode="open", rate=float(ctx.params["sessions"]), window=AT_1HZ_WINDOW
        )
        return SampleResult(
            {
                **_response(result, "p50", "p99"),
                "unanswered": result.unanswered,
                "cpu_per_event": cpu_per_event(cpu_s, result),
            },
            extra=self.backend.extra(result, **_underpowered(result)),
        )


@benchmark(
    id="selftest.events.calibrate",
    suites=("selftest",),
    kind="rate",
    metrics={
        "closed_ceiling": Metric(
            unit="ev/s",
            direction="higher",
            description="closed-loop rate of 10 sessions against the echo server",
        ),
        "open_lag_p99": Metric(
            unit="s",
            direction="lower",
            description=(
                f"send lag p99 of the open loop at {CALIBRATION_RATE:.0f} ev/s,"
                f" {CALIBRATION_FACTOR}x the highest fixed rate of the suite"
            ),
        ),
    },
    timeout=HOOK_TIMEOUT_S,
    estimate=8,
)
class Calibrate(_OnBackend):
    """Run the generator against an echo server, which answers at once: the closed-loop ceiling, and the open loop at 3x the highest rate the suite offers."""

    def setup(self, ctx: Context) -> None:
        """Start the echo server.

        Args:
            ctx: The benchmark context.
        """
        self.backend = _Backend(
            ctx, SHAPES["simple"](ECHO_STATES), sessions=CALIBRATION_SESSIONS
        )
        self.backend.start_echo()

    def sample(self, ctx: Context) -> SampleResult:
        """Measure the closed-loop ceiling, then offer the calibration rate.

        Args:
            ctx: The benchmark context.

        Returns:
            The ceiling and the open loop's send lag p99, with both results as
            extra data.

        Raises:
            GeneratorSaturated: When the generator does not keep up at the
                calibration rate, so the suite's rates are beyond it.
            LoadError: When sessions fail.
        """
        backend = self.backend
        assert backend is not None
        # The ceiling is where the generator saturates, so only sessions can fail it.
        closed, _ = backend.run("closed", None, CALIBRATION_CLOSED_WINDOW)
        if errors := closed.session_errors:
            msg = f"{len(errors)} of {closed.sessions} sessions failed: {errors[0]}"
            raise LoadError(msg)
        opened, _ = backend.run("open", CALIBRATION_RATE, CALIBRATION_STEP_WINDOW)
        checked_load(opened)
        assert opened.lag_s is not None
        if opened.unanswered:
            msg = (
                f"generator saturated: {opened.unanswered} events unanswered"
                f" at {CALIBRATION_RATE:.0f} ev/s"
            )
            raise GeneratorSaturated(msg, opened)
        return SampleResult(
            {
                "closed_ceiling": closed.answered_rate,
                "open_lag_p99": opened.lag_s["p99"],
            },
            extra={
                "closed": closed.to_dict(),
                "open": opened.to_dict(),
                "pinning": backend.pinning,
            },
        )
