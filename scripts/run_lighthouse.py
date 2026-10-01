"""Run the local Lighthouse benchmark with a fresh app build."""

from __future__ import annotations

import shutil
from pathlib import Path

from reflex_base import constants

from tests.integration.lighthouse_utils import (
    LIGHTHOUSE_LANDING_APP_NAME,
    run_landing_prod_lighthouse_benchmark,
)


def main() -> int:
    """Run the Lighthouse benchmark and print a compact summary.

    Returns:
        The process exit code.
    """
    scratch_root = Path(constants.Dirs.STATES)
    report_dir = scratch_root / "lighthouse"
    app_root = scratch_root / LIGHTHOUSE_LANDING_APP_NAME
    shutil.rmtree(app_root, ignore_errors=True)

    result = run_landing_prod_lighthouse_benchmark(
        app_root=app_root,
        report_path=report_dir / "landing-prod-lighthouse.json",
    )
    print(result.summary)  # noqa: T201
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
