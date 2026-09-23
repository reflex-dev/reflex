"""Event throughput and latency: how many events a reflex app answers, and how fast.

Each sample starts the playground (``examples/playground``) as a production
backend, ``reflex run --env prod --backend-only`` with one granian worker, and
drives it with the socket.io generator of :mod:`reflex_bench.drivers.events`:

- ``events.<shape>.capacity``: closed loop, the most events per second.
- ``events.<shape>.latency``: open loop at a fixed rate (half the capacity a
  closed-loop probe measures, unless ``--param rate=`` fixes it), the response
  times a user sees.
- ``events.<shape>.knee``: open-loop steps from 10 % to 110 % of the probed
  capacity; the knee is the highest rate the backend still keeps up with.
- ``events.sessions.at_1hz``: many sessions sending one event per second.

The shapes are the playground's ``BenchState.set_seq*`` handlers. The state
manager is a parameter; ``redis`` joins ``memory`` and ``disk`` when
``REFLEX_REDIS_URL`` is set in the harness's environment. On Linux with four
CPUs or more, the server runs on the lower half of the CPUs (not CPU 0) and the
generator on the upper half.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import psutil

from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.context import Context, git
from reflex_bench.drivers.app_process import AppProcess, cache_env, run_cli
from reflex_bench.drivers.echo_server import EchoProcess
from reflex_bench.drivers.events import (
    EventShape,
    GeneratorSaturated,
    LoadError,
    LoadPlan,
    LoadResult,
    LoadRunner,
    Mode,
    raise_fd_limit,
    seq_payload,
)
from reflex_bench.registry import Metric, SampleResult, benchmark

PLAYGROUND = Path(__file__).resolve().parents[5] / "examples" / "playground"
BENCH_STATE = "reflex___state____state.playground___state____bench_state"
SEQ_VAR = "last_seq_rx_state_"
SESSIONS = (1, 10, 50, 200)
AT_1HZ_SESSIONS = (50, 200, 1000)
KNEE_SHARES = (0.10, 0.25, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00, 1.10)
# A step keeps up when it answers 99 % of the offered rate, leaves nothing
# unanswered and keeps its p99 within 3x the p99 of the 10 % step.
KNEE_ANSWERED_SHARE = 0.99
KNEE_P99_FACTOR = 3.0
LATENCY_SHARE = 0.5
UNDERPOWERED_P99 = 10_000
CALIBRATION_SESSIONS = 10
CALIBRATION_SHARES = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50)
COMPILE_TIMEOUT_S = 600.0
HOOK_TIMEOUT_S = 600.0
KNEE_TIMEOUT_S = 1200.0


def _shape(handler: str) -> EventShape:
    """Describe a ``BenchState`` handler of the playground.

    Args:
        handler: The handler's name.

    Returns:
        The event shape: payload ``{"seq": n}``, echoed as ``last_seq``.
    """
    return EventShape(
        name=f"{BENCH_STATE}.{handler}",
        payload=seq_payload,
        delta_key=BENCH_STATE,
        seq_var=SEQ_VAR,
    )


SHAPES = {
    "simple": _shape("set_seq"),
    "complex": _shape("set_seq_complex"),
    "cross": _shape("set_seq_cross"),
    "background": _shape("set_seq_background"),
    # SharedState fan-out (one event updating many sessions) and SharedState
    # contention (many sessions writing one shared state) need the playground's
    # SharedState surface (ENG-12609); nothing is registered for them yet.
}


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


def split_cpus(allowed: Sequence[int]) -> dict[str, list[int]] | None:
    """Split CPUs between the server and the generator.

    Args:
        allowed: The CPUs the harness may use.

    Returns:
        ``{"server": lower half minus CPU 0, "generator": upper half}``, or
        ``None`` with fewer than four CPUs.
    """
    cpus = sorted(allowed)
    if len(cpus) < 4:
        return None
    half = len(cpus) // 2
    return {
        "server": [cpu for cpu in cpus[:half] if cpu != 0],
        "generator": cpus[half:],
    }


def pinning() -> dict[str, list[int]] | None:
    """Split this machine's CPUs between the server and the generator.

    Returns:
        The split, or ``None`` where CPU affinity is not available (not Linux).
    """
    if not hasattr(os, "sched_getaffinity"):
        return None
    return split_cpus(sorted(os.sched_getaffinity(0)))


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


def cpu_per_event(cpu_s: float, answered: int) -> float:
    """Divide the server's CPU time by the events it answered.

    Args:
        cpu_s: CPU seconds of the server tree in the measured window.
        answered: The events answered.

    Returns:
        Seconds of CPU per event.

    Raises:
        ValueError: Without answered events.
    """
    if answered <= 0:
        msg = "no answered event to divide the CPU time by"
        raise ValueError(msg)
    return cpu_s / answered


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


def _checked(result: LoadResult) -> LoadResult:
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


class _Sample:
    """What one sample starts: a server and the load runs against it.

    :meth:`stop` ends both from any thread, as ``conclude`` must after a
    timed-out ``sample``; a load started after that raises.
    """

    def __init__(self, ctx: Context, shape: EventShape) -> None:
        """Plan the sample; nothing starts yet.

        Args:
            ctx: The benchmark context.
            shape: The event the sessions send.
        """
        self.ctx = ctx
        self.shape = shape
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
            LoadError: When the sample was stopped.
        """
        with self._lock:
            if self._stopped:
                msg = "the sample was stopped"
                raise LoadError(msg)
            self._server = server

    def start_app(self) -> None:
        """Start the playground backend and pin it to the server CPUs."""
        ctx = self.ctx
        raise_fd_limit(ctx.params["sessions"])
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
        total = 0.0
        for proc in self._tree(self._server.pid):
            with contextlib.suppress(psutil.NoSuchProcess):
                times = proc.cpu_times()
                total += times.user + times.system
        return total

    def run(
        self, mode: Mode, rate: float | None, warmup_s: float, duration_s: float
    ) -> tuple[LoadResult, float | None]:
        """Run one load against the server.

        Args:
            mode: ``open`` or ``closed``.
            rate: The offered rate of the open loop.
            warmup_s: Seconds of load before the measured window.
            duration_s: The measured window.

        Returns:
            The result, and the reflex server's CPU seconds in the window
            (``None`` for the echo server).

        Raises:
            LoadError: When the sample was stopped or the load failed.
        """
        assert self.url is not None
        sessions = self.ctx.params.get("sessions", CALIBRATION_SESSIONS)
        generator = None if self.pinning is None else self.pinning["generator"]
        plan = LoadPlan(
            backend_url=self.url,
            reflex_version=self.ctx.subject.reflex_version,
            shape=self.shape,
            sessions=sessions,
            mode=mode,
            rate=rate,
            warmup_s=warmup_s,
            duration_s=duration_s,
            processes=generator_processes(sessions, generator),
            cpus=generator,
        )
        with self._lock:
            if self._stopped:
                msg = "the sample was stopped"
                raise LoadError(msg)
            runner = self._runner = LoadRunner(plan)
        if not isinstance(self._server, AppProcess):
            return runner.run(), None
        marks: dict[str, float] = {}
        result = runner.run(lambda edge: marks.__setitem__(edge, self.server_cpu_s()))
        return result, marks["end"] - marks["start"]

    def load(
        self, *, mode: Mode, rate: float | None, warmup_s: float, duration_s: float
    ) -> tuple[LoadResult, float]:
        """Run one load against the reflex server and check it.

        Args:
            mode: ``open`` or ``closed``.
            rate: The offered rate of the open loop.
            warmup_s: Seconds of load before the measured window.
            duration_s: The measured window.

        Returns:
            The checked result and the server's CPU seconds in the window.
        """
        result, cpu_s = self.run(mode, rate, warmup_s, duration_s)
        assert cpu_s is not None
        return _checked(result), cpu_s

    def extra(self, result: LoadResult, **more: Any) -> dict[str, Any]:
        """Describe a sample: the load result, how CPU was read and the pinning.

        Args:
            result: The load result.
            **more: Further entries.

        Returns:
            The sample's extra data.
        """
        return {
            **result.to_dict(),
            "cpu_method": self.cpu_method,
            "pinning": self.pinning,
            **more,
        }

    def stop(self) -> None:
        """Stop the running load and the server; safe from any thread and more than once."""
        with self._lock:
            self._stopped = True
            runner, server = self._runner, self._server
        if runner is not None:
            runner.stop()
        if server is not None:
            server.stop()


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


def _register(name: str, shape: EventShape) -> None:
    """Register the capacity, latency and knee benchmarks of one event shape.

    Args:
        name: The shape's name in the benchmark ids.
        shape: The event.
    """
    smoke = ("smoke",) if name == "simple" else ()

    @benchmark(
        id=f"events.{name}.capacity",
        suites=(*smoke, "daily"),
        kind="rate",
        params={"manager": MANAGERS, "sessions": SESSIONS},
        suite_params={"smoke": {"sessions": [10]}} if smoke else None,
        metrics={
            "throughput": THROUGHPUT,
            "service_p50": Metric(
                unit="s", direction="lower", description="answer time minus send time"
            ),
            "cpu_us_per_event": CPU_PER_EVENT,
        },
        timeout=HOOK_TIMEOUT_S,
        setup_timeout=COMPILE_TIMEOUT_S + 60,
        estimate=22,
    )
    class Capacity:
        """Closed loop, 10 s after 3 s of warmup: the most events per second the backend answers."""

        current: _Sample | None = None

        def setup_cache(self, ctx: Context) -> None:
            """Copy and compile the playground.

            Args:
                ctx: The benchmark context.
            """
            prepare_app(ctx)

        def prepare(self, ctx: Context) -> None:
            """Start the backend.

            Args:
                ctx: The benchmark context.
            """
            self.current = _Sample(ctx, shape)
            self.current.start_app()

        def sample(self, ctx: Context) -> SampleResult:
            """Load the backend as fast as it answers.

            Args:
                ctx: The benchmark context.

            Returns:
                The throughput, the median service time and the CPU per event.
            """
            assert self.current is not None
            result, cpu_s = self.current.load(
                mode="closed", rate=None, warmup_s=3, duration_s=10
            )
            assert result.service_s is not None
            return SampleResult(
                {
                    "throughput": result.answered_rate,
                    "service_p50": result.service_s["p50"],
                    "cpu_us_per_event": cpu_per_event(cpu_s, result.answered),
                },
                extra=self.current.extra(result),
            )

        def conclude(self, ctx: Context) -> None:
            """Stop the load and the backend, also after a failure or a timeout.

            Args:
                ctx: The benchmark context.
            """
            if self.current is not None:
                self.current.stop()
                self.current = None

    @benchmark(
        id=f"events.{name}.latency",
        suites=(*smoke, "daily"),
        kind="latency",
        params={"manager": MANAGERS, "sessions": SESSIONS, "rate": ("auto",)},
        suite_params={"smoke": {"sessions": [10], "rate": [50]}} if smoke else None,
        metrics={
            "response_p50": _latency("p50"),
            "response_p90": _latency("p90"),
            "response_p99": _latency("p99"),
            "response_max": _latency("maximum"),
            "throughput": THROUGHPUT,
            "unanswered": UNANSWERED,
            "cpu_us_per_event": CPU_PER_EVENT,
        },
        timeout=HOOK_TIMEOUT_S,
        setup_timeout=COMPILE_TIMEOUT_S + 60,
        estimate=58,
    )
    class Latency:
        """Open loop, 30 s after 10 s of warmup, at half the capacity (or --param rate=): the response times."""

        current: _Sample | None = None
        rate = 0.0
        capacity: float | None = None

        def setup_cache(self, ctx: Context) -> None:
            """Copy and compile the playground.

            Args:
                ctx: The benchmark context.
            """
            prepare_app(ctx)

        def prepare(self, ctx: Context) -> None:
            """Start the backend and, for ``rate=auto``, probe its capacity.

            Args:
                ctx: The benchmark context.
            """
            self.current = _Sample(ctx, shape)
            self.current.start_app()
            if ctx.params["rate"] == "auto":
                probe, _ = self.current.load(
                    mode="closed", rate=None, warmup_s=1, duration_s=5
                )
                self.capacity = probe.answered_rate
                self.rate = LATENCY_SHARE * probe.answered_rate
            else:
                self.rate = float(ctx.params["rate"])

        def sample(self, ctx: Context) -> SampleResult:
            """Offer the rate for 40 s and measure from the planned send times.

            Args:
                ctx: The benchmark context.

            Returns:
                Response time percentiles, throughput, unanswered events and
                the CPU per event.
            """
            assert self.current is not None
            result, cpu_s = self.current.load(
                mode="open", rate=self.rate, warmup_s=10, duration_s=30
            )
            return SampleResult(
                {
                    **_response(result, "p50", "p90", "p99", "max"),
                    "throughput": result.answered_rate,
                    "unanswered": result.unanswered,
                    "cpu_us_per_event": cpu_per_event(cpu_s, result.answered),
                },
                extra=self.current.extra(
                    result, probed_capacity=self.capacity, **_underpowered(result)
                ),
            )

        def conclude(self, ctx: Context) -> None:
            """Stop the load and the backend, also after a failure or a timeout.

            Args:
                ctx: The benchmark context.
            """
            if self.current is not None:
                self.current.stop()
                self.current = None

    @benchmark(
        id=f"events.{name}.knee",
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
        timeout=KNEE_TIMEOUT_S,
        setup_timeout=COMPILE_TIMEOUT_S + 60,
        estimate=440,
    )
    class Knee:
        """Open-loop steps from 10 % to 110 % of the capacity, 30 s after 10 s of warmup each: where the backend stops keeping up."""

        current: _Sample | None = None
        capacity = 0.0

        def setup_cache(self, ctx: Context) -> None:
            """Copy and compile the playground.

            Args:
                ctx: The benchmark context.
            """
            prepare_app(ctx)

        def prepare(self, ctx: Context) -> None:
            """Start the backend and probe its capacity.

            Args:
                ctx: The benchmark context.
            """
            self.current = _Sample(ctx, shape)
            self.current.start_app()
            probe, _ = self.current.load(
                mode="closed", rate=None, warmup_s=1, duration_s=5
            )
            self.capacity = probe.answered_rate

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
            current = self.current
            assert current is not None
            steps = []
            for share in KNEE_SHARES:
                result, _ = current.run("open", share * self.capacity, 10, 30)
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
                    "p99": None
                    if result.response_s is None
                    else result.response_s["p99"],
                    "unanswered": result.unanswered,
                })
            knee, low_load_p99 = find_knee(steps)
            return SampleResult(
                {"knee_rate": knee, "low_load_p99": low_load_p99},
                extra={
                    "capacity": self.capacity,
                    "steps": steps,
                    "pinning": current.pinning,
                    **({"knee": "none"} if not knee else {}),
                },
            )

        def conclude(self, ctx: Context) -> None:
            """Stop the load and the backend, also after a failure or a timeout.

            Args:
                ctx: The benchmark context.
            """
            if self.current is not None:
                self.current.stop()
                self.current = None


for _name, _shape_of in SHAPES.items():
    _register(_name, _shape_of)


@benchmark(
    id="events.sessions.at_1hz",
    suites=("daily",),
    kind="latency",
    params={"manager": MANAGERS, "sessions": AT_1HZ_SESSIONS},
    metrics={
        "response_p50": _latency("p50"),
        "response_p99": _latency("p99"),
        "unanswered": UNANSWERED,
        "cpu_us_per_event": CPU_PER_EVENT,
    },
    timeout=HOOK_TIMEOUT_S,
    setup_timeout=COMPILE_TIMEOUT_S + 60,
    estimate=60,
)
class AtOneHz:
    """Many sessions sending one simple event per second, 30 s after 10 s of warmup: the cost of idle-ish users."""

    current: _Sample | None = None

    def setup_cache(self, ctx: Context) -> None:
        """Copy and compile the playground.

        Args:
            ctx: The benchmark context.
        """
        prepare_app(ctx)

    def prepare(self, ctx: Context) -> None:
        """Start the backend.

        Args:
            ctx: The benchmark context.
        """
        self.current = _Sample(ctx, SHAPES["simple"])
        self.current.start_app()

    def sample(self, ctx: Context) -> SampleResult:
        """Offer one event per second per session.

        Args:
            ctx: The benchmark context.

        Returns:
            Response time percentiles, unanswered events and the CPU per event.
        """
        assert self.current is not None
        result, cpu_s = self.current.load(
            mode="open", rate=float(ctx.params["sessions"]), warmup_s=10, duration_s=30
        )
        return SampleResult(
            {
                **_response(result, "p50", "p99"),
                "unanswered": result.unanswered,
                "cpu_us_per_event": cpu_per_event(cpu_s, result.answered),
            },
            extra=self.current.extra(result, **_underpowered(result)),
        )

    def conclude(self, ctx: Context) -> None:
        """Stop the load and the backend, also after a failure or a timeout.

        Args:
            ctx: The benchmark context.
        """
        if self.current is not None:
            self.current.stop()
            self.current = None


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
        "open_max_rate": Metric(
            unit="ev/s",
            direction="higher",
            description="the highest open-loop rate that passes the self-check",
        ),
    },
    timeout=HOOK_TIMEOUT_S,
    estimate=50,
)
class Calibrate:
    """Run the generator against an echo server, which answers at once: how far it goes before it saturates."""

    current: _Sample | None = None

    def prepare(self, ctx: Context) -> None:
        """Start the echo server.

        Args:
            ctx: The benchmark context.
        """
        self.current = _Sample(ctx, SHAPES["simple"])
        self.current.start_echo()

    def sample(self, ctx: Context) -> SampleResult:
        """Measure the closed-loop ceiling, then open-loop steps up to half of it.

        Args:
            ctx: The benchmark context.

        Returns:
            The ceiling and the highest open-loop rate that passed the self-check,
            with each step's lag, CPU and check as extra data.
        """
        current = self.current
        assert current is not None
        closed, _ = current.run("closed", None, 1, 5)
        steps = []
        for share in CALIBRATION_SHARES:
            result, _ = current.run("open", share * closed.answered_rate, 1, 3)
            assert result.lag_s is not None
            steps.append({
                "offered": result.offered_rate,
                "answered": result.answered_rate,
                "unanswered": result.unanswered,
                "lag_p99_s": result.lag_s["p99"],
                "generator_cpu_fraction": result.generator_cpu_fraction,
                "check": result.check(),
            })
        passing = [
            step["offered"]
            for step in steps
            if step["check"] is None and step["unanswered"] == 0
        ]
        return SampleResult(
            {
                "closed_ceiling": closed.answered_rate,
                "open_max_rate": max(passing, default=0.0),
            },
            extra={
                "closed": {
                    "service_s": closed.service_s,
                    "generator_cpu_fraction": closed.generator_cpu_fraction,
                },
                "steps": steps,
                "pinning": current.pinning,
            },
        )

    def conclude(self, ctx: Context) -> None:
        """Stop the load and the echo server, also after a failure or a timeout.

        Args:
            ctx: The benchmark context.
        """
        if self.current is not None:
            self.current.stop()
            self.current = None
