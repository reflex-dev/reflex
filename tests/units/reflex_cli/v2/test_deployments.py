import importlib.metadata
import logging
import sys
from unittest.mock import MagicMock

import click
import httpx2
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.v2.deployments import check_version


def test_check_version_without_httpx(mocker: MockerFixture):
    """Version checks work when the legacy HTTP client is not installed.

    Args:
        mocker: The pytest-mock fixture.
    """
    mocker.patch.dict(sys.modules, {"httpx": None})
    mocker.patch("importlib.metadata.version", return_value="1.0.0")
    request = httpx2.Request("GET", "https://pypi.org/pypi/reflex-hosting-cli/json")
    response = httpx2.Response(
        200, request=request, json={"info": {"version": "1.0.0"}}
    )
    get = mocker.patch("httpx2.get", return_value=response)

    check_version()

    get.assert_called_once_with("https://pypi.org/pypi/reflex-hosting-cli/json")


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
    caplog: pytest.LogCaptureFixture,
):
    mocker.patch(
        "importlib.metadata.version",
        return_value=installed_version,
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"info": {"version": latest_version}}
    mocker.patch("httpx2.get", return_value=mock_response)

    if should_exit:
        with pytest.raises(click.exceptions.Exit) as excinfo:
            check_version()
        assert excinfo.value.exit_code == 1
        errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert errors == [
            "Warning: You are using reflex-hosting-cli version 1.0.0. A newer version 2.0.0 is available. Upgrade using: pip install --upgrade reflex-hosting-cli"
        ]
    else:
        check_version()
        errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert errors == []


def test_check_version_distribution_not_found(mocker: MockFixture):
    mocker.patch(
        "importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    )
    mock_httpx2_get = mocker.patch("httpx2.get")

    check_version()
    mock_httpx2_get.assert_not_called()


def test_check_version_request_exception(mocker: MockFixture):
    mocker.patch("importlib.metadata.version", return_value=MagicMock(version="1.0.0"))
    mocker.patch("httpx2.get", side_effect=httpx2.RequestError("Request failed"))
    check_version()


def test_check_version_http_status_error(mocker: MockFixture):
    mocker.patch("importlib.metadata.version", return_value=MagicMock(version="1.0.0"))
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        "HTTP error", request=MagicMock(), response=MagicMock()
    )
    mocker.patch("httpx2.get", return_value=mock_response)
    check_version()
