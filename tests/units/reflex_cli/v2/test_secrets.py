import json
import logging
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_cli.utils import hosting
from reflex_cli.v2.deployments import hosting_cli

from .utils import as_click_command

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()


def test_get_secrets_success(mocker: MockFixture):
    """Test successful retrieval of secrets."""
    mock_get_secrets = mocker.patch(
        "reflex_cli.utils.hosting.get_secrets",
        return_value={"secret_key_1": "value1", "secret_key_2": "value2"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    app_id = "app_id"

    args = ["secrets", "list", app_id]

    result = runner.invoke(hosting_cli, args)

    mock_get_secrets.assert_called_once_with(
        app_id=app_id,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    mock_console_print_table.assert_called_once_with(
        [
            ["secret_key_1"],
            ["secret_key_2"],
        ],
        headers=["Keys"],
    )

    assert result.exit_code == 0, result.output


def test_get_secrets_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure to retrieve secrets.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mock_get_secrets = mocker.patch(
        "reflex_cli.utils.hosting.get_secrets",
        return_value="failed to retrieve secrets.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    app_id = "app_id"

    args = ["secrets", "list", app_id]
    result = runner.invoke(hosting_cli, args)

    mock_get_secrets.assert_called_once_with(
        app_id=app_id,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["failed to retrieve secrets."]

    assert result.exit_code == 1


def test_get_secrets_json_output(mocker: MockFixture):
    """Test JSON output for secrets."""
    mock_get_secrets = mocker.patch(
        "reflex_cli.utils.hosting.get_secrets",
        return_value={"secret_key_1": "value1", "secret_key_2": "value2"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    app_id = "app_id"

    args = ["secrets", "list", app_id, "--json"]

    result = runner.invoke(hosting_cli, args)

    mock_get_secrets.assert_called_once_with(
        app_id=app_id,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert json.loads(result.stdout) == {
        "secret_key_1": "value1",
        "secret_key_2": "value2",
    }
    assert result.exit_code == 0, result.output


def test_delete_secret_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful deletion of a secret.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mock_delete_secret = mocker.patch(
        "reflex_cli.utils.hosting.delete_secret",
        return_value="Successfully deleted secret.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    result = runner.invoke(
        hosting_cli,
        ["secrets", "delete", "app_id", "key", "--reboot"],
    )

    assert result.exit_code == 0, result.output
    mock_delete_secret.assert_called_once_with(
        app_id="app_id",
        key="key",
        reboot=True,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["Successfully deleted secret."]


def test_delete_secret_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure to delete a secret.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mock_delete_secret = mocker.patch(
        "reflex_cli.utils.hosting.delete_secret",
        return_value="failed to delete secret.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    result = runner.invoke(
        hosting_cli,
        ["secrets", "delete", "app_id", "key", "--reboot"],
    )

    assert result.exit_code == 1
    mock_delete_secret.assert_called_once_with(
        app_id="app_id",
        key="key",
        reboot=True,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["failed to delete secret."]


def test_update_secrets_with_envfile(mocker: MockFixture):
    """Test updating secrets with an envfile."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_content = "key1=value1\nkey2=value2"
        env_path.write_text(env_content)

        mocker.patch("reflex_cli.utils.hosting.update_secrets")

        result = runner.invoke(
            hosting_cli,
            [
                "secrets",
                "update",
                "app_id",
                "--envfile",
                str(env_path),
                "--env",
                "key3=value3",
            ],
        )

        assert result.exit_code == 0, result.output


def test_update_secrets_with_envs(mocker: MockFixture):
    """Test updating secrets with --env arguments."""
    mock_process_envs = mocker.patch(
        "reflex_cli.utils.hosting.process_envs",
        return_value={"key1": "value1", "key2": "value2"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_update_secrets = mocker.patch("reflex_cli.utils.hosting.update_secrets")

    result = runner.invoke(
        hosting_cli,
        ["secrets", "update", "app_id", "--env", "key1=value1", "--env", "key2=value2"],
    )

    assert result.exit_code == 0, result.output
    mock_process_envs.assert_called_once_with(["key1=value1", "key2=value2"])
    mock_update_secrets.assert_called_once_with(
        app_id="app_id",
        secrets={"key1": "value1", "key2": "value2"},
        reboot=False,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )


def test_update_secrets_missing_arguments(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test updating secrets with neither --envfile nor --env.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    result = runner.invoke(hosting_cli, ["secrets", "update", "app_id"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["--envfile or --env must be provided"]


def test_update_secrets_invalid_env_format(mocker: MockFixture):
    """Test invalid format for --env."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    result = runner.invoke(
        hosting_cli, ["secrets", "update", "app_id", "--env", "invalid_env"]
    )

    assert result.exit_code == 1
    assert "Invalid env format: should be <key>=<value>." in result.stdout


def _authed(mocker: MockFixture) -> hosting.AuthenticatedClient:
    """Patch the client lookup and return the client it hands back.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The authenticated client every command under test will receive.
    """
    client = hosting.AuthenticatedClient(token="fake-token", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )
    return client


def test_update_secrets_json_output(mocker: MockFixture):
    """An update reports the names it wrote, never the values."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.update_secrets")

    result = runner.invoke(
        hosting_cli,
        [
            "secrets",
            "update",
            "app123",
            "--env",
            "B=2",
            "--env",
            "A=1",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "updated": ["A", "B"],
        "rebooted": False,
    }
    assert "1" not in json.dumps(json.loads(result.stdout)["updated"])


def test_update_secrets_json_output_keeps_warnings_off_stdout(
    mocker: MockFixture, tmp_path: Path
):
    """A warning raised on the way through does not break the document.

    Args:
        mocker: The pytest-mock fixture.
        tmp_path: A temporary directory to hold the env file.
    """
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.update_secrets")
    envfile = tmp_path / ".env"
    envfile.write_text("A=1\n")

    result = runner.invoke(
        hosting_cli,
        [
            "secrets",
            "update",
            "app123",
            "--envfile",
            str(envfile),
            "--env",
            "B=2",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "updated": ["A"],
        "rebooted": False,
    }
    assert "--envfile is set; ignoring --env" in result.stderr


def test_delete_secret_json_output(mocker: MockFixture):
    """Deleting a secret reports the key it removed."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.delete_secret", return_value="deleted")

    result = runner.invoke(
        hosting_cli, ["secrets", "delete", "app123", "MY_KEY", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "key": "MY_KEY",
        "deleted": True,
        "rebooted": False,
    }
