"""Lighthouse benchmark tests for production Reflex apps."""

from __future__ import annotations

from pathlib import Path

import pytest

from .lighthouse_utils import (
    run_landing_prod_lighthouse_benchmark,
    should_run_lighthouse,
)

pytestmark = pytest.mark.skipif(
    not should_run_lighthouse(),
    reason="Set REFLEX_RUN_LIGHTHOUSE=1 to run Lighthouse benchmark tests.",
)


@pytest.fixture(scope="module")
def lighthouse_landing_app_root(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Get the app root for the landing-page Lighthouse benchmark.

    Args:
        tmp_path_factory: Pytest helper for allocating temporary directories.

    Returns:
        The app root path for the landing-page benchmark app.
    """
    return tmp_path_factory.mktemp("lighthouse_landing_app")


def test_landing_page_lighthouse_scores(
    lighthouse_landing_app_root: Path,
    tmp_path: Path,
):
    """Assert that a single-page landing app stays in the 90s across Lighthouse categories."""
    result = run_landing_prod_lighthouse_benchmark(
        app_root=lighthouse_landing_app_root,
        report_path=tmp_path / "landing-prod-lighthouse.json",
    )
    print(result.summary)

    if result.failures:
        pytest.fail(
            "Lighthouse thresholds not met. See score summary above.",
            pytrace=False,
        )
