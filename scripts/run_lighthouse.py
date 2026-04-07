"""Run the local Lighthouse benchmark with persistent caching."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from tests.integration.lighthouse_utils import (
    get_local_cached_app_root,
    run_blank_prod_lighthouse_benchmark,
)


def main() -> int:
    """Run the Lighthouse benchmark and print a compact summary.

    Returns:
        The process exit code.
    """
    app_root = get_local_cached_app_root()
    report_path = Path(".states") / "lighthouse" / "blank-prod-lighthouse.json"

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with (
        contextlib.redirect_stdout(stdout_buffer),
        contextlib.redirect_stderr(stderr_buffer),
    ):
        result = run_blank_prod_lighthouse_benchmark(
            app_root=app_root,
            report_path=report_path,
        )

    print(result.summary)  # noqa: T201
    if result.failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
