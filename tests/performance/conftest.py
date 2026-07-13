"""Configuration for scheduled performance suites."""

from collections.abc import Generator
from pathlib import Path

import pytest

from reflex.testing import AppHarness, AppHarnessProd
from tests.benchmarks.support.apps import load_app_source


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register explicit performance-suite options.

    Args:
        parser: Pytest command-line parser.
    """
    group = parser.getgroup("performance")
    group.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="run scheduled performance tests",
    )
    group.addoption(
        "--performance-output",
        default=".pytest-tmp/performance",
        help="directory for performance JSON, traces, and profiles",
    )
    group.addoption(
        "--performance-scale",
        choices=("smoke", "release"),
        default="smoke",
        help="performance scenario scale",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip scheduled performance tests unless explicitly enabled.

    Args:
        config: Active Pytest configuration.
        items: Collected tests.
    """
    if config.getoption("--run-performance"):
        return
    skip = pytest.mark.skip(reason="pass --run-performance to execute this suite")
    for item in items:
        if "performance" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def performance_output(request: pytest.FixtureRequest) -> Path:
    """Return and create the performance artifact directory.

    Args:
        request: Pytest fixture request.

    Returns:
        Artifact directory.
    """
    output = Path(request.config.getoption("--performance-output")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    return output


@pytest.fixture(scope="module")
def performance_load_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Build and run the representative production load application per module.

    Module scope amortizes the production build within related scenarios while
    stopping the in-process servers before unrelated benchmark modules run.

    Args:
        tmp_path_factory: Pytest temporary directory factory.

    Yields:
        Running production app harness.
    """
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("performance_load"),
        app_source=load_app_source(),
        app_name="performance_load",
    ) as harness:
        yield harness


@pytest.fixture
def performance_scale(request: pytest.FixtureRequest) -> str:
    """Return the selected scenario scale.

    Args:
        request: Pytest fixture request.

    Returns:
        ``smoke`` or ``release``.
    """
    return request.config.getoption("--performance-scale")
