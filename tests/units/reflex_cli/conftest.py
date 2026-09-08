"""Shared fixtures for reflex_cli tests."""

import pytest
from pytest_mock import MockFixture
from reflex_cli import constants


@pytest.fixture(autouse=True)
def mock_check_version(mocker: MockFixture) -> None:
    """Bypass the hosting-cli PyPI version check during tests.

    The workspace build reports a dev version older than the published one,
    causing `check_version` to emit a warning and exit(1).
    """
    mocker.patch("reflex_cli.v2.deployments.check_version")


@pytest.fixture(autouse=True)
def isolate_hosting_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point the hosting config at a temporary directory.

    Several code paths under test write or delete the token file for real, so
    without this a test run destroys the developer's own `reflex login` state.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path_factory: The pytest temporary directory factory.
    """
    reflex_dir = tmp_path_factory.mktemp("reflex_data")
    monkeypatch.setattr(constants.Reflex, "DIR", str(reflex_dir))
    monkeypatch.setattr(
        constants.Hosting, "HOSTING_JSON", reflex_dir / "hosting_v1.json"
    )
    monkeypatch.setattr(
        constants.Hosting, "HOSTING_JSON_V0", reflex_dir / "hosting_v0.json"
    )
