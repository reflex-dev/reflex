"""Shared fixtures for reflex_cli tests."""

import pytest
from pytest_mock import MockFixture
from reflex_cli.constants.hosting import ReflexHostingCli


@pytest.fixture(autouse=True)
def mock_check_version(mocker: MockFixture) -> None:
    """Bypass the hosting-cli context and PyPI version check during tests.

    The workspace build reports a dev version older than the published one,
    causing `check_version` to emit a warning and exit(1).
    """
    mocker.patch(
        "reflex_cli.v2.deployments._reflex_version",
        ReflexHostingCli.RECOMMENDED_REFLEX_VERSION,
    )
    mocker.patch("reflex_cli.v2.deployments.check_version")
