"""Versioned result schema for wall-time and load benchmarks."""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def percentile(values: Sequence[float], value: float) -> float:
    """Return a linearly interpolated percentile.

    Args:
        values: Numeric observations.
        value: Percentile in the inclusive range 0 through 100.

    Returns:
        The interpolated percentile, or zero for an empty sequence.

    Raises:
        ValueError: If the requested percentile is outside the valid range.
    """
    if not 0 <= value <= 100:
        msg = "Percentile must be between 0 and 100."
        raise ValueError(msg)
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * value / 100
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return (
        ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction
    )


def _git_value(*args: str) -> str | None:
    """Read a value from the current Git checkout when available.

    Args:
        args: Arguments following ``git``.

    Returns:
        Stripped command output, or ``None`` outside a Git checkout.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


@dataclasses.dataclass(frozen=True)
class BenchmarkEnvironment:
    """Runtime and repository metadata attached to a performance report."""

    commit: str | None
    branch: str | None
    python: str
    implementation: str
    operating_system: str
    machine: str
    processor: str
    cpu_count: int | None
    ci: bool

    @classmethod
    def detect(cls) -> BenchmarkEnvironment:
        """Detect the current performance environment.

        Returns:
            Environment metadata suitable for cross-run validation.
        """
        return cls(
            commit=os.environ.get("GITHUB_SHA") or _git_value("rev-parse", "HEAD"),
            branch=os.environ.get("GITHUB_HEAD_REF")
            or os.environ.get("GITHUB_REF_NAME")
            or _git_value("branch", "--show-current"),
            python=platform.python_version(),
            implementation=platform.python_implementation(),
            operating_system=platform.platform(),
            machine=platform.machine(),
            processor=platform.processor(),
            cpu_count=os.cpu_count(),
            ci=os.environ.get("CI", "").lower() == "true",
        )


@dataclasses.dataclass(frozen=True)
class BenchmarkResult:
    """One parameterized performance benchmark result."""

    name: str
    parameters: Mapping[str, Any]
    observations_ms: Sequence[float]
    metrics: Mapping[str, float | int]
    warmup_iterations: int = 0
    measurement_iterations: int = 1

    def summary(self) -> dict[str, float | int]:
        """Summarize the benchmark's latency observations.

        Returns:
            Count and common latency percentiles in milliseconds.
        """
        values = self.observations_ms
        return {
            "count": len(values),
            "mean_ms": sum(values) / len(values) if values else 0.0,
            "p50_ms": percentile(values, 50),
            "p90_ms": percentile(values, 90),
            "p95_ms": percentile(values, 95),
            "p99_ms": percentile(values, 99),
            "max_ms": max(values, default=0.0),
        }

    def as_dict(self) -> dict[str, Any]:
        """Serialize this result.

        Returns:
            A JSON-compatible result mapping.
        """
        return {
            "name": self.name,
            "parameters": dict(self.parameters),
            "warmup_iterations": self.warmup_iterations,
            "measurement_iterations": self.measurement_iterations,
            "observations_ms": list(self.observations_ms),
            "summary": self.summary(),
            "metrics": dict(self.metrics),
        }


@dataclasses.dataclass
class PerformanceReport:
    """Collection of results produced in one benchmark environment."""

    suite: str
    results: list[BenchmarkResult] = dataclasses.field(default_factory=list)
    environment: BenchmarkEnvironment = dataclasses.field(
        default_factory=BenchmarkEnvironment.detect
    )
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def add(self, result: BenchmarkResult) -> None:
        """Append a benchmark result.

        Args:
            result: Result to append.
        """
        self.results.append(result)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the report.

        Returns:
            A JSON-compatible report mapping.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "suite": self.suite,
            "environment": dataclasses.asdict(self.environment),
            "metadata": self.metadata,
            "results": [result.as_dict() for result in self.results],
        }

    def write(self, path: str | Path) -> Path:
        """Write the report as deterministic formatted JSON.

        Args:
            path: Destination path.

        Returns:
            The resolved destination path.
        """
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def current_process_metrics() -> dict[str, int]:
    """Return portable process resource metrics.

    Returns:
        Resident memory, thread count, and process ID.
    """
    import psutil

    process = psutil.Process()
    return {
        "pid": process.pid,
        "rss_bytes": process.memory_info().rss,
        "threads": process.num_threads(),
    }


def runtime_metadata() -> dict[str, str]:
    """Return additional runtime identifiers when installed.

    Returns:
        Node and Redis version strings when their commands are available.
    """
    metadata = {"python_executable": sys.executable}
    for name, command in {
        "node": ["node", "--version"],
        "redis": ["redis-server", "--version"],
    }.items():
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        metadata[name] = (result.stdout or result.stderr).strip()
    return metadata
