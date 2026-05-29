import tempfile
from pathlib import Path

from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_cli.utils import hosting
from reflex_cli.v2.deployments import hosting_cli
from typer import Typer
from typer.main import get_command

hosting_cli = (
    get_command(hosting_cli) if isinstance(hosting_cli, Typer) else hosting_cli
)  # ty:ignore[invalid-assignment]

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


def test_get_secrets_error(mocker: MockFixture):
    """Test failure to retrieve secrets."""
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
    mock_console_error = mocker.patch("reflex_cli.utils.console.error")

    app_id = "app_id"

    args = ["secrets", "list", app_id]
    result = runner.invoke(hosting_cli, args)

    mock_get_secrets.assert_called_once_with(
        app_id=app_id,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    mock_console_error.assert_called_once_with("failed to retrieve secrets.")

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
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    app_id = "app_id"

    args = ["secrets", "list", app_id, "--json"]

    result = runner.invoke(hosting_cli, args)

    mock_get_secrets.assert_called_once_with(
        app_id=app_id,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with({
        "secret_key_1": "value1",
        "secret_key_2": "value2",
    })
    assert result.exit_code == 0, result.output


def test_delete_secret_success(mocker: MockFixture):
    """Test successful deletion of a secret."""
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
    mock_console_success = mocker.patch("reflex_cli.utils.console.success")

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
    mock_console_success.assert_called_once_with("Successfully deleted secret.")


def test_delete_secret_failure(mocker: MockFixture):
    """Test failure to delete a secret."""
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
    mock_console_error = mocker.patch("reflex_cli.utils.console.error")

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
    mock_console_error.assert_called_once_with("failed to delete secret.")


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
        mocker.patch("reflex_cli.utils.console.warn")

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


def test_update_secrets_missing_arguments(mocker: MockFixture):
    """Test updating secrets with neither --envfile nor --env."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["secrets", "update", "app_id"])

    assert result.exit_code == 1
    mock_console_error.assert_called_once_with("--envfile or --env must be provided")


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
