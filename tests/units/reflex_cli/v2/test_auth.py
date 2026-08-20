"""Tests for the `reflex cloud whoami` and `reflex cloud token` commands."""

import json
import logging

import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_cli.utils import hosting
from reflex_cli.utils.exceptions import TokenAccessDeniedError, TokenValidationError
from reflex_cli.v2.auth import token_fingerprint
from reflex_cli.v2.deployments import hosting_cli
from typer import Typer
from typer.main import get_command

hosting_cli = (
    get_command(hosting_cli) if isinstance(hosting_cli, Typer) else hosting_cli
)

runner = CliRunner()

VALIDATED_INFO = {
    "email": "user@example.com",
    "user_id": "user-uuid",
    "org_id": "org-uuid",
    "tier": "Pro",
    "is_service_account": False,
    "_memo": {},
}


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def test_token_fingerprint_is_stable_and_hides_the_token():
    token = "super-secret-token"
    assert token_fingerprint(token) == token_fingerprint(token)
    assert token_fingerprint(token) != token_fingerprint(token + "x")
    assert token not in token_fingerprint(token)
    assert token_fingerprint("") == ""


def test_whoami_reports_identity_and_token_source(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("valid_token", hosting.TokenSource.CONFIG),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value=dict(VALIDATED_INFO)
    )

    result = runner.invoke(hosting_cli, ["whoami", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["email"] == "user@example.com"
    assert payload["org_id"] == "org-uuid"
    assert payload["token_source"] == "config file"
    assert payload["token_fingerprint"] == token_fingerprint("valid_token")
    # Private control-plane fields stay out of the output.
    assert "_memo" not in payload
    # The token itself is never printed.
    assert "valid_token" not in result.output


def test_whoami_table_output_hides_the_token(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("valid_token", hosting.TokenSource.CONFIG),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value=dict(VALIDATED_INFO)
    )
    print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["whoami"])

    assert result.exit_code == 0
    rows = print_table.call_args.args[0]
    assert ["email", "user@example.com"] in rows
    assert ["token_source", "config file"] in rows
    assert all("valid_token" not in cell for row in rows for cell in row)


def test_whoami_prefers_the_token_option(mocker: MockFixture):
    from_config = mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source"
    )
    validate = mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value=dict(VALIDATED_INFO)
    )

    result = runner.invoke(hosting_cli, ["whoami", "--json", "--token", "cli_token"])

    assert result.exit_code == 0
    validate.assert_called_once_with("cli_token")
    from_config.assert_not_called()
    assert json.loads(result.output)["token_source"] == "--token option"


def test_whoami_without_a_token_does_not_open_a_browser(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("", hosting.TokenSource.NONE),
    )
    authenticate = mocker.patch("reflex_cli.utils.hosting.authenticate_on_browser")

    result = runner.invoke(hosting_cli, ["whoami"])

    assert result.exit_code == 1
    authenticate.assert_not_called()
    assert any(
        "Not logged in" in message for message in _messages(caplog, logging.ERROR)
    )


def test_whoami_surfaces_the_auth_request_id(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("stale_token", hosting.TokenSource.ENVIRONMENT),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=TokenAccessDeniedError("access denied", request_id="req-123"),
    )

    result = runner.invoke(hosting_cli, ["whoami"])

    assert result.exit_code == 1
    errors = _messages(caplog, logging.ERROR)
    assert any("req-123" in message for message in errors)
    assert any("REFLEX_ACCESS_TOKEN" in message for message in errors)


def test_token_print_writes_the_raw_token_to_stdout(mocker: MockFixture):
    long_token = "t" * 300
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=(long_token, hosting.TokenSource.CONFIG),
    )

    result = runner.invoke(hosting_cli, ["token", "--print"])

    assert result.exit_code == 0
    # Captured verbatim on one line, so `$(reflex cloud token --print)` is exact.
    assert result.output == long_token + "\n"


def test_token_print_without_a_token_fails(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("", hosting.TokenSource.NONE),
    )

    result = runner.invoke(hosting_cli, ["token", "--print"])

    assert result.exit_code == 1
    assert any(
        "No access token stored" in message
        for message in _messages(caplog, logging.ERROR)
    )


def test_token_set_validates_before_saving(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value=dict(VALIDATED_INFO)
    )
    save = mocker.patch("reflex_cli.utils.hosting.save_token_to_config")
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("new_token", hosting.TokenSource.CONFIG),
    )

    result = runner.invoke(hosting_cli, ["token", "--set", "new_token"])

    assert result.exit_code == 0
    save.assert_called_once_with("new_token")
    assert any("user@example.com" in message for message in _messages(caplog, SUCCESS))


def test_token_set_keeps_the_old_token_when_the_new_one_is_rejected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=TokenValidationError("server error", request_id="req-456"),
    )
    save = mocker.patch("reflex_cli.utils.hosting.save_token_to_config")
    delete = mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    result = runner.invoke(hosting_cli, ["token", "--set", "bad_token"])

    assert result.exit_code == 1
    # A bad --set must not clobber or delete a working token.
    save.assert_not_called()
    delete.assert_not_called()
    assert any("req-456" in message for message in _messages(caplog, logging.ERROR))


def test_token_set_reports_a_failed_write(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value=dict(VALIDATED_INFO)
    )
    # save_token_to_config swallows write errors, so the command reads back.
    mocker.patch("reflex_cli.utils.hosting.save_token_to_config")
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token_with_source",
        return_value=("new_token", hosting.TokenSource.ENVIRONMENT),
    )

    result = runner.invoke(hosting_cli, ["token", "--set", "new_token"])

    assert result.exit_code == 1
    assert any(
        "Unable to persist" in message for message in _messages(caplog, logging.ERROR)
    )


def test_token_clear_removes_the_token(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    delete = mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    result = runner.invoke(hosting_cli, ["token", "--clear"])

    assert result.exit_code == 0
    delete.assert_called_once_with()
    assert any("Cleared" in message for message in _messages(caplog, SUCCESS))


def test_token_clear_warns_when_the_env_var_still_applies(
    mocker: MockFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    monkeypatch.setenv("REFLEX_ACCESS_TOKEN", "env_token")
    mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    result = runner.invoke(hosting_cli, ["token", "--clear"])

    assert result.exit_code == 0
    assert any(
        "REFLEX_ACCESS_TOKEN is still set" in message
        for message in _messages(caplog, logging.INFO)
    )


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--print", "--clear"],
        ["--print", "--set", "tok"],
        ["--set", "tok", "--clear"],
    ],
)
def test_token_requires_exactly_one_operation(args: list[str], mocker: MockFixture):
    save = mocker.patch("reflex_cli.utils.hosting.save_token_to_config")
    delete = mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    result = runner.invoke(hosting_cli, ["token", *args])

    assert result.exit_code == 2
    assert "exactly one of --print, --set or --clear" in result.output
    save.assert_not_called()
    delete.assert_not_called()
