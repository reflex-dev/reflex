from __future__ import annotations

import json
from unittest.mock import mock_open

import click
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.utils.hosting import (
    authenticated_token,
    delete_token_from_config,
    get_authenticated_client,
    get_existing_access_token,
    save_token_to_config,
)


@pytest.mark.parametrize(
    "config_content, expected_token",
    [
        ('{"access_token": "valid_token"}', "valid_token"),
        ("{}", ""),
        (None, ""),
    ],
)
def test_get_existing_access_token(
    mocker: MockerFixture, config_content: str | None, expected_token: str
):
    mocker.patch("os.environ.get", return_value="")
    mocker.patch("pathlib.Path.open", mock_open(read_data=config_content))
    assert get_existing_access_token() == expected_token

    mocker.patch("pathlib.Path.open", side_effect=FileNotFoundError("Test exception"))
    assert get_existing_access_token() == ""


@pytest.mark.parametrize(
    "file_exists, config_content",
    [
        (True, '{"access_token": "valid_token"}'),
        (True, '{"another_key": "value"}'),
        (False, ""),
    ],
)
def test_delete_token_from_config(
    mocker: MockerFixture,
    file_exists: bool,
    config_content: str,
):
    mocker.patch("pathlib.Path.exists", return_value=file_exists)
    mock_os_remove = mocker.patch("pathlib.Path.unlink")

    mocked_open = mock_open(read_data=config_content)
    mocker.patch("pathlib.Path.open", mocked_open)
    mock_json_load = mocker.patch(
        "json.load", return_value=json.loads(config_content or "{}")
    )
    mock_json_dump = mocker.patch("json.dump")

    delete_token_from_config()

    if file_exists:
        assert mocked_open.call_count == 2
        mock_json_load.assert_called_once()
        mock_json_dump.assert_called_once()
        assert "access_token" not in mock_json_dump.call_args.args[0]
        mock_os_remove.assert_called_once()
    else:
        mocked_open.assert_not_called()
        mock_os_remove.assert_not_called()


def test_save_token_to_config(mocker: MockFixture):
    mocker.patch("pathlib.Path.exists", return_value=False)
    mock_makedirs = mocker.patch("pathlib.Path.mkdir")
    save_token_to_config("test_token")
    mock_makedirs.assert_called_once()

    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_json_dump = mocker.patch("json.dump")
    mocker.patch("pathlib.Path.open", mock_open())
    save_token_to_config("test_token")
    mock_json_dump.assert_called_once()


def test_authenticated_token_found_and_valid(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="valid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value={"user_info": True}
    )

    token = authenticated_token()

    assert token == ("valid_token", {"user_info": True})


def test_authenticated_token_not_found(mocker: MockFixture):
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")

    token = authenticated_token()
    assert token == ("", {})


def test_authenticated_token_found_but_invalid(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="invalid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=ValueError("access denied"),
    )
    mocker.patch(
        "reflex_cli.constants.hosting.Hosting.AUTH_RETRY_LIMIT", return_value=1
    )

    token = authenticated_token()
    assert token == ("", {})


def test_authenticated_token_found_but_validation_fails(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="invalid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=ValueError("server error"),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value="new_valid_token",
    )
    mock_delete_token = mocker.patch(
        "reflex_cli.utils.hosting.delete_token_from_config"
    )

    token = authenticated_token()

    assert token == ("", {})
    mock_delete_token.assert_called_once()


def test_authenticate_without_token_in_non_interactive_mode(mocker: MockerFixture):
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")
    with pytest.raises(click.exceptions.Exit):
        get_authenticated_client(token=None, interactive=False)


def test_authenticate_with_env_token_in_non_interactive_mode(mocker: MockerFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="env_token"
    )
    mock_get_auth_client = mocker.patch(
        "reflex_cli.utils.hosting.get_authentication_client"
    )
    mock_authenticated_client = mocker.MagicMock()
    mock_get_auth_client.return_value = mock_authenticated_client

    result = get_authenticated_client(token=None, interactive=False)

    assert result == mock_authenticated_client
    mock_get_auth_client.assert_called_once_with(None)
