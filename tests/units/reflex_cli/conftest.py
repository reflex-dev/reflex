"""Shared fixtures for reflex_cli tests."""

import pytest
from pytest_mock import MockFixture


@pytest.fixture(autouse=True)
def mock_check_version(mocker: MockFixture) -> None:
    """Bypass the hosting-cli PyPI version check during tests.

    The workspace build reports a dev version older than the published one,
    causing `check_version` to emit a warning and exit(1).
    """
    mocker.patch("reflex_cli.v2.deployments.check_version")
