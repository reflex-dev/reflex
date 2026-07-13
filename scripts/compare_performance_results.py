"""Compare performance report JSON files against a baseline run.

Matches results across two directories of ``PerformanceReport`` JSON files by
suite, benchmark name, and parameters, then flags latency-percentile and byte
regressions with warn/fail thresholds. Absolute floors keep tiny baselines
from flagging noise: a change must exceed both the percentage threshold and
the floor to count. Comparisons across materially different environments are
reported as informational and never fail.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_WARN_PCT = 25.0
DEFAULT_FAIL_PCT = 50.0
DEFAULT_FLOOR_MS = 5.0
DEFAULT_FLOOR_BYTES = 1_024
# Process and heap measurements are inherently noisy; require a much larger
# absolute change than deterministic byte metrics like wire or bundle size.
MEMORY_FLOOR_BYTES = 5_242_880
MEMORY_METRIC_PREFIXES = ("rss_", "heap_")

COMPARED_PERCENTILES = ("p50_ms", "p95_ms", "p99_ms")
ENVIRONMENT_KEYS = ("python", "implementation", "operating_system", "machine")


@dataclasses.dataclass(frozen=True)
class Finding:
    """One compared metric and its regression status."""

    benchmark: str
    metric: str
    baseline: float
    current: float
    change_pct: float
    status: str

    def render(self) -> str:
        """Format the finding for terminal output.

        Returns:
            One aligned report line.
        """
        return (
            f"{self.status.upper():<6} {self.benchmark} {self.metric}: "
            f"{self.baseline:.2f} -> {self.current:.2f} ({self.change_pct:+.1f}%)"
        )


def load_reports(directory: Path) -> dict[str, dict[str, Any]]:
    """Index benchmark results from every report file in a directory.

    Args:
        directory: Directory containing ``PerformanceReport`` JSON files.

    Returns:
        Results keyed by suite, benchmark name, and canonical parameters.
    """
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "schema_version" not in data:
            continue
        for result in data.get("results", []):
            key = "|".join([
                data.get("suite", path.stem),
                result["name"],
                json.dumps(result.get("parameters", {}), sort_keys=True),
            ])
            index[key] = result | {"environment": data.get("environment", {})}
    return index


def environments_match(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    """Check whether two results were produced in comparable environments.

    Args:
        baseline: Baseline result with attached environment.
        current: Current result with attached environment.

    Returns:
        Whether the interpreter and platform identifiers all match.
    """
    baseline_env = baseline.get("environment", {})
    current_env = current.get("environment", {})
    return all(
        baseline_env.get(key) == current_env.get(key) for key in ENVIRONMENT_KEYS
    )


def _classify(
    baseline: float,
    current: float,
    floor: float,
    warn_pct: float,
    fail_pct: float,
) -> tuple[float, str]:
    """Classify one metric change; lower values are always better.

    Args:
        baseline: Baseline value.
        current: Current value.
        floor: Minimum absolute increase considered meaningful.
        warn_pct: Percentage increase that warns.
        fail_pct: Percentage increase that fails.

    Returns:
        Percentage change and status (``ok``, ``warn``, or ``fail``).
    """
    if baseline <= 0:
        return 0.0, "ok"
    change_pct = (current - baseline) / baseline * 100
    if current - baseline < floor:
        return change_pct, "ok"
    if change_pct >= fail_pct:
        return change_pct, "fail"
    if change_pct >= warn_pct:
        return change_pct, "warn"
    return change_pct, "ok"


def compare(
    baseline: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    *,
    warn_pct: float = DEFAULT_WARN_PCT,
    fail_pct: float = DEFAULT_FAIL_PCT,
    floor_ms: float = DEFAULT_FLOOR_MS,
    floor_bytes: float = DEFAULT_FLOOR_BYTES,
) -> list[Finding]:
    """Compare matched benchmark results between two runs.

    Latency percentiles are compared for results with observations; metrics
    named ``*_bytes`` are compared with the byte floor, raised to
    ``MEMORY_FLOOR_BYTES`` for noisy process-memory metrics. Counts, ratios,
    and unmatched benchmarks are ignored.

    Args:
        baseline: Indexed baseline results.
        current: Indexed current results.
        warn_pct: Percentage increase that warns.
        fail_pct: Percentage increase that fails.
        floor_ms: Minimum meaningful latency increase in milliseconds.
        floor_bytes: Minimum meaningful byte increase.

    Returns:
        Findings for every compared metric, in report order.
    """
    findings: list[Finding] = []
    for key in sorted(baseline.keys() & current.keys()):
        baseline_result, current_result = baseline[key], current[key]
        comparisons: list[tuple[str, float, float, float]] = []
        if baseline_result.get("observations_ms") and current_result.get(
            "observations_ms"
        ):
            comparisons.extend(
                (
                    name,
                    baseline_result["summary"][name],
                    current_result["summary"][name],
                    floor_ms,
                )
                for name in COMPARED_PERCENTILES
            )
        baseline_metrics = baseline_result.get("metrics", {})
        current_metrics = current_result.get("metrics", {})
        comparisons.extend(
            (
                name,
                baseline_metrics[name],
                current_metrics[name],
                max(floor_bytes, MEMORY_FLOOR_BYTES)
                if name.startswith(MEMORY_METRIC_PREFIXES)
                else floor_bytes,
            )
            for name in sorted(baseline_metrics.keys() & current_metrics.keys())
            if name.endswith("_bytes")
        )
        for metric, baseline_value, current_value, floor in comparisons:
            change_pct, status = _classify(
                baseline_value, current_value, floor, warn_pct, fail_pct
            )
            findings.append(
                Finding(key, metric, baseline_value, current_value, change_pct, status)
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Compare two performance result directories.

    Args:
        argv: Command-line arguments, defaulting to ``sys.argv``.

    Returns:
        Process exit code: 1 when comparable environments show a failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="baseline results directory")
    parser.add_argument("current", type=Path, help="current results directory")
    parser.add_argument("--warn-pct", type=float, default=DEFAULT_WARN_PCT)
    parser.add_argument("--fail-pct", type=float, default=DEFAULT_FAIL_PCT)
    parser.add_argument("--floor-ms", type=float, default=DEFAULT_FLOOR_MS)
    parser.add_argument("--floor-bytes", type=float, default=DEFAULT_FLOOR_BYTES)
    args = parser.parse_args(argv)

    baseline = load_reports(args.baseline)
    current = load_reports(args.current)
    if not baseline or not current:
        print("No comparable reports found; skipping comparison.")
        return 0

    findings = compare(
        baseline,
        current,
        warn_pct=args.warn_pct,
        fail_pct=args.fail_pct,
        floor_ms=args.floor_ms,
        floor_bytes=args.floor_bytes,
    )
    comparable = all(
        environments_match(baseline[key], current[key])
        for key in baseline.keys() & current.keys()
    )
    for finding in findings:
        if finding.status != "ok":
            print(finding.render())
    regressions = [finding for finding in findings if finding.status == "fail"]
    print(
        f"Compared {len(findings)} metrics: "
        f"{len(regressions)} fail, "
        f"{sum(finding.status == 'warn' for finding in findings)} warn."
    )
    if not comparable:
        print("Environments differ; comparison is informational only.")
        return 0
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
