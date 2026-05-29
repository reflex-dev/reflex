from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.core.config import Config
from reflex_cli.utils import hosting
from reflex_cli.utils.exceptions import GetAppError
from reflex_cli.v2.deployments import hosting_cli
from typer.main import Typer, get_command

hosting_cli = (
    get_command(hosting_cli) if isinstance(hosting_cli, Typer) else hosting_cli
)  # ty:ignore[invalid-assignment]

runner = CliRunner()


def test_app_history_success(mocker: MockFixture):
    """Test retrieving deployment history successfully."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_history = mocker.patch(
        "reflex_cli.utils.hosting.get_app_history",
        return_value=[
            {
                "id": "deployment1",
                "status": "success",
                "hostname": "example.com",
                "python version": "3.10",
                "reflex version": "1.2.3",
                "vm type": "small",
                "timestamp": "2024-11-29T12:00:00Z",
            },
            {
                "id": "deployment2",
                "status": "failure",
                "hostname": "example.org",
                "python version": "3.11",
                "reflex version": "1.1.0",
                "vm type": "medium",
                "timestamp": "2024-11-28T10:00:00Z",
            },
        ],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 0, result.output
    mock_get_app_history.assert_called_once_with(
        app_id="test_app_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print_table.assert_called_once()


def test_app_history_as_json(mocker: MockFixture):
    """Test retrieving deployment history with JSON output."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_history = mocker.patch(
        "reflex_cli.utils.hosting.get_app_history",
        return_value=[
            {
                "id": "deployment1",
                "status": "success",
                "hostname": "example.com",
                "python version": "3.10",
                "reflex version": "1.2.3",
                "vm type": "small",
                "timestamp": "2024-11-29T12:00:00Z",
            }
        ],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["apps", "history", "test_app_id", "--json"],
    )

    assert result.exit_code == 0, result.output
    mock_get_app_history.assert_called_once_with(
        app_id="test_app_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with(
        json.dumps([
            {
                "id": "deployment1",
                "status": "success",
                "hostname": "example.com",
                "python version": "3.10",
                "reflex version": "1.2.3",
                "vm type": "small",
                "timestamp": "2024-11-29T12:00:00Z",
            }
        ])
    )


def test_app_history_no_deployments(mocker: MockFixture):
    """Test retrieving deployment history when there are no deployments."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_history = mocker.patch(
        "reflex_cli.utils.hosting.get_app_history",
        return_value=[],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 0, result.output
    mock_get_app_history.assert_called_once_with(
        app_id="test_app_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with("[]")


def test_app_history_http_error(mocker: MockFixture):
    """Test retrieving deployment history when an HTTP error occurs."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_history = mocker.patch(
        "reflex_cli.utils.hosting.get_app_history",
        side_effect=Exception("HTTP request failed"),
    )
    mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 1
    mock_get_app_history.assert_called_once_with(
        app_id="test_app_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )


def test_deployment_build_logs_success(mocker: MockFixture):
    """Test successful retrieval of build logs."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_deployment_build_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_build_logs",
        return_value={"log": "Build completed successfully."},
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 0, result.output
    mock_get_deployment_build_logs.assert_called_once_with(
        deployment_id="test_deployment_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with({"log": "Build completed successfully."})


def test_deployment_build_logs_with_token(mocker: MockFixture):
    """Test retrieval of build logs with a provided token."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_deployment_build_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_build_logs",
        return_value={"log": "Build completed successfully."},
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["apps", "build-logs", "test_deployment_id", "--token", "fake-token"],
    )

    assert result.exit_code == 0, result.output
    mock_get_deployment_build_logs.assert_called_once_with(
        deployment_id="test_deployment_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with({"log": "Build completed successfully."})


def test_deployment_build_logs_not_authenticated(mocker: MockFixture):
    """Test retrieval of build logs when not authenticated."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_deployment_build_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_build_logs",
        side_effect=Exception("not authenticated"),
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 1  # Command should fail due to exception
    mock_get_deployment_build_logs.assert_called_once_with(
        deployment_id="test_deployment_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_not_called()


def test_deployment_build_logs_http_error(mocker: MockFixture):
    """Test retrieval of build logs when an HTTP error occurs."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_deployment_build_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_build_logs",
        side_effect=Exception("HTTP error: bad response from server"),
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 1
    mock_get_deployment_build_logs.assert_called_once_with(
        deployment_id="test_deployment_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_not_called()


def test_deployment_status_success(mocker: MockFixture):
    """Test successful retrieval of a deployment's status."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_status = mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_status",
        return_value="Deployment is running smoothly.",
    )
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "status", "12345"])

    assert result.exit_code == 0, result.output
    mock_get_status.assert_called_once_with(
        deployment_id="12345",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print.assert_called_once_with("Deployment is running smoothly.")


def test_deployment_status_watch_success(mocker: MockFixture):
    """Test continuous status watching for a deployment."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_watch_status = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=None,
    )

    result = runner.invoke(hosting_cli, ["apps", "status", "12345", "--watch"])

    assert result.exit_code == 0, result.output
    mock_watch_status.assert_called_once_with(
        deployment_id="12345",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )


def test_deployment_status_http_error(mocker: MockFixture):
    """Test HTTP error during status retrieval."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_get.return_value = mock_response
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["apps", "status", "12345"])

    assert result.exit_code == 0, result.output
    mock_error.assert_called_once_with("get status failed: Invalid token")


def test_stop_app_success(mocker: MockFixture):
    """Test successful stopping of an app."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_stop_app = mocker.patch(
        "reflex_cli.utils.hosting.stop_app",
        return_value="App stopped successfully",
    )
    mock_success = mocker.patch("reflex_cli.utils.console.success")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    mock_stop_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_success.assert_called_once_with("App stopped successfully")


def test_stop_app_failure(mocker: MockFixture):
    """Test failure during app stop operation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_stop_app = mocker.patch(
        "reflex_cli.utils.hosting.stop_app",
        return_value="stop app failed: Unable to stop app due to server error",
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    mock_stop_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error.assert_called_once_with(
        "stop app failed: Unable to stop app due to server error"
    )


def test_stop_app_http_error(mocker: MockFixture):
    """Test HTTP error during app stop operation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_post = mocker.patch("httpx.post")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_post.return_value = mock_response
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    mock_error.assert_called_once_with("stop app failed: Invalid token")


def test_start_app_success(mocker: MockFixture):
    """Test successful start of an app."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_start_app = mocker.patch(
        "reflex_cli.utils.hosting.start_app",
        return_value={"status": "success", "message": "App started successfully"},
    )
    mock_success = mocker.patch("reflex_cli.utils.console.success")

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    mock_start_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_success.assert_called_once_with({
        "status": "success",
        "message": "App started successfully",
    })


def test_start_app_failure(mocker: MockFixture):
    """Test failure during app start operation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_start_app = mocker.patch(
        "reflex_cli.utils.hosting.start_app",
        return_value="start app failed: Unable to start app due to server error",
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    mock_start_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error.assert_called_once_with(
        "start app failed: Unable to start app due to server error"
    )


def test_start_app_http_error(mocker: MockFixture):
    """Test HTTP error during app start operation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_post = mocker.patch("httpx.post")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_post.return_value = mock_response
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    mock_error.assert_called_once_with("start app failed: Invalid token")


def test_delete_app_success(mocker: MockFixture):
    """Test successful deletion of an app with confirmation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete_app = mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value={"status": "success", "message": "App deleted successfully"},
    )
    mock_get_app = mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count == 2
    mock_get_app.assert_has_calls(
        [
            mock.call(
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
                app_id="app123",
            ),
            mock.call(
                app_id="app123",
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
            ),
        ],
        any_order=True,
    )
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    mock_delete_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_warn.assert_called_once_with({
        "status": "success",
        "message": "App deleted successfully",
    })


def test_delete_app_failure(mocker: MockFixture):
    """Test failure during app deletion."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete_app = mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value="delete app failed: Unable to delete app due to server error",
    )
    mock_get_app = mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count == 2
    mock_get_app.assert_has_calls(
        [
            mock.call(
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
                app_id="app123",
            ),
            mock.call(
                app_id="app123",
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
            ),
        ],
        any_order=True,
    )
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    mock_delete_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_warn.assert_called_once_with(
        "delete app failed: Unable to delete app due to server error"
    )


def test_delete_app_no_app_id(mocker: MockFixture):
    """Test case when no app_id is provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    result = runner.invoke(hosting_cli, ["apps", "delete", ""])

    assert result.exit_code == 1
    mock_error.assert_called_once_with("No valid app_id or app_name provided.")


def test_delete_app_http_error(mocker: MockFixture):
    """Test HTTP error during app deletion."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete = mocker.patch("httpx.delete")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_delete.return_value = mock_response

    mock_get_app = mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count >= 1
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    mock_warn.assert_called_once_with("delete app failed: Invalid token")


def test_delete_app_confirmation_cancelled(mocker: MockFixture):
    """Test deletion cancelled when user responds 'n' to confirmation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete_app = mocker.patch("reflex_cli.utils.hosting.delete_app")
    mock_get_app = mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="n")
    mock_info = mocker.patch("reflex_cli.utils.console.info")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count == 2
    mock_get_app.assert_has_calls(
        [
            mock.call(
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
                app_id="app123",
            ),
            mock.call(
                app_id="app123",
                client=hosting.AuthenticatedClient(
                    token="fake-token", validated_data={"foo": "bar"}
                ),
            ),
        ],
        any_order=True,
    )
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    mock_info.assert_called_once_with("Deletion cancelled.")
    mock_delete_app.assert_not_called()


def test_delete_app_non_interactive_skips_confirmation(mocker: MockFixture):
    """Test deletion proceeds without confirmation when --no-interactive flag is used."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete_app = mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value={"status": "success", "message": "App deleted successfully"},
    )
    mock_get_app = mocker.patch("reflex_cli.utils.hosting.get_app")
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "app123", "--no-interactive"]
    )

    assert result.exit_code == 0, result.output
    mock_ask.assert_not_called()
    assert mock_get_app.call_count == 1
    mock_delete_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_warn.assert_called_once_with({
        "status": "success",
        "message": "App deleted successfully",
    })


def test_delete_app_get_app_fails_fallback_to_unknown(mocker: MockFixture):
    """Test deletion shows 'Unknown' when get_app fails."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_delete_app = mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value={"status": "success", "message": "App deleted successfully"},
    )
    mock_get_app = mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        side_effect=[
            GetAppError("Failed to fetch app"),
            {"id": "app123", "name": "Unknown"},
        ],
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count == 1
    mock_ask.assert_not_called()
    mock_delete_app.assert_not_called()
    mock_warn.assert_called_once_with("No application found with ID 'app123'")


def test_delete_app_with_app_name_confirmation(mocker: MockFixture):
    """Test deletion with app name shows proper app name in confirmation."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_search_app = mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={"id": "app123", "name": "my-test-app"},
    )
    mock_delete_app = mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value={"status": "success", "message": "App deleted successfully"},
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "--app-name", "my-test-app"])

    assert result.exit_code == 0, result.output
    mock_search_app.assert_called_once()
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'my-test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    mock_delete_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_warn.assert_called_once_with({
        "status": "success",
        "message": "App deleted successfully",
    })


def test_delete_app_not_found_early_exit(mocker: MockFixture):
    """Test early exit with warning when app is not found during search."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_search_app = mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=None,
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")
    mock_delete_app = mocker.patch("reflex_cli.utils.hosting.delete_app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "--app-name", "nonexistent-app"]
    )

    assert result.exit_code == 1, result.output
    mock_search_app.assert_called_once()
    mock_warn.assert_called_once_with("App 'nonexistent-app' not found.")
    mock_ask.assert_not_called()
    mock_delete_app.assert_not_called()


def test_app_logs_no_app_id(mocker: MockFixture):
    """Test case when no app_id is provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    result = runner.invoke(hosting_cli, ["apps", "logs", ""])

    assert result.exit_code == 1
    mock_error.assert_called_once_with("No valid app_id or app_name provided.")


def test_app_logs_invalid_time_range(mocker: MockFixture):
    """Test case when offset is provided without start and end."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")
    result = runner.invoke(
        hosting_cli,
        [
            "apps",
            "logs",
            "app123",
            "--start",
            "423453423",
        ],
    )

    assert result.exit_code == 1
    mock_error.assert_called_once_with("must provide both start and end")


def test_app_logs_success(mocker: MockFixture):
    """Test case for successful log retrieval."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=["log1", "log2", "log3"],
    )
    mock_info = mocker.patch("reflex_cli.utils.console.info")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once_with(
        app_id="app123",
        offset=3600,
        start=None,
        end=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
        cursor=None,
    )
    mock_info.assert_any_call("log3")
    mock_info.assert_any_call("log2")
    mock_info.assert_any_call("log1")


def test_app_logs_failure(mocker: MockFixture):
    """Test case when log retrieval fails."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value="get app logs failed: Unable to retrieve logs",
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once_with(
        app_id="app123",
        offset=3600,
        start=None,
        end=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
        cursor=None,
    )
    mock_warn.assert_called_once_with("Unable to retrieve logs.")


def test_app_logs_http_error(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(json=lambda: {"detail": "Invalid token"}),
    )
    mock_get.return_value = mock_response
    mock_warn = mocker.patch("reflex_cli.v2.deployments.console.warn")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value={"id": "fake_app_id"})
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "fake_app_id", "--token", "fake_token", "--follow", "false"],
    )

    assert result.exit_code == 0, result.output
    mock_warn.assert_called_once_with("Unable to retrieve logs.")


def test_list_apps_no_project(mocker: MockFixture):
    """Test case when no project is provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="default_project",
    )
    mock_list_apps = mocker.patch(
        "reflex_cli.utils.hosting.list_apps",
        return_value=[{"id": "1", "name": "App1"}, {"id": "2", "name": "App2"}],
    )
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 0, result.output
    mock_get_selected_project.assert_called_once()
    mock_list_apps.assert_called_once_with(
        project="default_project",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print_table.assert_called_once_with(
        [["1", "App1"], ["2", "App2"]],
        headers=["id", "name"],
    )


def test_list_apps_with_project(mocker: MockFixture):
    """Test case when a project is provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_list_apps = mocker.patch(
        "reflex_cli.utils.hosting.list_apps",
        return_value=[{"id": "1", "name": "App1"}],
    )
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "list", "--project", "project123"])

    assert result.exit_code == 0, result.output
    mock_list_apps.assert_called_once_with(
        project="project123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print_table.assert_called_once_with(
        [["1", "App1"]],
        headers=["id", "name"],
    )


def test_list_apps_json_output(mocker: MockFixture):
    """Test case for JSON output."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_list_apps = mocker.patch(
        "reflex_cli.utils.hosting.list_apps",
        return_value=[{"id": "1", "name": "App1"}],
    )
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "list", "--json"])

    assert result.exit_code == 0, result.output
    mock_list_apps.assert_called_once_with(
        project=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print.assert_called_once_with(json.dumps([{"id": "1", "name": "App1"}]))


def test_list_apps_error(mocker: MockFixture):
    """Test case when an error occurs while listing deployments."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_list_apps = mocker.patch(
        "reflex_cli.utils.hosting.list_apps",
        side_effect=Exception("Unable to list deployments"),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 1
    mock_list_apps.assert_called_once_with(
        project=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error.assert_called_once_with("Unable to list deployments")


def test_list_apps_empty_response(mocker: MockFixture):
    """Test case when no deployments are found."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_list_apps = mocker.patch("reflex_cli.utils.hosting.list_apps", return_value=[])
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 0, result.output
    mock_list_apps.assert_called_once_with(
        project=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print.assert_called_once_with("[]")


def test_scale_no_args_or_config(mocker: MockFixture):
    """Test error when neither args nor config file exists."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(),
    )
    mocker.patch("reflex_cli.core.config.Config.exists", return_value=False)
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "scale", "--app-name", "random"])

    assert result.exit_code == 1
    mock_error.assert_called_with(
        "specify either --vmtype or --regions or add them to the cloud.yml or pyproject.toml file"
    )


def test_scale_both_vmtype_and_regions(mocker: MockFixture):
    """Test error when both --vmtype and --regions are provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--vmtype", "c1m1", "--regions", "sjc"]
    )

    assert result.exit_code == 1
    mock_error.assert_called_with(
        "Only one of --vmtype or --regions should be provided."
    )


def test_scale_args_override_config(mocker: MockFixture):
    """Test warning when both args and config are provided."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    mocker.patch(
        "reflex_cli.utils.hosting.scale_app",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.ScaleParams.from_config",
        return_value=hosting.ScaleParams(
            type=hosting.ScaleType(hosting.ScaleType.SIZE), vm_type="c1m1"
        ),
    )
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(regions={"ams": 1}, vmtype="c1m2"),
    )
    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mock_warn = mocker.patch("reflex_cli.v2.deployments.console.warn")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--vmtype", "c1m1"]
    )

    assert result.exit_code == 0, result.output
    mock_warn.assert_called_with(
        "CLI arguments will override the values in the cloud.yml or pyproject.toml file."
    )


def test_scale_warn_cli_args_with_scale_type(mocker: MockFixture):
    """Test error when scaletype is set to size but vmtype is missing from config."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token",
            validated_data={"foo": "bar"},
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.scale_app",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.ScaleParams.from_config",
        return_value=hosting.ScaleParams(
            type=hosting.ScaleType(hosting.ScaleType.SIZE), vm_type="c1m1"
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )

    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(regions={"ams": 1}, vmtype=None),
    )
    mock_warn = mocker.patch("reflex_cli.utils.console.warn")

    result = runner.invoke(
        hosting_cli,
        [
            "apps",
            "scale",
            "--app-name",
            "random",
            "--regions",
            "ams",
            "--scale-type",
            "size",
        ],
    )

    assert result.exit_code == 0, result.output
    mock_warn.assert_called_with(
        "using --scale-type with --regions or --vmtype will have no effect"
    )


def test_scale_regions_via_config_no_scaletype(mocker: MockFixture):
    """Test error when scaletype is set to regions but regions is missing from config."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token",
            validated_data={"foo": "bar"},
        ),
    )

    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(regions=None, vmtype="c1m2"),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["apps", "scale", "--app-name", "random"])

    assert result.exit_code == 1
    mock_error.assert_called_with(
        "specify the type of scaling using --scale-type when using cloud.yml or pyproject.toml"
    )


def test_scale_regions_via_config_without_regions(mocker: MockFixture):
    """Test error when scaletype is set to regions but regions is missing from config."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token",
            validated_data={"foo": "bar"},
        ),
    )

    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(regions=None, vmtype="c1m2"),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--scale-type", "region"]
    )

    assert result.exit_code == 1
    mock_error.assert_called_with(
        "'regions' should be provided in the cloud.yml for region scaling"
    )


def test_scale_size_via_config_without_vmtype(mocker: MockFixture):
    """Test error when scaletype is set to size but vmtype is missing from config."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token",
            validated_data={"foo": "bar"},
        ),
    )

    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(regions=None, vmtype=None),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--scale-type", "size"]
    )

    assert result.exit_code == 1
    mock_error.assert_called_with(
        "'vmtype' should be provided in the cloud.yml for size scaling"
    )


@pytest.mark.parametrize(
    ("config", "scale_params", "command_args"),
    [
        (
            Config(vmtype="c1m1"),
            hosting.ScaleParams(
                type=hosting.ScaleType(hosting.ScaleType.SIZE),
                vm_type="c1m1",
            ),
            ["--vmtype", "c1m1"],
        ),
        (
            Config(vmtype=None, regions={"ams": 1}),
            hosting.ScaleParams(
                type=hosting.ScaleType.REGION,
                vm_type=None,
                regions=(hosting.Region(name="ams", number_of_machines=1),),
            ),
            ["--regions", "ams"],
        ),
        (
            Config(vmtype=None, regions={"ams": 1, "sjc": 1}),
            hosting.ScaleParams(
                type=hosting.ScaleType.REGION,
                vm_type=None,
                regions=(
                    hosting.Region(name="ams", number_of_machines=1),
                    hosting.Region(name="sjc", number_of_machines=1),
                ),
            ),
            ["--regions", "ams", "--regions", "sjc"],
        ),
    ],
)
def test_scale_correct_post_request_cli_args(
    mocker: MockerFixture,
    config: Config,
    scale_params: hosting.ScaleParams,
    command_args: list[str],
):
    """Test the correct POST request is made with appropriate parameters."""
    mocker.patch("reflex_cli.core.config.Config.exists", return_value=False)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    mock_authenticated_client = mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=mock_authenticated_client,
    )
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=config,
    )
    mock_post = mocker.patch("reflex_cli.utils.hosting.scale_app")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", *command_args]
    )

    assert result.exit_code == 0, result.output
    mock_post.assert_called_with(
        app_id="fake-id", scale_params=scale_params, client=mock_authenticated_client
    )


@pytest.mark.parametrize(
    ("config", "scale_params", "command_args"),
    [
        (
            Config(vmtype="c1m1", regions=None),
            hosting.ScaleParams(
                type=hosting.ScaleType(hosting.ScaleType.SIZE),
                vm_type="c1m1",
            ),
            ["--vmtype", "c1m1"],
        ),
        (
            Config(vmtype=None, regions={"ams": 1}),
            hosting.ScaleParams(
                type=hosting.ScaleType.REGION,
                vm_type=None,
                regions=(hosting.Region(name="ams", number_of_machines=1),),
            ),
            ["--regions", "ams"],
        ),
    ],
)
def test_scale_correct_post_request_config(
    mocker: MockerFixture,
    config: Config,
    scale_params: hosting.ScaleParams,
    command_args: list[str],
):
    """Test the correct POST request is made with appropriate parameters from config."""
    mocker.patch("reflex_cli.core.config.Config.exists", return_value=True)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    mock_authenticated_client = mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=mock_authenticated_client,
    )
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=config,
    )
    mock_post = mocker.patch("reflex_cli.utils.hosting.scale_app")
    mocker.patch(
        "reflex_cli.utils.hosting.ScaleParams.from_config", return_value=scale_params
    )
    mock_scale_params = mocker.patch(
        "reflex_cli.utils.hosting.ScaleParams.set_type_from_cli_args"
    )

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", *command_args]
    )

    assert result.exit_code == 0, result.output
    mock_post.assert_called_with(
        app_id="fake-id",
        scale_params=mock_scale_params.return_value,
        client=mock_authenticated_client,
    )
