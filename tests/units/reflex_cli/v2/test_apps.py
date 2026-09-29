from __future__ import annotations

import datetime
import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture, MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_build_sdk.types import App, AppSummary, DeploymentRecord, LogRecord
from reflex_cli.core.config import Config
from reflex_cli.utils import hosting
from reflex_cli.v2.apps import _resolve_app_id, apps_cli
from reflex_cli.v2.deployments import hosting_cli

from .utils import api_error, as_click_command, fake_client

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()

_APP_ID = uuid.UUID(int=21)
_PROJECT_ID = uuid.UUID(int=22)
_DEPLOYMENT_ID = uuid.UUID(int=31)


def _authed(mocker: MockFixture):
    """Patch the client lookup and hand back a client with a fresh API mock.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The client every command under test will receive.
    """
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )
    return client


def app_summary(name: str = "test-app", **fields) -> AppSummary:
    """Build an app as a listing or a search reports one.

    Args:
        name: The app's name.
        fields: Overrides for its other fields.

    Returns:
        The app.
    """
    return AppSummary(**{
        "id": _APP_ID,
        "name": name,
        "description": "",
        "project_id": _PROJECT_ID,
        "provider": "fly",
        "disable_secrets": False,
        **fields,
    })


def app(name: str = "test-app", **fields) -> App:
    """Build an app as `apps inspect` reports one.

    Args:
        name: The app's name.
        fields: Overrides for its other fields.

    Returns:
        The app.
    """
    return App(**{
        "id": _APP_ID,
        "name": name,
        "description": "",
        "project_id": _PROJECT_ID,
        "org_id": None,
        "provider": "fly",
        "full_deploy": False,
        "min_instances": None,
        "max_instances": None,
        "has_deployments": True,
        "latest_deployment": None,
        "backend_url": None,
        "disable_secrets": False,
        "weekly_report_enabled": False,
        "source_thread_id": None,
        "unreleased_provider": None,
        "any_environment_live": False,
        "any_environment_stopped": False,
        "any_environment_paused": False,
        "any_environment_credit_paused": False,
        **fields,
    })


def deployment_record(**fields) -> DeploymentRecord:
    """Build a deployment as an app's history reports one.

    Args:
        fields: Overrides for the record's fields.

    Returns:
        The deployment.
    """
    return DeploymentRecord(**{
        "id": _DEPLOYMENT_ID,
        "url": "https://example.com",
        "backend_url": "https://api.example.com",
        "status": "success",
        "pause_reason": None,
        "failure_code": None,
        "failure_reason": None,
        "description": None,
        "reflex_version": "1.2.3",
        "python_version": "3.10",
        "created_at": datetime.datetime(2024, 11, 29, 12, tzinfo=datetime.timezone.utc),
        "updated_at": None,
        "deployed_by": None,
        "vm_type": None,
        "environment_id": None,
        "environment_name": None,
        "can_rollback": True,
        "updated_by": None,
        "promoted_from_id": None,
        **fields,
    })


def log_records(*messages: str) -> Iterator[LogRecord]:
    """Yield log lines the way the client does: once, lazily.

    A list would let a caller that reads the whole iterator pass a test it
    should fail, which is the paging contract `--follow` rests on.

    Args:
        messages: The lines that were logged.

    Yields:
        The records.
    """
    for message in messages:
        yield log_record(message)


def log_record(message: str) -> LogRecord:
    """Build one line of an app's runtime logs.

    Args:
        message: The line that was logged.

    Returns:
        The record.
    """
    return LogRecord(
        ns=0,
        timestamp="2024-11-29T12:00:00Z",
        name="app",
        message=message,
        event_id=None,
        stream_id=None,
        revision_id=None,
    )


def test_app_history_success(mocker: MockFixture):
    """Test retrieving deployment history successfully."""
    client = _authed(mocker)
    client.api.apps.history.return_value = [deployment_record()]
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 0, result.output
    client.api.apps.history.assert_called_once_with("test_app_id")
    mock_console_print_table.assert_called_once()


def test_app_history_as_json(mocker: MockFixture):
    """Test retrieving deployment history with JSON output."""
    client = _authed(mocker)
    client.api.apps.history.return_value = [deployment_record()]
    result = runner.invoke(
        hosting_cli,
        ["apps", "history", "test_app_id", "--json"],
    )

    assert result.exit_code == 0, result.output
    client.api.apps.history.assert_called_once_with("test_app_id")
    assert json.loads(result.stdout) == [
        {
            "id": str(_DEPLOYMENT_ID),
            "status": "success",
            "url": "https://example.com",
            "python version": "3.10",
            "reflex version": "1.2.3",
            "vm type": None,
            "timestamp": "2024-11-29T12:00:00+00:00",
            "description": "",
            "can rollback": True,
        }
    ]


def test_app_history_without_a_url(mocker: MockFixture):
    """A deployment that is not serving yet reports a null url, not a missing key.

    Args:
        mocker: The pytest-mock fixture.
    """
    client = _authed(mocker)
    client.api.apps.history.return_value = [deployment_record(url=None)]

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)[0]["url"] is None


def test_app_history_no_deployments(mocker: MockFixture):
    """Test retrieving deployment history when there are no deployments."""
    client = _authed(mocker)
    client.api.apps.history.return_value = []
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 0, result.output
    client.api.apps.history.assert_called_once_with("test_app_id")
    mock_console_print.assert_called_once_with("[]")


def test_app_history_http_error(mocker: MockFixture):
    """Test retrieving deployment history when an HTTP error occurs."""
    client = _authed(mocker)
    client.api.apps.history.side_effect = api_error(500, "HTTP request failed")

    result = runner.invoke(hosting_cli, ["apps", "history", "test_app_id"])

    assert result.exit_code == 1
    client.api.apps.history.assert_called_once_with("test_app_id")


def test_deployment_build_logs_success(mocker: MockFixture):
    """Test successful retrieval of build logs."""
    client = _authed(mocker)
    client.api.deployments.build_logs.return_value = "Build completed successfully."
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 0, result.output
    client.api.deployments.build_logs.assert_called_once_with("test_deployment_id")
    mock_console_print.assert_called_once_with("Build completed successfully.")


def test_deployment_build_logs_with_token(mocker: MockFixture):
    """Test retrieval of build logs with a provided token."""
    client = _authed(mocker)
    client.api.deployments.build_logs.return_value = "Build completed successfully."
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["apps", "build-logs", "test_deployment_id", "--token", "fake-token"],
    )

    assert result.exit_code == 0, result.output
    client.api.deployments.build_logs.assert_called_once_with("test_deployment_id")
    mock_console_print.assert_called_once_with("Build completed successfully.")


def test_deployment_build_logs_not_authenticated(mocker: MockFixture):
    """Test retrieval of build logs when not authenticated."""
    client = _authed(mocker)
    client.api.deployments.build_logs.side_effect = api_error(500, "not authenticated")
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 1  # Command should fail due to exception
    client.api.deployments.build_logs.assert_called_once_with("test_deployment_id")
    mock_console_print.assert_not_called()


def test_deployment_build_logs_http_error(mocker: MockFixture):
    """Test retrieval of build logs when an HTTP error occurs."""
    client = _authed(mocker)
    client.api.deployments.build_logs.side_effect = api_error(
        500, "HTTP error: bad response from server"
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "test_deployment_id"])

    assert result.exit_code == 1
    client.api.deployments.build_logs.assert_called_once_with("test_deployment_id")
    mock_console_print.assert_not_called()


def test_deployment_status_success(mocker: MockFixture):
    """Test successful retrieval of a deployment's status."""
    client = _authed(mocker)
    client.api.deployments.status.return_value = "Deployment is running smoothly."
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "status", "12345"])

    assert result.exit_code == 0, result.output
    client.api.deployments.status.assert_called_once_with("12345")
    mock_print.assert_called_once_with("Deployment is running smoothly.")


def test_deployment_status_watch_success(mocker: MockFixture):
    """Test continuous status watching for a deployment."""
    client = _authed(mocker)
    mock_watch_status = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=hosting.WatchResult(hosting.WatchOutcome.SUCCEEDED, "ready"),
    )

    result = runner.invoke(hosting_cli, ["apps", "status", "12345", "--watch"])

    assert result.exit_code == 0, result.output
    mock_watch_status.assert_called_once_with(
        deployment_id="12345",
        client=client,
    )


def test_deployment_status_http_error(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test HTTP error during status retrieval.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.deployments.status.side_effect = api_error(400, "Invalid token")

    result = runner.invoke(hosting_cli, ["apps", "status", "12345"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Invalid token"]


def test_stop_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful stopping of an app.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 0, result.output
    client.api.apps.stop.assert_called_once_with("app123")
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["app stopped"]


def test_stop_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app stop operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.stop.side_effect = api_error(
        500, "Unable to stop app due to server error"
    )

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 1
    client.api.apps.stop.assert_called_once_with("app123")
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to stop app due to server error"]


def test_stop_app_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test HTTP error during app stop operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.stop.side_effect = api_error(401, "Invalid token")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["You are not authenticated. Run `reflex login` to authenticate."]


def test_start_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful start of an app.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 0, result.output
    client.api.apps.start.assert_called_once_with("app123")
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["app started"]


def test_start_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app start operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.start.side_effect = api_error(
        500, "Unable to start app due to server error"
    )

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 1
    client.api.apps.start.assert_called_once_with("app123")
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to start app due to server error"]


def test_start_app_http_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test HTTP error during app start operation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.start.side_effect = api_error(401, "Invalid token")

    result = runner.invoke(hosting_cli, ["apps", "start", "app123"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["You are not authenticated. Run `reflex login` to authenticate."]


def test_delete_app_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful deletion of an app with confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.get.return_value = app("test-app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    assert client.api.apps.get.call_count == 1
    client.api.apps.get.assert_called_once_with("app123")
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    client.api.apps.delete.assert_called_once_with("app123")
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["app deleted"]


def test_delete_app_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during app deletion.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.delete.side_effect = api_error(
        500, "Unable to delete app due to server error"
    )
    client.api.apps.get.return_value = app("test-app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 1
    client.api.apps.get.assert_called_once_with("app123")
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    client.api.apps.delete.assert_called_once_with("app123")
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Unable to delete app due to server error"]


def test_delete_app_no_app_id(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when no app_id is provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
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
    client = _authed(mocker)
    client.api.apps.delete.side_effect = api_error(400, "Invalid token")

    client.api.apps.get.return_value = app("test-app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 1
    assert client.api.apps.get.call_count >= 1
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Invalid token"]


def test_delete_app_confirmation_cancelled(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion cancelled when user responds 'n' to confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.get.return_value = app("test-app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="n")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    assert client.api.apps.get.call_count == 1
    client.api.apps.get.assert_called_once_with("app123")
    mock_ask.assert_called_once_with(
        "Are you sure you want to delete app 'test-app' (ID: app123)?",
        choices=["y", "n"],
        default="n",
    )
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert infos == ["Deletion cancelled."]
    client.api.apps.delete.assert_not_called()


def test_delete_app_non_interactive_skips_confirmation(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion proceeds without confirmation when --no-interactive flag is used.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    mock_ask = mocker.patch("reflex_cli.utils.console.ask")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "app123", "--no-interactive"]
    )

    assert result.exit_code == 0, result.output
    mock_ask.assert_not_called()
    assert client.api.apps.get.call_count == 1
    client.api.apps.delete.assert_called_once_with("app123")
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["app deleted"]


def test_delete_app_unknown_id(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Deleting an app ID that does not exist fails with a non-zero exit.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.get.side_effect = api_error(404, "Failed to fetch app")
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--interactive"])

    assert result.exit_code == 1, result.output
    assert client.api.apps.get.call_count == 1
    mock_ask.assert_not_called()
    client.api.apps.delete.assert_not_called()
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["No application found with ID 'app123'"]


def test_delete_app_with_app_name_confirmation(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test deletion with app name shows proper app name in confirmation.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    mock_search_app = mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("my-test-app"),
    )
    mock_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "--app-name", "my-test-app", "--interactive"]
    )

    assert result.exit_code == 0, result.output
    mock_search_app.assert_called_once()
    mock_ask.assert_called_once_with(
        f"Are you sure you want to delete app 'my-test-app' (ID: {_APP_ID})?",
        choices=["y", "n"],
        default="n",
    )
    client.api.apps.delete.assert_called_once_with(str(_APP_ID))
    successes = [r.getMessage() for r in caplog.records if r.levelno == SUCCESS]
    assert successes == ["app deleted"]


def test_delete_app_not_found_early_exit(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test early exit with warning when app is not found during search.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    mock_search_app = mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=None,
    )
    mock_ask = mocker.patch("reflex_cli.utils.console.ask")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "--app-name", "nonexistent-app"]
    )

    assert result.exit_code == 1, result.output
    mock_search_app.assert_called_once()
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["App 'nonexistent-app' not found."]
    mock_ask.assert_not_called()
    client.api.apps.delete.assert_not_called()


def test_app_logs_no_app_id(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when no app_id is provided.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
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
    _authed(mocker)
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
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records("log1", "log2", "log3")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert result.exit_code == 0, result.output
    assert client.api.apps.logs.call_args.args == ("app123",)
    # No window was asked for, so none is sent: the span is the API's own. A
    # window of this command's invention would report nothing for an app whose
    # last line predates it.
    window = client.api.apps.logs.call_args.kwargs
    assert window["start"] is None
    assert window["end"] is None
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert sum("log" in message for message in infos) == 3


def test_app_logs_offset_sends_that_window(mocker: MockFixture):
    """An offset is still the window it asks for, counted back from now.

    Args:
        mocker: The pytest-mock fixture.
    """
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records("log1")

    result = runner.invoke(
        hosting_cli, ["apps", "logs", "app123", "--offset", "3600", "--follow", "false"]
    )

    assert result.exit_code == 0, result.output
    window = client.api.apps.logs.call_args.kwargs
    assert (window["end"] - window["start"]).total_seconds() == 3600


def test_app_logs_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when log retrieval fails.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.logs.side_effect = api_error(409, "Unable to retrieve logs")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    # The server said why; our own generic line would lose it.
    assert errors == ["Unable to retrieve logs"]


def test_app_logs_empty(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """A window with nothing in it says so rather than printing nothing.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records()

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "fake_app_id", "--token", "fake_token", "--follow", "false"],
    )

    assert result.exit_code == 0, result.output
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["No logs found for the specified criteria."]


def test_list_apps_no_project(mocker: MockFixture):
    """Test case when no project is provided."""
    client = _authed(mocker)
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="default_project",
    )
    client.api.apps.list.return_value = [
        app_summary("App1"),
        app_summary("App2", id=uuid.UUID(int=23)),
    ]
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 0, result.output
    mock_get_selected_project.assert_called_once()
    client.api.apps.list.assert_called_once_with(project_id="default_project")
    mock_print_table.assert_called_once_with(
        [
            [str(_APP_ID), "App1", "", str(_PROJECT_ID), "fly", "False"],
            [str(uuid.UUID(int=23)), "App2", "", str(_PROJECT_ID), "fly", "False"],
        ],
        headers=[
            "id",
            "name",
            "description",
            "project_id",
            "provider",
            "disable_secrets",
        ],
    )


def test_list_apps_with_project(mocker: MockFixture):
    """Test case when a project is provided."""
    client = _authed(mocker)
    client.api.apps.list.return_value = [app_summary("App1")]
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(hosting_cli, ["apps", "list", "--project", "project123"])

    assert result.exit_code == 0, result.output
    client.api.apps.list.assert_called_once_with(project_id="project123")
    mock_print_table.assert_called_once_with(
        [[str(_APP_ID), "App1", "", str(_PROJECT_ID), "fly", "False"]],
        headers=[
            "id",
            "name",
            "description",
            "project_id",
            "provider",
            "disable_secrets",
        ],
    )


def test_list_apps_json_output(mocker: MockFixture):
    """Test case for JSON output."""
    client = _authed(mocker)
    client.api.apps.list.return_value = [app_summary("App1")]
    result = runner.invoke(hosting_cli, ["apps", "list", "--json"])

    assert result.exit_code == 0, result.output
    client.api.apps.list.assert_called_once_with(project_id=None)
    assert json.loads(result.stdout) == [
        {
            "id": str(_APP_ID),
            "name": "App1",
            "description": "",
            "project_id": str(_PROJECT_ID),
            "provider": "fly",
            "disable_secrets": False,
        }
    ]


def test_list_apps_error(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test case when an error occurs while listing deployments.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.list.side_effect = api_error(500, "Unable to list deployments")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 1
    client.api.apps.list.assert_called_once_with(project_id=None)
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    # The API's own explanation, not a line of the CLI's own.
    assert errors == ["Unable to list deployments"]


def test_list_apps_empty_response(mocker: MockFixture):
    """Test case when no deployments are found."""
    client = _authed(mocker)
    client.api.apps.list.return_value = []
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 0, result.output
    client.api.apps.list.assert_called_once_with(project_id=None)
    mock_print.assert_called_once_with("[]")


def test_scale_no_args_or_config(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test error when neither args nor config file exists.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
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
    _authed(mocker)

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
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
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
    _authed(mocker)
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
        return_value=app_summary("fake-app"),
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
    _authed(mocker)

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
    _authed(mocker)

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
    _authed(mocker)

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
        return_value=app_summary("fake-app"),
    )
    client = _authed(mocker)
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
        app_id=str(_APP_ID), scale_params=scale_params, client=client
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
        return_value=app_summary("fake-app"),
    )
    client = _authed(mocker)
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
        app_id=str(_APP_ID),
        scale_params=mock_scale_params.return_value,
        client=client,
    )


# The rollback/describe tests invoke the `apps` group directly rather than
# through `hosting_cli` so they don't depend on the reflex-version gate on the
# top-level group callback.


def test_app_rollback_success(mocker: MockFixture):
    """A confirmed rollback calls the API with the resolved app + deployment."""
    client = _authed(mocker)
    client.api.apps.rollback.return_value = None

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    client.api.apps.rollback.assert_called_once_with("app-1", "dep-1")


def test_app_rollback_defaults_to_cancel(mocker: MockFixture):
    """Pressing Enter at the confirm prompt cancels rather than rolling back."""
    client = _authed(mocker)

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--interactive"],
        input="\n",
    )

    assert result.exit_code == 0, result.output
    client.api.apps.rollback.assert_not_called()


def test_app_rollback_error_exits_nonzero(mocker: MockFixture):
    """A refused rollback surfaces and the command exits non-zero."""
    client = _authed(mocker)
    client.api.apps.rollback.side_effect = api_error(409, "rollback failed: nope")

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-id", "app-1", "--no-interactive"],
    )

    assert result.exit_code == 1


def test_app_rollback_resolves_app_name(mocker: MockFixture):
    """--app-name is resolved to an app id before rolling back."""
    client = _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=app_summary())
    client.api.apps.rollback.return_value = None

    result = runner.invoke(
        apps_cli,
        ["rollback", "dep-1", "--app-name", "myapp", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    assert client.api.apps.rollback.call_args.args[0] == str(_APP_ID)


def test_app_describe_sets_note(mocker: MockFixture):
    """Describe forwards the note to the description endpoint."""
    client = _authed(mocker)
    client.api.deployments.set_description.return_value = None

    result = runner.invoke(
        apps_cli,
        ["describe", "dep-1", "--description", "hotfix", "--app-id", "app-1"],
    )

    assert result.exit_code == 0, result.output
    client.api.deployments.set_description.assert_called_once_with(
        "app-1", "dep-1", "hotfix"
    )


def test_app_describe_error_exits_nonzero(mocker: MockFixture):
    """A failed description update exits non-zero."""
    client = _authed(mocker)
    client.api.deployments.set_description.side_effect = api_error(404, "no deployment")

    result = runner.invoke(
        apps_cli,
        ["describe", "dep-1", "--description", "x", "--app-id", "app-1"],
    )

    assert result.exit_code == 1


def test_resolve_app_id_prefers_app_name_over_config(mocker: MockFixture):
    """An explicit --app-name overrides a configured appid rather than being ignored."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value=Config(appid="config-app-id"),
    )
    search = mocker.patch(
        "reflex_cli.utils.hosting.search_app", return_value=app_summary()
    )

    assert _resolve_app_id(None, "myapp", client, interactive=False) == str(_APP_ID)
    search.assert_called_once()


def test_resolve_app_id_falls_back_to_config(mocker: MockFixture):
    """With no explicit app id or name, the configured appid is used."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value=Config(appid="config-app-id"),
    )
    search = mocker.patch("reflex_cli.utils.hosting.search_app")

    assert _resolve_app_id(None, None, client, interactive=False) == "config-app-id"
    search.assert_not_called()


def test_resolve_app_id_explicit_id_wins(mocker: MockFixture):
    """An explicit app id short-circuits both name lookup and config."""
    client = fake_client()
    read_config = mocker.patch("reflex_cli.utils.hosting.read_config")
    search = mocker.patch("reflex_cli.utils.hosting.search_app")

    assert _resolve_app_id("explicit-id", "myapp", client, interactive=False) == (
        "explicit-id"
    )
    search.assert_not_called()
    read_config.assert_not_called()


def test_app_logs_does_not_follow_by_default(mocker: MockFixture):
    """One page is fetched and the command returns, with nothing to answer.

    Following prompts between pages, and a prompt nobody answers is a command
    that never exits -- which is why it is opt-in.
    """
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records(*(f"log{n}" for n in range(150)))
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--interactive"])

    assert result.exit_code == 0, result.output
    client.api.apps.logs.assert_called_once()
    prompt.assert_not_called()


def test_app_logs_follow_needs_a_person_to_answer_the_prompt(mocker: MockFixture):
    """--follow is ignored without interactive mode rather than hanging."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records(*(f"log{n}" for n in range(150)))
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--follow", "true", "--no-interactive"],
    )

    assert result.exit_code == 0, result.output
    client.api.apps.logs.assert_called_once()
    prompt.assert_not_called()


def test_app_logs_follow_pages_when_asked_interactively(mocker: MockFixture):
    """Passing --follow at a terminal still walks the pages."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records(*(f"log{n}" for n in range(150)))
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="exit")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--follow", "true", "--interactive"],
    )

    assert result.exit_code == 0, result.output
    client.api.apps.logs.assert_called_once()
    prompt.assert_called_once()


def test_app_logs_json_output(mocker: MockFixture):
    """The page and its next cursor come back as one document."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records("log1", "log2")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["app_id"] == "app123"
    assert [entry["message"] for entry in document["entries"]] == ["log1", "log2"]
    # The SDK paged the whole window, so there is no cursor to hand back.
    assert document["cursor"] is None
    assert document["error"] is None


def test_app_logs_json_output_never_follows(mocker: MockFixture):
    """--follow cannot page a document that is only complete once."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records(*(f"log{n}" for n in range(150)))
    prompt = mocker.patch("rich.prompt.Prompt.ask", return_value="")

    result = runner.invoke(
        hosting_cli,
        ["apps", "logs", "app123", "--json", "--follow", "true", "--interactive"],
    )

    assert result.exit_code == 0, result.output
    client.api.apps.logs.assert_called_once()
    prompt.assert_not_called()
    assert json.loads(result.stdout)["cursor"] is None


def test_app_logs_json_output_when_empty(mocker: MockFixture):
    """No logs is an empty document rather than a warning to parse."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records()

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

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "stopped": True,
        "message": "app stopped",
    }


def test_stop_app_json_output_on_failure(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A refusal exits non-zero rather than claiming the app was stopped.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.stop.side_effect = api_error(409, "app is deploying")

    result = runner.invoke(hosting_cli, ["apps", "stop", "app123", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["app is deploying"]


def test_start_app_json_output(mocker: MockFixture):
    """Starting an app reports the outcome as a document."""
    _authed(mocker)

    result = runner.invoke(hosting_cli, ["apps", "start", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "started": True,
        "message": "app started",
    }


def test_delete_app_json_output(mocker: MockFixture):
    """Deleting an app reports the outcome as a document."""
    client = _authed(mocker)
    client.api.apps.get.return_value = app("test-app")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": True,
        "message": "app deleted",
    }


def test_delete_app_json_output_on_failure(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A refusal exits non-zero rather than claiming the app was deleted.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.get.return_value = app("test-app")
    client.api.apps.delete.side_effect = api_error(409, "app is deploying")

    result = runner.invoke(hosting_cli, ["apps", "delete", "app123", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["app is deploying"]


def test_app_logs_json_output_when_unreadable(mocker: MockFixture):
    """Logs that could not be read are distinguishable from none existing."""
    client = _authed(mocker)
    client.api.apps.logs.side_effect = api_error(500, "Unable to retrieve logs.")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""


def test_delete_app_json_output_when_cancelled(mocker: MockFixture):
    """Declining the confirmation is reported rather than left silent."""
    client = _authed(mocker)
    client.api.apps.get.return_value = app("test-app")
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
    client.api.apps.delete.assert_not_called()


def test_app_rollback_json_output(mocker: MockFixture):
    """A rollback reports what it rolled back to."""
    _authed(mocker)

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
    client = _authed(mocker)
    client.api.deployments.build_logs.return_value = "step 1\nstep 2"

    result = runner.invoke(hosting_cli, ["apps", "build-logs", "dep-1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "logs": "step 1\nstep 2",
    }


def test_deployment_status_json_output(mocker: MockFixture):
    """A status read reports the status and whether it is a failure."""
    client = _authed(mocker)
    client.api.deployments.status.return_value = "deploying"

    result = runner.invoke(hosting_cli, ["apps", "status", "dep-1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "status": "deploying",
        "success": True,
    }


def test_deployment_status_json_output_while_watching(mocker: MockFixture):
    """The watch hands back its last status, so nothing is asked again."""
    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=hosting.WatchResult(
            hosting.WatchOutcome.SUCCEEDED, "completed successfully"
        ),
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
    client.api.deployments.status.assert_not_called()


def test_deployment_status_json_output_when_the_watch_stopped_early(
    mocker: MockFixture,
):
    """A watch that could not see the end says so rather than claiming success."""
    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=hosting.WatchResult(hosting.WatchOutcome.UNFINISHED, "Building"),
    )

    result = runner.invoke(
        hosting_cli, ["apps", "status", "dep-1", "--watch", "--json"]
    )

    # Not a failure: the deployment is still running, and the document says so
    # by refusing to answer rather than by guessing.
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "status": "Building",
        "success": None,
    }
    client.api.deployments.status.assert_not_called()


def test_deployment_status_json_output_when_the_watch_failed(mocker: MockFixture):
    """A deployment that ended without going live exits non-zero."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=hosting.WatchResult(hosting.WatchOutcome.FAILED, "Failed"),
    )

    result = runner.invoke(
        hosting_cli, ["apps", "status", "dep-1", "--watch", "--json"]
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "deployment_id": "dep-1",
        "status": "Failed",
        "success": False,
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
    client = _authed(mocker)
    client.api.apps.list.return_value = [app_summary("App1")]
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project", return_value="project-1"
    )

    result = runner.invoke(hosting_cli, ["apps", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "id": str(_APP_ID),
            "name": "App1",
            "description": "",
            "project_id": str(_PROJECT_ID),
            "provider": "fly",
            "disable_secrets": False,
        }
    ]


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
    client = _authed(mocker)
    client.api.deployments.status.return_value = status

    result = runner.invoke(hosting_cli, ["apps", "status", "12345", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "deployment_id": "12345",
        "status": status,
        "success": success,
    }


def test_app_logs_json_output_names_the_servers_reason(mocker: MockFixture):
    """A refusal the server explained is reported in its own words."""
    client = _authed(mocker)
    client.api.apps.logs.side_effect = api_error(409, "app is not running")

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""


def test_delete_app_json_output_when_app_is_gone(mocker: MockFixture):
    """An unknown app ID exits non-zero but still prints the JSON result."""
    client = _authed(mocker)
    client.api.apps.get.side_effect = api_error(404, "no such app")

    result = runner.invoke(
        hosting_cli, ["apps", "delete", "app123", "--json", "--no-interactive"]
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "app_id": "app123",
        "deleted": False,
        "message": "No application found with ID 'app123'",
    }
    client.api.apps.delete.assert_not_called()


def test_list_apps_expired_token(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """A token that expired since it was validated says what to do about it.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.apps.list.side_effect = api_error(401, "expired")

    result = runner.invoke(hosting_cli, ["apps", "list"])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["You are not authenticated. Run `reflex login` to authenticate."]


def test_scale_app_expired_token_says_to_log_in(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An unusable token is not reported as a scale that failed.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    mocker.patch("reflex_cli.core.config.Config.exists", return_value=False)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app", return_value=app_summary("fake-app")
    )
    client.api.apps.scale.side_effect = api_error(401, "expired")

    result = runner.invoke(
        hosting_cli, ["apps", "scale", "--app-name", "random", "--vmtype", "c1m1"]
    )

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["You are not authenticated. Run `reflex login` to authenticate."]


def test_app_logs_stops_after_one_page(mocker: MockFixture):
    """Without --follow the command reads a page, not the whole window."""
    client = _authed(mocker)
    pulled = 0

    def records() -> Iterator[LogRecord]:
        nonlocal pulled
        for n in range(500):
            pulled += 1
            yield log_record(f"log{n}")

    client.api.apps.logs.return_value = records()

    result = runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert result.exit_code == 0, result.output
    assert pulled == 100


def test_app_logs_reads_newest_first(mocker: MockFixture):
    """The most recent lines are the ones a single page should carry."""
    client = _authed(mocker)
    client.api.apps.logs.return_value = log_records("newest")

    runner.invoke(hosting_cli, ["apps", "logs", "app123", "--follow", "false"])

    assert client.api.apps.logs.call_args.kwargs["order"] == "newest_first"
