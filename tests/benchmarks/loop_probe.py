"""Wall-time probes for asyncio performance benchmarks."""

import asyncio
import contextlib
from dataclasses import dataclass, field
from types import TracebackType


@dataclass
class EventLoopProbe:
    """Sample event-loop lag and live task count during a workload."""

    interval: float = 0.01
    lag_samples: list[float] = field(default_factory=list, init=False)
    peak_tasks: int = field(default=0, init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "EventLoopProbe":
        """Start sampling and allow the sampler task to initialize.

        Returns:
            The running probe.
        """
        if self.interval <= 0:
            msg = "Event-loop probe interval must be greater than zero."
            raise ValueError(msg)
        self.lag_samples.clear()
        self.peak_tasks = 0
        self._task = asyncio.create_task(
            self._sample(),
            name="reflex_benchmark_event_loop_probe",
        )
        await asyncio.sleep(0)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the sampler.

        Args:
            exc_type: Exception type raised by the measured workload, if any.
            exc_value: Exception raised by the measured workload, if any.
            traceback: Traceback raised by the measured workload, if any.
        """
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _sample(self) -> None:
        """Record scheduling delay and the number of live tasks."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.interval
        while True:
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            now = loop.time()
            self.lag_samples.append(max(0.0, now - deadline))
            self.peak_tasks = max(self.peak_tasks, len(asyncio.all_tasks(loop)))
            deadline = max(deadline + self.interval, now + self.interval)

    def summary(self) -> dict[str, float | int]:
        """Return stable summary fields for benchmark JSON output.

        Returns:
            Sample count, peak tasks, and event-loop lag percentiles in milliseconds.
        """
        return {
            "sample_count": len(self.lag_samples),
            "peak_tasks": self.peak_tasks,
            "lag_p50_ms": self._percentile(50) * 1000,
            "lag_p95_ms": self._percentile(95) * 1000,
            "lag_p99_ms": self._percentile(99) * 1000,
            "lag_max_ms": max(self.lag_samples, default=0.0) * 1000,
        }

    def _percentile(self, percentile: float) -> float:
        """Calculate a linearly interpolated lag percentile.

        Args:
            percentile: Percentile in the inclusive range 0 through 100.

        Returns:
            The percentile lag in seconds, or zero when there are no samples.
        """
        if not self.lag_samples:
            return 0.0
        values = sorted(self.lag_samples)
        position = (len(values) - 1) * percentile / 100
        lower_index = int(position)
        upper_index = min(lower_index + 1, len(values) - 1)
        fraction = position - lower_index
        return (
            values[lower_index] + (values[upper_index] - values[lower_index]) * fraction
        )
