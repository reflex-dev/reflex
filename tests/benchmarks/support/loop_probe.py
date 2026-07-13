"""Wall-time probes for asyncio performance benchmarks."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import TracebackType

from .report import percentile


@dataclass
class EventLoopProbe:
    """Sample event-loop lag, tasks, and benchmark-specific gauges."""

    interval: float = 0.01
    gauges: Mapping[str, Callable[[], int]] = field(default_factory=dict)
    lag_samples: list[float] = field(default_factory=list, init=False)
    task_samples: list[int] = field(default_factory=list, init=False)
    gauge_samples: dict[str, list[int]] = field(default_factory=dict, init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    @property
    def peak_tasks(self) -> int:
        """Return the largest observed live-task count.

        Returns:
            Peak live tasks.
        """
        return max(self.task_samples, default=0)

    async def __aenter__(self) -> EventLoopProbe:
        """Start sampling and allow the sampler task to initialize.

        Returns:
            The running probe.
        """
        if self.interval <= 0:
            msg = "Event-loop probe interval must be greater than zero."
            raise ValueError(msg)
        self.lag_samples.clear()
        self.task_samples.clear()
        self.gauge_samples = {name: [] for name in self.gauges}
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
        """Record scheduling delay, tasks, and custom gauges."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.interval
        while True:
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            now = loop.time()
            self.lag_samples.append(max(0.0, now - deadline))
            self.task_samples.append(len(asyncio.all_tasks(loop)))
            for name, gauge in self.gauges.items():
                self.gauge_samples[name].append(gauge())
            deadline = max(deadline + self.interval, now + self.interval)

    def summary(self) -> dict[str, float | int]:
        """Return stable summary fields for benchmark JSON output.

        Returns:
            Sample count, peak tasks, custom gauge peaks, and lag percentiles.
        """
        summary: dict[str, float | int] = {
            "sample_count": len(self.lag_samples),
            "peak_tasks": self.peak_tasks,
            "lag_p50_ms": percentile(self.lag_samples, 50) * 1000,
            "lag_p95_ms": percentile(self.lag_samples, 95) * 1000,
            "lag_p99_ms": percentile(self.lag_samples, 99) * 1000,
            "lag_max_ms": max(self.lag_samples, default=0.0) * 1000,
        }
        summary.update({
            f"peak_{name}": max(samples, default=0)
            for name, samples in self.gauge_samples.items()
        })
        return summary
