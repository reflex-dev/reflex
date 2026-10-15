"""Self-test benchmarks: they exercise the harness itself.

Only the ``selftest`` suite contains them, so they stay out of ``list`` and
``run`` unless asked for with ``--suite selftest`` or a ``selftest.*`` filter.
The ``selftest.app.*`` ones drive a real blank app of the subject through its
CLI, to check the app driver and the collectors.
"""

from __future__ import annotations

import dataclasses
import math
import random
import threading
import time
from pathlib import Path

from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppProcess, cache_env, run_cli
from reflex_bench.registry import Metric, SampleResult, benchmark

WALL = {"wall": Metric(unit="s", direction="lower")}
APP_TIMEOUT_S = 600.0


def noise_value(rng: random.Random, cv: float, shift: float = 1.0) -> float:
    """Draw a log-normal value with median ``shift`` seconds.

    Args:
        rng: The random generator.
        cv: The coefficient of variation, in percent.
        shift: The median, as a multiple of 1 s; ``1.1`` is a 10 % regression.

    Returns:
        The value in seconds.
    """
    sigma = math.sqrt(math.log1p((cv / 100) ** 2))
    return shift * rng.lognormvariate(0.0, sigma)


@benchmark(
    id="selftest.sleep",
    suites=("selftest",),
    params={"ms": [10, 50]},
    metrics=WALL,
    warmup=1,
    timeout=10,
    estimate=0.05,
)
class Sleep:
    """Sleep for a fixed time; checks the timing pipeline."""

    def sample(self, ctx: Context) -> None:
        """Sleep; the scheduler's wall-time measurement is the result.

        Args:
            ctx: The benchmark context.
        """
        time.sleep(ctx.params["ms"] / 1000)


@benchmark(
    id="selftest.noise",
    suites=("selftest",),
    params={"cv": [5, 20]},
    hidden_params={"shift": 1.0},
    metrics={"value": Metric(unit="s", direction="lower")},
    estimate=0,
)
class Noise:
    """Return seeded log-normal values around 1 s without waiting; checks statistics."""

    def sample(self, ctx: Context) -> dict[str, float]:
        """Draw one value.

        Args:
            ctx: The benchmark context; ``shift`` multiplies the values.

        Returns:
            The drawn value.
        """
        return {"value": noise_value(ctx.rng, ctx.params["cv"], ctx.params["shift"])}


@benchmark(
    id="selftest.exact",
    suites=("selftest",),
    kind="track",
    metrics={"bytes": Metric(unit="B", direction="lower", assume="exact")},
    estimate=0,
)
class Exact:
    """Return a constant byte count; checks deterministic metrics."""

    def sample(self, ctx: Context) -> dict[str, float]:
        """Report the constant.

        Args:
            ctx: The benchmark context.

        Returns:
            The byte count.
        """
        return {"bytes": 238_400}


@benchmark(
    id="selftest.fail",
    suites=("selftest",),
    metrics=WALL,
    estimate=0,
)
class Fail:
    """Raise in sample(); checks that failures are recorded and the run continues."""

    def sample(self, ctx: Context) -> None:
        """Fail.

        Args:
            ctx: The benchmark context.

        Raises:
            RuntimeError: Always.
        """
        msg = "selftest.fail always fails"
        raise RuntimeError(msg)


@benchmark(
    id="selftest.timeout",
    suites=("selftest",),
    metrics=WALL,
    timeout=0.5,
    # The first sample times out after 0.5 s and ends the instance, but `list`
    # multiplies the per-sample estimate by the 30 automatic runs.
    estimate=0.5 / 30,
)
class Timeout:
    """Block past the timeout until conclude() releases it; checks timeout handling."""

    def setup(self, ctx: Context) -> None:
        """Create the event that releases a blocked sample.

        Args:
            ctx: The benchmark context.
        """
        self.release = threading.Event()

    def sample(self, ctx: Context) -> None:
        """Block until released (or an hour passes).

        Args:
            ctx: The benchmark context.
        """
        self.release.wait(3600)

    def conclude(self, ctx: Context) -> None:
        """Release the blocked sample, as a real benchmark would kill its process tree.

        Args:
            ctx: The benchmark context.
        """
        self.release.set()


def app_env(ctx: Context) -> dict[str, str]:
    """Build the environment of the app self-tests.

    Args:
        ctx: The benchmark context.

    Returns:
        ``ctx.env`` with reflex's data directory (bun, templates) in the cache
        directory, so the first ``setup_cache`` is a cold start and later runs
        are warm.
    """
    return {**ctx.env, **cache_env(reflex_dir=ctx.cache_dir / "reflex")}


def init_app(ctx: Context) -> Path:
    """Create a blank app in the cache directory unless it is there.

    Args:
        ctx: The benchmark context.

    Returns:
        The app directory.
    """
    app = ctx.cache_dir / "app"
    if not (app / "rxconfig.py").is_file():
        app.mkdir(parents=True, exist_ok=True)
        run_cli(
            ctx.subject.python,
            ["init", "--template", "blank"],
            cwd=app,
            env=app_env(ctx),
            timeout=APP_TIMEOUT_S,
        ).check()
    return app


@benchmark(
    id="selftest.app.compile",
    suites=("selftest",),
    metrics={
        "wall": Metric(unit="s", direction="lower"),
        "cpu": Metric(unit="s", direction="lower"),
        "peak_mem": Metric(unit="B", direction="lower"),
    },
    timeout=APP_TIMEOUT_S + 60,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=3,
)
class AppCompile:
    """Compile a blank app with `reflex compile`; checks run_cli and the collectors."""

    def setup_cache(self, ctx: Context) -> None:
        """Create the app.

        Args:
            ctx: The benchmark context.
        """
        init_app(ctx)

    def sample(self, ctx: Context) -> SampleResult:
        """Compile once, in a cgroup scope when the host has one, else sampling PSS.

        Args:
            ctx: The benchmark context.

        Returns:
            Wall, CPU and peak memory of the whole tree, with the phase
            attribution and the collector details as extra data.

        Raises:
            RuntimeError: When no memory collector works on this host.
        """
        scope = CgroupScope() if CgroupScope.available() is None else None
        result = run_cli(
            ctx.subject.python,
            ["compile"],
            cwd=ctx.cache_dir / "app",
            env=app_env(ctx),
            timeout=APP_TIMEOUT_S,
            scope=scope,
            phases=True,
            sample_memory=scope is None,
        ).check()
        if result.cgroup is not None:
            peak, memory = (
                result.cgroup.memory_peak_bytes,
                dataclasses.asdict(result.cgroup),
            )
        elif result.pss is not None:
            peak, memory = result.pss.peak_bytes, result.pss.to_dict()
        else:
            msg = "no memory collector measured the compile"
            raise RuntimeError(msg)
        return SampleResult(
            {"wall": result.wall_s, "cpu": result.cpu_s, "peak_mem": peak},
            extra={
                "phases": result.attribution(),
                "timing": result.timing,
                "tree": result.tree.to_dict() if result.tree is not None else None,
                "cpu_method": result.cpu_method,
                "memory_method": result.memory_method,
                "memory": memory,
            },
        )


@benchmark(
    id="selftest.app.dev_ready",
    suites=("selftest",),
    kind="startup",
    metrics={
        "process_ready": Metric(unit="s", direction="lower"),
        "http_ready": Metric(unit="s", direction="lower"),
    },
    timeout=APP_TIMEOUT_S,
    setup_timeout=APP_TIMEOUT_S + 60,
    estimate=5,
)
class AppDevReady:
    """Start a blank app with `reflex run` in dev mode until it serves HTTP; checks AppProcess."""

    app: AppProcess | None = None

    def setup_cache(self, ctx: Context) -> None:
        """Create the app.

        Args:
            ctx: The benchmark context.
        """
        init_app(ctx)

    def sample(self, ctx: Context) -> dict[str, float]:
        """Start the app and wait for tiers 1 and 2; conclude() stops it.

        Args:
            ctx: The benchmark context.

        Returns:
            Seconds from the spawn to process-ready and to HTTP-ready.
        """
        # conclude() may run on another thread after a timeout and clear self.app.
        app = self.app = AppProcess(
            ctx.subject.python,
            ctx.cache_dir / "app",
            mode="dev",
            reflex_version=ctx.subject.reflex_version,
            env=app_env(ctx),
        )
        readiness = app.start()
        http_ready = app.wait_http_ready()
        return {"process_ready": readiness.process_ready, "http_ready": http_ready}

    def conclude(self, ctx: Context) -> None:
        """Kill the app's process tree, also after a failed or timed-out sample.

        Args:
            ctx: The benchmark context.
        """
        if self.app is not None:
            self.app.stop()
            self.app = None
