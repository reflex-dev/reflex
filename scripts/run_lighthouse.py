"""Run the local Lighthouse benchmark with a fresh app build."""

from __future__ import annotations

import contextlib
import io
import shutil
from collections.abc import Callable
from pathlib import Path

from tests.integration.lighthouse_utils import (
    LIGHTHOUSE_APP_NAME,
    LIGHTHOUSE_LANDING_APP_NAME,
    LighthouseBenchmarkResult,
    run_blank_prod_lighthouse_benchmark,
    run_landing_prod_lighthouse_benchmark,
)


def _run_benchmark(
    run_fn: Callable[..., LighthouseBenchmarkResult],
    app_root: Path,
    report_path: Path,
) -> LighthouseBenchmarkResult:
    """Run a single benchmark, suppressing internal output.

    Returns:
        The benchmark result.
    """
    shutil.rmtree(app_root, ignore_errors=True)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with (
        contextlib.redirect_stdout(stdout_buffer),
        contextlib.redirect_stderr(stderr_buffer),
    ):
        return run_fn(app_root=app_root, report_path=report_path)


def main() -> int:
    """Run the Lighthouse benchmarks and print compact summaries.

    Returns:
        The process exit code.
    """
    report_dir = Path(".states") / "lighthouse"
    all_failures = []

    benchmarks = [
        (
            LIGHTHOUSE_APP_NAME,
            run_blank_prod_lighthouse_benchmark,
            report_dir / "blank-prod-lighthouse.json",
        ),
        (
            LIGHTHOUSE_LANDING_APP_NAME,
            run_landing_prod_lighthouse_benchmark,
            report_dir / "landing-prod-lighthouse.json",
        ),
    ]

    for name, run_fn, report_path in benchmarks:
        app_root = Path(".states") / name
        result = _run_benchmark(run_fn, app_root, report_path)
        print(result.summary)  # noqa: T201
        print()  # noqa: T201
        all_failures.extend(result.failures)

    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
