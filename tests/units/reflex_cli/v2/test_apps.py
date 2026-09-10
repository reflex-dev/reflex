from __future__ import annotations

import json
import logging
from unittest import mock

import httpx
import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture, MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_cli.core.config import Config
from reflex_cli.utils import hosting
from reflex_cli.utils.exceptions import GetAppError
from reflex_cli.v2.apps import _resolve_app_id, apps_cli
from reflex_cli.v2.deployments import hosting_cli

from .utils import as_click_command

hosting_cli = as_click_command(hosting_cli)

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
    assert json.loads(result.stdout) == [
        {
            "id": "deployment1",
            "status": "success",
            "hostname": "example.com",
            "python version": "3.10",
            "reflex version": "1.2.3",
            "vm type": "small",
            "timestamp": "2024-11-29T12:00:00Z",
        }
    ]


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


def test_deployment_status_http_error(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test HTTP error during status retrieval.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["get status failed: Invalid token"]


def test_stop_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful stopping of an app.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    mock_stop_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["App stopped successfully"]


def test_stop_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app stop operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    mock_stop_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["stop app failed: Unable to stop app due to server error"]


def test_stop_app_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test HTTP error during app stop operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["stop app failed: Invalid token"]


def test_start_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful start of an app.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    mock_start_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == [
        str({"status": "success", "message": "App started successfully"})
    ]


def test_start_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app start operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    mock_start_app.assert_called_once_with(
        app_id="app123",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["start app failed: Unable to start app due to server error"]


def test_start_app_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test HTTP error during app start operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["start app failed: Invalid token"]


def test_delete_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful deletion of an app with confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [
        str({"status": "success", "message": "App deleted successfully"})
    ]


def test_delete_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app deletion.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["delete app failed: Unable to delete app due to server error"]


def test_delete_app_no_app_id(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when no app_id is provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    result = runner.invoke(hosting_cli, ["apps", "delete", ""])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["No valid app_id or app_name provided."]


def test_delete_app_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test HTTP error during app deletion.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count >= 1
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["delete app failed: Invalid token"]


def test_delete_app_confirmation_cancelled(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion cancelled when user responds 'n' to confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

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
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert infos == ["Deletion cancelled."]
    mock_delete_app.assert_not_called()


def test_delete_app_non_interactive_skips_confirmation(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion proceeds without confirmation when --no-interactive flag is used.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [
        str({"status": "success", "message": "App deleted successfully"})
    ]


def test_delete_app_get_app_fails_fallback_to_unknown(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion shows 'Unknown' when get_app fails.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    assert mock_get_app.call_count == 1
    mock_ask.assert_not_called()
    mock_delete_app.assert_not_called()
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["No application found with ID 'app123'"]


def test_delete_app_with_app_name_confirmation(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion with app name shows proper app name in confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "--app-name", "my-test-app", "--interactive"]
    )

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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [
        str({"status": "success", "message": "App deleted successfully"})
    ]


def test_delete_app_not_found_early_exit(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test early exit with warning when app is not found during search.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    mock_delete_app = mocker.patch("reflex_cli.utils.hosting.delete_app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "--app-name", "nonexistent-app"]
    )

    assert result.exit_code == 1, result.output
    mock_search_app.assert_called_once()
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["App 'nonexistent-app' not found."]
    mock_ask.assert_not_called()
    mock_delete_app.assert_not_called()


def test_app_logs_no_app_id(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when no app_id is provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    result = runner.invoke(hosting_cli, ["apps", "logs", ""])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["No valid app_id or app_name provided."]


def test_app_logs_invalid_time_range(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test case when offset is provided without start and end.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
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
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["must provide both start and end"]


def test_app_logs_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case for successful log retrieval.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert "log3" in infos
    assert "log2" in infos
    assert "log1" in infos


def test_app_logs_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when log retrieval fails.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    # The server said why; our own generic line would lose it.
    assert warnings == ["get app logs failed: Unable to retrieve logs"]


def test_app_logs_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["get app logs failed: Invalid token"]


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
    result = runner.invoke(hosting_cli, ["apps", "list", "--json"])

    assert result.exit_code == 0, result.output
    mock_list_apps.assert_called_once_with(
        project=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert json.loads(result.stdout) == [{"id": "1", "name": "App1"}]


def test_list_apps_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when an error occurs while listing deployments.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 1
    mock_list_apps.assert_called_once_with(
        project=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to list deployments"]


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


def test_scale_no_args_or_config(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test error when neither args nor config file exists.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "scale", "--app-name", "random"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[-1] == (
        "specify either --vmtype or --regions or add them to the cloud.yml or pyproject.toml file"
    )


def test_scale_both_vmtype_and_regions(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test error when both --vmtype and --regions are provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--vmtype", "c1m1", "--regions", "sjc"]
    )

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[-1] == "Only one of --vmtype or --regions should be provided."


def test_scale_args_override_config(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test warning when both args and config are provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--vmtype", "c1m1"]
    )

    assert result.exit_code == 0, result.output
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings[-1] == (
        "CLI arguments will override the values in the cloud.yml or pyproject.toml file."
    )


def test_scale_warn_cli_args_with_scale_type(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test error when scaletype is set to size but vmtype is missing from config.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings[-1] == (
        "using --scale-type with --regions or --vmtype will have no effect"
    )


def test_scale_regions_via_config_no_scaletype(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test error when scaletype is set to regions but regions is missing from config.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(hosting_cli, ["apps", "scale", "--app-name", "random"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[-1] == (
        "specify the type of scaling using --scale-type when using cloud.yml or pyproject.toml"
    )


def test_scale_regions_via_config_without_regions(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test error when scaletype is set to regions but regions is missing from config.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--scale-type", "region"]
    )

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[-1] == (
        "'regions' should be provided in the cloud.yml for region scaling"
    )


def test_scale_size_via_config_without_vmtype(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test error when scaletype is set to size but vmtype is missing from config.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
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

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--scale-type", "size"]
    )

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[-1] == (
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


# The rollback/describe tests invoke the `apps` group directly rather than
# through `hosting_cli` so they don't depend on the reflex-version gate on the
# top-level group callback.


def test_app_rollback_success(mocker: MockFixture):
    """A confirmed rollback calls the API with the resolved app + deployment."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mock_rollback = mocker.patch(
        "reflex_cli.utils.hosting.rollback_deployment", return_value=None
    )

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    mock_rollback.assert_called_once_with(
        app_id="app-1", deployment_id="dep-1", client=mock_client
    )


def test_app_rollback_defaults_to_cancel(mocker: MockFixture):
    """Pressing Enter at the confirm prompt cancels rather than rolling back."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mock_rollback = mocker.patch("reflex_cli.utils.hosting.rollback_deployment")

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--interactive"],
        input="\n",
    )

    assert result.exit_code == 0, result.output
    mock_rollback.assert_not_called()


def test_app_rollback_error_exits_nonzero(mocker: MockFixture):
    """An API error string surfaces and the command exits non-zero."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mocker.patch(
        "reflex_cli.utils.hosting.rollback_deployment",
        return_value="rollback failed: no image",
    )

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--no-interactive"],
    )

    assert result.exit_code == 1


def test_app_rollback_resolves_app_name(mocker: MockFixture):
    """--app-name is resolved to an app id before rolling back."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app", return_value={"id": "resolved-id"}
    )
    mock_rollback = mocker.patch(
        "reflex_cli.utils.hosting.rollback_deployment", return_value=None
    )

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-name", "myapp", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    assert mock_rollback.call_args.kwargs["app_id"] == "resolved-id"


def test_app_describe_sets_note(mocker: MockFixture):
    """Describe forwards the note to the description endpoint."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mock_desc = mocker.patch(
        "reflex_cli.utils.hosting.update_deployment_description", return_value=None
    )

    result = runner.invoke(
        apps_cli,
        ["describe", "dep-1", "--description", "hotfix", "--app-id", "app-1"],
    )

    assert result.exit_code == 0, result.output
    mock_desc.assert_called_once_with(
        app_id="app-1", deployment_id="dep-1", description="hotfix", client=mock_client
    )


def test_app_describe_error_exits_nonzero(mocker: MockFixture):
    """A failed description update exits non-zero."""
    mock_client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=mock_client
    )
    mocker.patch(
        "reflex_cli.utils.hosting.update_deployment_description",
        return_value="update description failed: no deployment",
    )

    result = runner.invoke(
        apps_cli,
        ["describe", "dep-1", "--description", "x", "--app-id", "app-1"],
    )

    assert result.exit_code == 1


def test_resolve_app_id_prefers_app_name_over_config(mocker: MockFixture):
    """An explicit --app-name overrides a configured appid rather than being ignored."""
    client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value=Config(appid="config-app-id"),
    )
    search = mocker.patch(
        "reflex_cli.utils.hosting.search_app", return_value={"id": "named-app-id"}
    )

    assert _resolve_app_id(None, "myapp", client, interactive=False) == "named-app-id"
    search.assert_called_once()


def test_resolve_app_id_falls_back_to_config(mocker: MockFixture):
    """With no explicit app id or name, the configured appid is used."""
    client = hosting.AuthenticatedClient(token="t", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value=Config(appid="config-app-id"),
    )
    search = mocker.patch("reflex_cli.utils.hosting.search_app")

    assert _resolve_app_id(None, None, client, interactive=False) == "config-app-id"
    search.assert_not_called()


def test_resolve_app_id_explicit_id_wins(mocker: MockFixture):
    """An explicit app id short-circuits both name lookup and config."""
    client = hosting.AuthenticatedClient(token="t", validated_data={})
    read_config = mocker.patch("reflex_cli.utils.hosting.read_config")
    search = mocker.patch("reflex_cli.utils.hosting.search_app")

    assert _resolve_app_id("explicit-id", "myapp", client, interactive=False) == (
        "explicit-id"
    )
    search.assert_not_called()
    read_config.assert_not_called()


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


def test_app_logs_does_not_follow_by_default(mocker: MockFixture):
    """One page is fetched and the command returns, with nothing to answer.

    Following prompts between pages, and a prompt nobody answers is a command
    that never exits -- which is why it is opt-in.
    """
    _authed(mocker)
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=[["log1"], "next-cursor"],
    )
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once()
    prompt.assert_not_called()


def test_app_logs_follow_needs_a_person_to_answer_the_prompt(mocker: MockFixture):
    """--follow is ignored without interactive mode rather than hanging."""
    _authed(mocker)
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=[["log1"], "next-cursor"],
    )
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--follow", "true", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once()
    prompt.assert_not_called()


def test_app_logs_follow_pages_when_asked_interactively(mocker: MockFixture):
    """Passing --follow at a terminal still walks the pages."""
    _authed(mocker)
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=[["log1"], "next-cursor"],
    )
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="exit")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--follow", "true", "--interactive"],
    )

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once()
    prompt.assert_called_once()


def test_app_logs_json_output(mocker: MockFixture):
    """The page and its next cursor come back as one document."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=[["log1", "log2"], "next-cursor"],
    )

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        # Reversed into chronological order, the same as the rendered form.
        "entries": ["log2", "log1"],
        "cursor": "next-cursor",
        "error": None,
    }


def test_app_logs_json_output_never_follows(mocker: MockFixture):
    """--follow cannot page a document that is only complete once."""
    _authed(mocker)
    mock_get_app_logs = mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value=[["log1"], "next-cursor"],
    )
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--json", "--follow", "true", "--interactive"],
    )

    assert result.exit_code == 0, result.output
    mock_get_app_logs.assert_called_once()
    prompt.assert_not_called()
    assert json.loads(result.stdout)["cursor"] == "next-cursor"


def test_app_logs_json_output_when_empty(mocker: MockFixture):
    """No logs is an empty document rather than a warning to parse."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_app_logs", return_value=[])

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "entries": [],
        "cursor": None,
        "error": None,
    }


def test_stop_app_json_output(mocker: MockFixture):
    """Stopping an app reports the outcome as a document."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.stop_app", return_value="app stopped")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "stopped": True,
        "message": "app stopped",
    }


def test_stop_app_json_output_on_failure(mocker: MockFixture):
    """A refusal is reported in the document, not only in the log."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.stop_app", return_value="stop failed")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["stopped"] is False


def test_start_app_json_output(mocker: MockFixture):
    """Starting an app reports the outcome as a document."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.start_app", return_value="app started")

    result = runner.invoke(hosting_cli, ["apps", "start", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "started": True,
        "message": "app started",
    }


def test_delete_app_json_output(mocker: MockFixture):
    """Deleting an app reports the outcome as a document."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mocker.patch("reflex_cli.utils.hosting.delete_app", return_value="")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": True,
        "message": "",
    }


def test_delete_app_json_output_on_failure(mocker: MockFixture):
    """A refusal is reported as a failed deletion, not as a deleted app."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.delete_app",
        return_value="delete app failed: app is deploying",
    )

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": False,
        "message": "delete app failed: app is deploying",
    }


def test_app_logs_json_output_when_unreadable(mocker: MockFixture):
    """Logs that could not be read are distinguishable from none existing."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_app_logs", return_value=None)

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "entries": [],
        "cursor": None,
        "error": "Unable to retrieve logs.",
    }


def test_delete_app_json_output_when_cancelled(mocker: MockFixture):
    """Declining the confirmation is reported rather than left silent."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_app",
        return_value={"id": "app123", "name": "test-app"},
    )
    delete = mocker.patch("reflex_cli.utils.hosting.delete_app")
    mocker.patch("reflex_cli.utils.console.ask", return_value="n")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "app123", "--json", "--interactive"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": False,
        "cancelled": True,
    }
    delete.assert_not_called()


def test_app_rollback_json_output(mocker: MockFixture):
    """A rollback reports what it rolled back to."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.rollback_deployment", return_value="")

    result = runner.invoke(
        hosting_cli,
        ["apps", "rollback", "dep-1", "--app-id", "app-1", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app-1",
        "deployment_id": "dep-1",
        "rolled_back": True,
        "cancelled": False,
    }


def test_app_describe_json_output(mocker: MockFixture):
    """Setting a changelog note reports the note it set."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.update_deployment_description", return_value=""
    )

    result = runner.invoke(
        hosting_cli,
        [
            "apps",
            "describe",
            "dep-1",
            "--app-id",
            "app-1",
            "--description",
            "hotfix",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app-1",
        "deployment_id": "dep-1",
        "description": "hotfix",
    }


def test_deployment_build_logs_json_output(mocker: MockFixture):
    """Build logs come back as a field rather than as raw console text."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_build_logs",
        return_value="step 1\nstep 2",
    )

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "dep-1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "logs": "step 1\nstep 2",
    }


def test_deployment_status_json_output(mocker: MockFixture):
    """A status read reports the status and whether it is a failure."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_status", return_value="deploying"
    )

    result = runner.invoke(hosting_cli, ["apps", "status", "dep-1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "status": "deploying",
        "success": True,
    }


def test_deployment_status_json_output_while_watching(mocker: MockFixture):
    """Watching re-reads the status once it ends, since the watch returns a bool."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.watch_deployment_status", return_value=True)
    mocker.patch(
        "reflex_cli.utils.hosting.get_deployment_status",
        return_value="completed successfully",
    )

    result = runner.invoke(
        hosting_cli, ["apps", "status", "dep-1", "--watch", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "status": "completed successfully",
        "success": True,
    }


def test_scale_app_json_output(mocker: MockFixture):
    """Scaling reports the parameters it applied."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.scale_app")
    mocker.patch(
        "reflex_cli.core.config.Config.from_yaml_or_toml_or_default",
        return_value=Config(),
    )

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "app123", "--vmtype", "c1m1", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "scaled": True,
        "vmtype": "c1m1",
        "regions": [],
        "scale_type": "size",
    }


def test_json_output_keeps_human_messages_off_stdout(mocker: MockFixture):
    """A log line from the command body never lands inside the document."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.list_apps", return_value=[{"id": "1", "name": "App1"}]
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project", return_value="project-1"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        return_value={"id": "project-1", "name": "My Project"},
    )

    result = runner.invoke(hosting_cli, ["apps", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"id": "1", "name": "App1"}]


@pytest.mark.parametrize(
    ("status", "success"),
    [
        ("deployment completed successfully", True),
        ("Deployment is running smoothly.", True),
        ("AwaitingApproval", True),
        ("build error", False),
        ("deployment failed", False),
        ("error: something went wrong", False),
        ("unable to find status for given id", False),
    ],
)
def test_deployment_status_json_agrees_with_watch(
    mocker: MockFixture, status: str, success: bool
):
    """The polled document classifies a status the way --watch does.

    Args:
        mocker: The pytest-mock fixture.
        status: The status string the hosting service returned.
        success: Whether that status should be reported as a success.
    """
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_deployment_status", return_value=status)

    result = runner.invoke(hosting_cli, ["apps", "status", "12345", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "12345",
        "status": status,
        "success": success,
    }


def test_app_logs_json_output_names_the_servers_reason(mocker: MockFixture):
    """A refusal the server explained is reported in its own words."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_app_logs",
        return_value="get app logs failed: app is not running",
    )

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "entries": [],
        "cursor": None,
        "error": "get app logs failed: app is not running",
    }


def test_delete_app_json_output_when_app_is_gone(mocker: MockFixture):
    """The one exit here that is zero still says the app was not deleted."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_app", return_value=None)
    delete = mocker.patch("reflex_cli.utils.hosting.delete_app")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": False,
        "message": "App with ID 'app123' not found.",
    }
    delete.assert_not_called()
