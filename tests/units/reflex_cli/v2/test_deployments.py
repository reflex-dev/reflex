import importlib.metadata
from unittest.mock import MagicMock

import click
import httpx
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.v2.deployments import check_version


@pytest.mark.parametrize(
    "installed_version, latest_version, should_exit",
    [
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "2.0.0", True),
    ],
)
def test_check_version(
    mocker: MockerFixture,
    installed_version: str,
    latest_version: str,
    should_exit: bool,
):
    mocker.patch(
        "importlib.metadata.version",
        return_value=installed_version,
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"info": {"version": latest_version}}
    mocker.patch("httpx.get", return_value=mock_response)
    mock_console_error = mocker.patch("reflex_cli.utils.console.error")

    if should_exit:
        with pytest.raises(click.exceptions.Exit) as excinfo:
            check_version()
        assert excinfo.value.exit_code == 1
        mock_console_error.assert_called_once_with(
            "Warning: You are using reflex-hosting-cli version 1.0.0. A newer version 2.0.0 is available. Upgrade using: pip install --upgrade reflex-hosting-cli"
        )
    else:
        check_version()
        mock_console_error.assert_not_called()


def test_check_version_distribution_not_found(mocker: MockFixture):
    mocker.patch(
        "importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    )
    mock_httpx_get = mocker.patch("httpx.get")

    check_version()
    mock_httpx_get.assert_not_called()


def test_check_version_request_exception(mocker: MockFixture):
    mocker.patch("importlib.metadata.version", return_value=MagicMock(version="1.0.0"))
    mocker.patch("httpx.get", side_effect=httpx.RequestError("Request failed"))
    check_version()


def test_check_version_http_status_error(mocker: MockFixture):
    mocker.patch("importlib.metadata.version", return_value=MagicMock(version="1.0.0"))
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP error", request=MagicMock(), response=MagicMock()
    )
    mocker.patch("httpx.get", return_value=mock_response)
    check_version()
