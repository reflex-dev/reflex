"""Configuration for scheduled performance suites."""

from pathlib import Path

import pytest


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


@pytest.fixture
def performance_scale(request: pytest.FixtureRequest) -> str:
    """Return the selected scenario scale.

    Args:
        request: Pytest fixture request.

    Returns:
        ``smoke`` or ``release``.
    """
    return request.config.getoption("--performance-scale")
