"""Self-test benchmarks: they exercise the harness itself, without reflex.

Only the ``selftest`` suite contains them, so they stay out of ``list`` and
``run`` unless asked for with ``--suite selftest`` or a ``selftest.*`` filter.
"""

from __future__ import annotations

import math
import random
import threading
import time

from reflex_bench.context import Context
from reflex_bench.registry import Metric, benchmark

WALL = {"wall": Metric(unit="s", direction="lower")}


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
    estimate=0.5,
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
