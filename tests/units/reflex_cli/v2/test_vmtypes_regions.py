import json
import logging

import httpx
import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.v2.deployments import hosting_cli

from .utils import as_click_command

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()


def test_get_vm_types_success(mocker: MockFixture):
    """Test successful retrieval of VM types."""
    mock_get_vm_types = mocker.patch(
        "reflex_cli.utils.hosting.get_vm_types",
        return_value=[
            {"id": "1", "name": "Small", "cpu": 2, "ram": 4},
            {"id": "2", "name": "Medium", "cpu": 4, "ram": 8},
        ],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["vmtypes"])

    assert result.exit_code == 0, result.output
    mock_get_vm_types.assert_called_once()
    mock_console_print_table.assert_called_once_with(
        [
            ["1", "Small", "2", "4"],
            ["2", "Medium", "4", "8"],
        ],
        headers=["id", "name", "cpu (cores)", "ram (gb)"],
    )


def test_get_vm_types_as_json(mocker: MockFixture):
    """Test retrieval of VM types with JSON output."""
    mock_get_vm_types = mocker.patch(
        "reflex_cli.utils.hosting.get_vm_types",
        return_value=[
            {"id": "1", "name": "Small", "cpu": 2, "ram": 4},
            {"id": "2", "name": "Medium", "cpu": 4, "ram": 8},
        ],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["vmtypes", "--json"])

    assert result.exit_code == 0, result.output
    mock_get_vm_types.assert_called_once()
    mock_console_print.assert_called_once_with(
        '[{"id": "1", "name": "Small", "cpu": 2, "ram": 4}, {"id": "2", "name": "Medium", "cpu": 4, "ram": 8}]'
    )


def test_get_vm_types_empty(mocker: MockFixture):
    """Test retrieval when no VM types are available."""
    mock_get_vm_types = mocker.patch(
        "reflex_cli.utils.hosting.get_vm_types", return_value=[]
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["vmtypes"])

    assert result.exit_code == 0, result.output
    mock_get_vm_types.assert_called_once()
    mock_console_print.assert_called_once_with("[]")


def test_get_vm_types_invalid_response(mocker: MockFixture):
    """Test handling of invalid server response."""
    mock_get_vm_types = mocker.patch(
        "reflex_cli.utils.hosting.get_vm_types",
        return_value=[{"invalid_key": "value"}],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["vmtypes"])

    assert result.exit_code == 0, result.output
    mock_get_vm_types.assert_called_once()
    # Expect the invalid key will not match the displayed table
    mock_console_print_table.assert_called_once_with(
        [[]], headers=["id", "name", "cpu (cores)", "ram (gb)"]
    )


def test_get_vm_types_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test handling of an HTTP error.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_get.return_value = mock_response
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    mock_console_print = mocker.patch("reflex_cli.utils.console.print")
    result = runner.invoke(hosting_cli, ["vmtypes"])

    assert result.exit_code == 0, result.output
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to get vmtypes due to HTTP Error."]
    mock_console_print.assert_called_once_with("[]")


def test_get_deployment_regions_success(mocker: MockerFixture):
    """Test successful retrieval of regions with table output."""
    mock_get_regions = mocker.patch(
        "reflex_cli.utils.hosting.get_regions",
        return_value=[
            {"name": "Amsterdam, Netherlands", "code": "ams"},
            {"name": "Stockholm, Sweden", "code": "arn"},
        ],
    )
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["regions"])

    assert result.exit_code == 0, result.output
    mock_get_regions.assert_called_once()
    mock_print_table.assert_called_once_with(
        [["Amsterdam, Netherlands", "ams"], ["Stockholm, Sweden", "arn"]],
        headers=["name", "code"],
    )


def test_get_deployment_regions_as_json(mocker: MockFixture):
    """Test successful retrieval of regions with JSON output."""
    mock_get_regions = mocker.patch(
        "reflex_cli.utils.hosting.get_regions",
        return_value=[
            {"name": "Amsterdam, Netherlands", "code": "ams"},
            {"name": "Stockholm, Sweden", "code": "arn"},
        ],
    )
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["regions", "--json"])

    assert result.exit_code == 0, result.output
    mock_get_regions.assert_called_once()
    mock_print.assert_called_once_with(
        json.dumps([
            {"name": "Amsterdam, Netherlands", "code": "ams"},
            {"name": "Stockholm, Sweden", "code": "arn"},
        ])
    )


def test_get_deployment_regions_empty(mocker: MockFixture):
    """Test retrieval when no regions are available."""
    mock_get_regions = mocker.patch(
        "reflex_cli.utils.hosting.get_regions",
        return_value=[],
    )
    mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["regions"])

    assert result.exit_code == 0, result.output
    mock_get_regions.assert_called_once()


def test_get_deployment_regions_http_error(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """Test handling of an HTTP error.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_get.return_value = mock_response
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["regions"])

    assert result.exit_code == 0, result.output
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to get regions due to HTTP Error."]
