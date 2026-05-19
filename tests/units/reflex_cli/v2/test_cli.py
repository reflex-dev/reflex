from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from unittest.mock import MagicMock

import click
import httpx
import pytest
from packaging import version
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.utils import hosting
from reflex_cli.v2 import cli


def test_login_success_existing_token(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.authenticated_token",
        return_value=("fake-code", {}),
    )
    mock_authenticate_on_browser = mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value=("fake-token", {}),
    )
    cli.login()
    mock_authenticate_on_browser.assert_not_called()


def test_login_success_on_browser(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.authenticated_token",
        side_effect=[("", {}), ("fake-token", {})],
    )

    mock_authenticate_on_browser = mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value=("fake-token", {}),
    )
    cli.login()
    mock_authenticate_on_browser.assert_called_once()


def test_login_failure(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.authenticated_token",
        return_value=("", {}),
    )
    mock_authenticate_on_browser = mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser", return_value=("", {})
    )
    with pytest.raises(SystemExit):
        cli.login()
    mock_authenticate_on_browser.assert_called_once()


def test_logout(mocker: MockFixture):
    mock_delete_token = mocker.patch(
        "reflex_cli.utils.hosting.delete_token_from_config",
    )
    mock_success = mocker.patch(
        "reflex_cli.utils.console.success",
    )

    cli.logout()
    mock_delete_token.assert_called_once()
    mock_success.assert_called_once_with("Successfully logged out.")


@pytest.fixture
def mock_export_fn():
    rx_version = version.parse(importlib.metadata.version("reflex"))
    breaking_version = version.parse("0.7.6")
    _mock_export_fn = (
        (lambda arg1, arg2, arg3, arg4, arg5, arg6: ...)
        if rx_version <= breaking_version
        else (lambda arg1, arg2, arg3, arg4, arg5, arg6, arg7: ...)
    )

    return MagicMock(side_effect=_mock_export_fn)


@pytest.fixture
def mock_export_import_error_fn():
    def _mock_export_fn(
        arg1: str, arg2: str, arg3: str, arg4: bool, arg5: bool, arg6: bool
    ) -> None:
        raise ImportError

    return MagicMock(side_effect=_mock_export_fn)


def test_deploy_non_interactive_with_invalid_app_name(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="", export_fn=MagicMock(), interactive=False)


@pytest.mark.parametrize(
    "hostname",
    [{"error": "fake-error"}, {"hostname": "fake-hostname", "server": "fake-server"}],
)
def test_deploy_non_interactive_app_not_found(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    hostname: dict[str, str],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=None,
    )
    create_app = mocker.patch(
        "reflex_cli.utils.hosting.create_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )

    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value=hostname,
    )
    create_deployment = mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"error": "fake-error"},
    )
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"error": "fake-error"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )

    if "error" in hostname:
        with pytest.raises(click.exceptions.Exit):
            cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
        create_app.assert_called_once()
        return

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
    create_app.assert_called_once()
    create_deployment.assert_called_once()
    watch_deployment.assert_called_once()


def test_deploy_create_deployment_failure(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={"name": "fake-app", "id": "fake-id"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    create_deployment = mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value="deployment failed",
    )
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
    create_deployment.assert_called_once()
    watch_deployment.assert_not_called()


def test_deploy_non_interactive_project_name(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        return_value={"name": "fake-project"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    search_project = mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value={"name": "fake-project", "id": "fake-project-id"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )
    create_deployment = mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"deployment_id": "fake-deployment-id"},
    )
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        project_name="fake-project",
    )
    search_project.assert_called_once()
    create_deployment.assert_called_once()
    watch_deployment.assert_called_once()


def test_deploy_non_interactive_project_name_multiple_values(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        return_value={"name": "fake-project"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "fake-project",
            "id": "fake-id",
        },
        {
            "name": "fake-project",
            "id": "another-fake-id",
        },
    ]
    mocker.patch("httpx.get", return_value=mock_response)

    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    console_error = mocker.patch("reflex_cli.utils.console.error")

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            project_name="fake-project",
        )
    console_error.assert_called_once_with(
        "Multiple projects with the name 'fake-project' found. Please provide a unique name."
    )


def test_deploy_interactive_project_name_multiple_values(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    get_project = mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        return_value={"name": "fake-project"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
        },
    )
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "fake-project",
            "id": "fake-id",
        },
        {
            "name": "fake-project",
            "id": "another-fake-id",
        },
    ]
    mocker.patch("httpx.get", return_value=mock_response)

    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"deployment_id": "fake-deployment-id"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="0")

    cli.deploy(
        app_name="fake-app", export_fn=mock_export_fn, project_name="fake-project"
    )
    console_ask.assert_called_once()
    get_project.assert_called_once_with(
        "fake-id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )


@pytest.mark.parametrize(
    "app_name, app_id",
    [
        (None, None),
        ("", ""),
    ],
)
def test_deploy_non_interactive_no_app_name_and_id(
    mocker: MockerFixture, app_name: str | None, app_id: str | None
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    console_error = mocker.patch("reflex_cli.utils.console.error")

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name=app_name, app_id=app_id, export_fn=MagicMock(), interactive=False
        )

    console_error.assert_called_once_with(
        "Please provide a valid app name or ID for the deployed instance."
    )


def test_deploy_non_interactive_export_failure(
    mocker: MockerFixture, mock_export_import_error_fn: MagicMock
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value={"name": "fake-app", "id": "fake-id"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    create_deployment = mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"deployment_id": "fake-deployment-id"},
    )
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_import_error_fn,
            interactive=False,
        )

    create_deployment.assert_not_called()
    watch_deployment.assert_not_called()


def test_deploy_envfile_missing_python_dotenv_exits(
    mocker: MockerFixture,
    mock_export_fn: MagicMock,
):
    """Deploy should exit when --envfile is used without python-dotenv."""
    import builtins

    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
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
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    create_deployment = mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"deployment_id": "fake-deployment-id"},
    )
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    console_error = mocker.patch("reflex_cli.utils.console.error")

    real_import = builtins.__import__

    def _mock_import(name: str, *args, **kwargs):
        if name == "dotenv":
            raise ImportError
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=_mock_import)

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            envfile=".env",
        )

    console_error.assert_any_call(
        """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
    )
    mock_export_fn.assert_not_called()
    create_deployment.assert_not_called()
    watch_deployment.assert_not_called()


def test_deploy_non_interactive_with_invalid_project(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        side_effect=httpx.HTTPStatusError(
            "HTTP Error",
            request=mocker.Mock(),
            response=mocker.Mock(json=lambda: {"detail": "project does not exist"}),
        ),
    )
    mock_error = mocker.patch(
        "reflex_cli.utils.console.error",
    )
    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="app-name",
            export_fn=MagicMock(),
            project="fake-project",
            interactive=False,
        )

    mock_error.assert_called_with("project does not exist")


def test_deploy_create_deployment_multiple_apps_non_interactive(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "fake-app", "id": "fake-id"},
        {"name": "fake-app", "id": "another-fake-id"},
    ]
    mocker.patch("httpx.get", return_value=mock_response)

    mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    console_error = mocker.patch("reflex_cli.utils.console.error")
    mocker.patch(
        "reflex_cli.utils.hosting.authenticated_token",
        return_value=("fake-code", {}),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value=("fake-token", {}),
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            token="fake-token",
        )
    console_error.assert_called_once_with(
        "Multiple apps with the name 'fake-app' found. Please provide a unique name."
    )


def test_deploy_create_deployment_multiple_apps_interactive(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_deployment_args",
        return_value="success",
    )
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "fake-app",
            "id": "fake-id",
            "project_id": "fake-project",
            "project": {"name": "fake-project", "id": "fake-project-id"},
        },
        {
            "name": "fake-app",
            "id": "another-fake-id",
            "project_id": "another-fake-project",
            "project": {
                "name": "another-fake-project",
                "id": "another-fake-project-id",
            },
        },
    ]
    mocker.patch("httpx.get", return_value=mock_response)

    get_host_name = mocker.patch(
        "reflex_cli.utils.hosting.get_hostname",
        return_value={"hostname": "fake-hostname", "server": "fake-server"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.create_deployment",
        return_value={"deployment_id": "fake-deployment-id"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authenticated_token",
        return_value=("fake-code", {}),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value=("fake-token", {}),
    )
    mocker.patch("reflex_cli.utils.console.print")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="0")

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)
    console_ask.assert_called_once()
    get_host_name.assert_called_once_with(
        app_id="fake-id",
        app_name="fake-app",
        hostname=None,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
