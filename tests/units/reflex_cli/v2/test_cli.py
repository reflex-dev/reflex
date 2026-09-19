from __future__ import annotations

import importlib.metadata
import logging
import uuid
from collections.abc import Callable
from unittest.mock import MagicMock

import click
import pytest
from packaging import version
from pytest_mock import MockerFixture, MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_build_sdk.types import (
    App,
    AppSummary,
    FullDeployChange,
    GcpConnection,
    GcpStatus,
    HostnameReservation,
    Project,
    ProjectRef,
    ProjectTier,
    ProviderChange,
)
from reflex_cli.v2 import cli

from .utils import FakeClient, api_error, fake_client

_APP_ID = uuid.UUID(int=51)
_PROJECT_ID = uuid.UUID(int=52)
_RESERVATION = HostnameReservation(
    frontend_url="fake-hostname", backend_url="fake-server"
)


def _authed(mocker: MockFixture):
    """Patch the client lookup and hand back a client with a fresh API mock.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The client the deploy under test will receive.
    """
    client = fake_client()
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.apps.set_provider.return_value = ProviderChange(provider="fly")
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )
    return client


def app_summary(name: str = "fake-app", **fields) -> AppSummary:
    """Build an app as a search reports one.

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
        **fields,
    })


def app(name: str = "fake-app", **fields) -> App:
    """Build an app as `apps get` reports one.

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
        **fields,
    })


def project(name: str = "fake-project", **fields) -> Project:
    """Build a project as the API reports one.

    Args:
        name: The project's name.
        fields: Overrides for its other fields.

    Returns:
        The project.
    """
    return Project(**{
        "id": _PROJECT_ID,
        "name": name,
        "tier": ProjectTier(name="Pro", cpu_quota=4, ram_quota=8, deployment_quota=10),
        "owner_id": uuid.UUID(int=53),
        "owner_email": "owner@example.com",
        "seats": 1,
        "apps": [],
        **fields,
    })


def _log_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


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


def test_logout(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    mock_delete_token = mocker.patch(
        "reflex_cli.utils.hosting.delete_token_from_config",
    )

    cli.logout()
    mock_delete_token.assert_called_once()
    assert _log_messages(caplog, SUCCESS) == ["Successfully logged out."]


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
    # Takes *args so it raises ImportError under both export_fn arities: reflex
    # > 0.7.6 passes 7 arguments, and a fixed 6-argument signature would raise
    # TypeError there instead, never exercising the ImportError path.
    def _mock_export_fn(*args: str | bool) -> None:
        raise ImportError

    return MagicMock(side_effect=_mock_export_fn)


def test_deploy_non_interactive_with_invalid_app_name(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    _authed(mocker)

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="", export_fn=MagicMock(), interactive=False)


@pytest.mark.parametrize("refused", [True, False])
def test_deploy_non_interactive_app_not_found(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    refused: bool,
):
    """A missing app is created, and a refused hostname aborts the deploy.

    Args:
        mocker: The pytest-mock fixture.
        mock_export_fn: The export the deploy drives.
        refused: Whether the hostname reservation is refused.
    """
    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    client.api.apps.create.return_value = app("fake-app")
    if refused:
        client.api.apps.reserve_hostname.side_effect = api_error(409, "hostname taken")
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value=True,
    )

    if refused:
        with pytest.raises(click.exceptions.Exit):
            cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
        client.api.apps.create.assert_called_once()
        return

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
    client.api.apps.create.assert_called_once()
    client.api.deployments.create.assert_called_once()
    watch_deployment.assert_called_once()


def test_deploy_create_deployment_failure(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.deployments.create.side_effect = api_error(400, "deployment failed")
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)
    client.api.deployments.create.assert_called_once()
    watch_deployment.assert_not_called()


def test_deploy_non_interactive_project_name(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _authed(mocker)
    client.api.projects.get.return_value = project("fake-project")
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    search_project = mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="fake-project"),
    )
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        project_name="fake-project",
    )
    search_project.assert_called_once()
    client.api.deployments.create.assert_called_once()
    watch_deployment.assert_called_once()


def test_deploy_non_interactive_project_name_multiple_values(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    caplog: pytest.LogCaptureFixture,
):
    client = _authed(mocker)
    client.api.projects.search.return_value = [
        ProjectRef(id=_PROJECT_ID, name="fake-project"),
        ProjectRef(id=uuid.UUID(int=71), name="fake-project"),
    ]
    client.api.projects.get.return_value = project("fake-project")
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )

    client.api.apps.reserve_hostname.return_value = _RESERVATION
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            project_name="fake-project",
        )
    assert _log_messages(caplog, logging.ERROR) == [
        "Multiple projects with the name 'fake-project' found. Please provide a unique name."
    ]


def test_deploy_interactive_project_name_multiple_values(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _authed(mocker)
    client.api.projects.search.return_value = [
        ProjectRef(id=_PROJECT_ID, name="fake-project"),
        ProjectRef(id=uuid.UUID(int=71), name="fake-project"),
    ]
    client.api.projects.get.return_value = project("fake-project")
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )

    client.api.apps.reserve_hostname.return_value = _RESERVATION
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value={},
    )
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )

    def answer(question: str, **kwargs):
        # "0" picks the first of the two matches; everything else is confirmed.
        return "0" if "would you like to use" in question else "y"

    console_ask = mocker.patch("reflex_cli.utils.console.ask", side_effect=answer)

    cli.deploy(
        app_name="fake-app", export_fn=mock_export_fn, project_name="fake-project"
    )
    # One prompt: the project to use, resolved out of the two that matched.
    assert any(
        "would you like to use" in call.args[0] for call in console_ask.call_args_list
    )
    client.api.projects.get.assert_any_call(str(_PROJECT_ID))


@pytest.mark.parametrize(
    "app_name, app_id",
    [
        (None, None),
        ("", ""),
    ],
)
def test_deploy_non_interactive_no_app_name_and_id(
    mocker: MockerFixture,
    app_name: str | None,
    app_id: str | None,
    caplog: pytest.LogCaptureFixture,
):
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name=app_name, app_id=app_id, export_fn=MagicMock(), interactive=False
        )

    assert _log_messages(caplog, logging.ERROR) == [
        "Please provide a valid app name or ID for the deployed instance."
    ]


def test_deploy_non_interactive_export_failure(
    mocker: MockerFixture, mock_export_import_error_fn: MagicMock
):
    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_import_error_fn,
            interactive=False,
        )

    client.api.deployments.create.assert_not_called()
    watch_deployment.assert_not_called()


def test_deploy_envfile_missing_python_dotenv_exits(
    mocker: MockerFixture,
    mock_export_fn: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """Deploy should exit when --envfile is used without python-dotenv.

    Args:
        mocker: The pytest-mock fixture.
        mock_export_fn: The mocked export function.
        caplog: The pytest log capture fixture.
    """
    import builtins

    client = _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    watch_deployment = mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
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

    assert (
        """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
        in _log_messages(caplog, logging.ERROR)
    )
    mock_export_fn.assert_not_called()
    client.api.deployments.create.assert_not_called()
    watch_deployment.assert_not_called()


def test_deploy_non_interactive_with_invalid_project(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    client = _authed(mocker)
    client.api.projects.get.side_effect = api_error(404, "project does not exist")
    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="app-name",
            export_fn=MagicMock(),
            project="fake-project",
            interactive=False,
        )

    errors = _log_messages(caplog, logging.ERROR)
    assert errors[-1] == "project does not exist"


def test_deploy_create_deployment_multiple_apps_non_interactive(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    caplog: pytest.LogCaptureFixture,
):
    client = _authed(mocker)
    client.api.apps.search.return_value = [
        app_summary("fake-app"),
        app_summary("fake-app", id=uuid.UUID(int=72)),
    ]
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )

    client.api.apps.reserve_hostname.return_value = _RESERVATION
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
    assert _log_messages(caplog, logging.ERROR) == [
        "Multiple apps with the name 'fake-app' found. Please provide a unique name."
    ]


def test_deploy_create_deployment_multiple_apps_interactive(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _authed(mocker)
    client.api.apps.search.return_value = [
        app_summary("fake-app"),
        app_summary("fake-app", id=uuid.UUID(int=72)),
    ]
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="fake-project",
    )

    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.deployments.create.return_value = uuid.UUID(int=41)
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

    def answer(question: str, **kwargs):
        # "0" picks the first of the two matches; everything else is confirmed.
        return "0" if "would you like to use" in question else "y"

    console_ask = mocker.patch("reflex_cli.utils.console.ask", side_effect=answer)

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)
    assert any(
        "would you like to use" in call.args[0] for call in console_ask.call_args_list
    )
    client.api.apps.reserve_hostname.assert_called_once_with(
        _APP_ID, "fake-app", hostname=None
    )


def _common_deploy_mocks(mocker: MockerFixture, *, selected_project: str | None = None):
    """Set up a deploy that reaches the submit without any of it being real.

    Args:
        mocker: The pytest-mock fixture.
        selected_project: The project the config has selected, if any.

    Returns:
        The client the deploy under test will receive.
    """
    client = fake_client(user_id="user-uuid")
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    client.api.apps.set_provider.return_value = ProviderChange(provider="fly")
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value=selected_project,
    )
    mocker.patch(
        "reflex_cli.utils.hosting.watch_deployment_status",
        return_value={"status": "ready"},
    )
    return client


def test_deploy_interactive_existing_app_names_its_project(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    client.api.projects.get.return_value = project("RealProject")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)

    client.api.projects.get.assert_called_once_with(str(_PROJECT_ID))
    prompts = [call.args[0] for call in console_ask.call_args_list]
    deploy_prompt = next(p for p in prompts if p.startswith("Deploy to app"))
    assert "RealProject" in deploy_prompt


def test_deploy_interactive_new_app_resolved_project_reuses_validation(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="ChosenProject"),
    )
    client.api.projects.get.return_value = project("ChosenProject")
    client.api.apps.create.return_value = app("fake-app")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        project_name="ChosenProject",
        interactive=True,
    )

    client.api.projects.get.assert_called_once_with(str(_PROJECT_ID))
    client.api.apps.create.assert_called_once()
    create_prompt = next(
        call.args[0]
        for call in console_ask.call_args_list
        if call.args and call.args[0].startswith("Create and deploy")
    )
    assert "ChosenProject" in create_prompt


def test_deploy_interactive_new_app_non_default_project_shows_name(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker, selected_project="default-project-id")
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="OtherProject"),
    )
    client.api.projects.get.return_value = project("OtherProject")
    client.api.apps.create.return_value = app("fake-app")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        project_name="OtherProject",
        interactive=True,
    )

    client.api.apps.create.assert_called_once()
    create_prompt = next(
        call.args[0]
        for call in console_ask.call_args_list
        if call.args and call.args[0].startswith("Create and deploy")
    )
    assert "OtherProject" in create_prompt


def test_deploy_interactive_existing_app_falls_back_to_the_project_id(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    # The project could not be read, so the prompt falls back to its id.
    client.api.projects.get.side_effect = api_error(403, "no access")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)

    deploy_prompt = next(
        call.args[0]
        for call in console_ask.call_args_list
        if call.args and call.args[0].startswith("Deploy to app")
    )
    assert str(_PROJECT_ID) in deploy_prompt


def test_deploy_interactive_existing_app_user_declines_exits_cleanly(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("RealProject"),
    )
    mocker.patch("reflex_cli.utils.console.ask", return_value="n")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)

    assert exc_info.value.exit_code == 0
    client.api.deployments.create.assert_not_called()


def test_deploy_interactive_new_app_user_declines_create_exits_cleanly(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="ChosenProject"),
    )
    client.api.projects.get.return_value = project("ChosenProject")
    mocker.patch("reflex_cli.utils.console.ask", side_effect=["y", "n"])

    with pytest.raises(click.exceptions.Exit) as exc_info:
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            project_name="ChosenProject",
            interactive=True,
        )

    assert exc_info.value.exit_code == 0
    client.api.apps.create.assert_not_called()
    client.api.deployments.create.assert_not_called()


def test_deploy_interactive_get_project_failure_exits_before_prompting(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="BrokenProject"),
    )
    client.api.projects.get.side_effect = api_error(400, "bad project")
    search_app = mocker.patch("reflex_cli.utils.hosting.search_app")
    console_ask = mocker.patch("reflex_cli.utils.console.ask")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            project_name="BrokenProject",
            interactive=True,
        )

    assert exc_info.value.exit_code == 1
    console_ask.assert_not_called()
    search_app.assert_not_called()
    client.api.apps.create.assert_not_called()


def test_deploy_interactive_new_app_no_selected_project_shows_default_name(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    client = _common_deploy_mocks(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    client.api.projects.get.return_value = project("MyPersonalProject")
    client.api.apps.create.return_value = app("fake-app")
    console_ask = mocker.patch("reflex_cli.utils.console.ask", return_value="y")

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=True)

    client.api.projects.get.assert_called_once_with("user-uuid")
    client.api.apps.create.assert_called_once()
    create_prompt = next(
        call.args[0]
        for call in console_ask.call_args_list
        if call.args and call.args[0].startswith("Create and deploy")
    )
    assert "MyPersonalProject" in create_prompt


def test_deploy_empty_project_in_config_is_not_forwarded_to_create_app(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    from reflex_cli.core.config import Config

    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.read_config",
        return_value=Config(name="fake-app", project="   "),
    )
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    client.api.apps.create.return_value = app("fake-app")

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)

    client.api.projects.get.assert_not_called()
    client.api.apps.create.assert_called_once()
    assert client.api.apps.create.call_args.kwargs.get("project_id") is None


def _deploy_call_recorder(mocker: MockerFixture) -> tuple[MagicMock, FakeClient]:
    """Set up a succeeding non-interactive deploy on an existing app.

    Returns:
        A parent mock recording ``set_instance_bounds`` and ``client.api.deployments.create``
        in call order.

    """
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app"),
    )
    client.api.deployments.create.return_value = uuid.UUID(int=41)
    recorder = MagicMock()
    recorder.attach_mock(
        mocker.patch("reflex_cli.utils.hosting.set_instance_bounds", return_value=None),
        "set_instance_bounds",
    )
    recorder.attach_mock(client.api.deployments.create, "create_deployment")
    return recorder, client


def test_deploy_forwards_vmtype_to_create_deployment(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """--vmtype reaches the deployment submit unchanged, with no CLI validation."""
    recorder, _ = _deploy_call_recorder(mocker)

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        vmtype="c2m2",
    )

    assert recorder.create_deployment.call_args.kwargs["vm_type"] == "c2m2"


@pytest.mark.parametrize(
    ("min_instances", "max_instances"),
    [(1, 4), (2, None), (None, 8)],
)
def test_deploy_sets_instance_bounds_before_submitting(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    min_instances: int | None,
    max_instances: int | None,
):
    """Bounds are applied to the app before the deployment that reads them."""
    recorder, _ = _deploy_call_recorder(mocker)

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        min_instances=min_instances,
        max_instances=max_instances,
    )

    assert [call[0] for call in recorder.mock_calls] == [
        "set_instance_bounds",
        "create_deployment",
    ]
    bounds_kwargs = recorder.set_instance_bounds.call_args.kwargs
    assert bounds_kwargs["app_id"] == str(_APP_ID)
    assert bounds_kwargs["min_instances"] == min_instances
    assert bounds_kwargs["max_instances"] == max_instances


def test_deploy_without_instance_bounds_flags_skips_the_call(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """An app keeps its platform defaults when neither bound is passed."""
    recorder, _ = _deploy_call_recorder(mocker)

    cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)

    recorder.set_instance_bounds.assert_not_called()
    recorder.create_deployment.assert_called_once()


def test_deploy_failed_export_does_not_apply_instance_bounds(
    mocker: MockerFixture,
    mock_export_import_error_fn: Callable[[str, str, str, bool, bool, bool], None],
):
    """A build that never produces a deployment leaves the bounds untouched."""
    recorder, _ = _deploy_call_recorder(mocker)

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_import_error_fn,
            interactive=False,
            min_instances=3,
            max_instances=9,
        )

    recorder.set_instance_bounds.assert_not_called()
    recorder.create_deployment.assert_not_called()


@pytest.mark.parametrize(
    ("submit_result", "expected_exc"),
    [
        # The submit is refused...
        ({"side_effect": api_error(413, "too large")}, click.exceptions.Exit),
        # ...or dies before answering at all (transport error, interrupt).
        ({"side_effect": KeyError("no route")}, KeyError),
        ({"side_effect": KeyboardInterrupt()}, KeyboardInterrupt),
    ],
)
def test_deploy_warns_when_bounds_outlive_a_failed_submit(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    submit_result: dict[str, object],
    expected_exc: type[BaseException],
    caplog: pytest.LogCaptureFixture,
):
    """Bounds that stuck without a deployment are called out on every exit path."""
    _, client = _deploy_call_recorder(mocker)
    client.api.deployments.create.configure_mock(**submit_result)

    with pytest.raises(expected_exc):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            min_instances=3,
        )

    assert any(
        "even though this deploy failed" in msg
        for msg in _log_messages(caplog, logging.WARNING)
    )


def test_deploy_hedges_when_the_bounds_response_is_lost(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    caplog: pytest.LogCaptureFixture,
):
    """A dropped response leaves the outcome unknown, so neither is asserted."""
    recorder, _ = _deploy_call_recorder(mocker)
    recorder.set_instance_bounds.side_effect = KeyError("no route")

    with pytest.raises(KeyError):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            min_instances=3,
        )

    warning = next(
        msg
        for msg in _log_messages(caplog, logging.WARNING)
        if "instance bounds" in msg
    )
    assert "may or may not have been applied" in warning
    recorder.create_deployment.assert_not_called()


def test_deploy_does_not_warn_about_bounds_it_never_applied(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    caplog: pytest.LogCaptureFixture,
):
    """A deploy that failed without touching the bounds stays quiet about them."""
    recorder, _ = _deploy_call_recorder(mocker)
    recorder.create_deployment.side_effect = api_error(413, "too large")

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)

    assert not any(
        "instance bounds" in msg for msg in _log_messages(caplog, logging.WARNING)
    )


@pytest.mark.parametrize(
    "detail",
    [
        "set instance bounds failed: min_instances must be <= max_instances",
        "set instance bounds failed: platform does not support instance bounds",
        "set instance bounds failed: a scale operation is already running",
    ],
)
def test_deploy_rejected_instance_bounds_aborts_before_submitting(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    detail: str,
    caplog: pytest.LogCaptureFixture,
):
    """A rejected bound surfaces the server message and stops the deploy."""
    recorder, _ = _deploy_call_recorder(mocker)
    recorder.set_instance_bounds.return_value = detail

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            min_instances=5,
            max_instances=1,
        )

    assert _log_messages(caplog, logging.ERROR) == [detail]
    recorder.create_deployment.assert_not_called()


def test_deploy_forwards_strategy_to_create_deployment(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """--strategy reaches the deployment submit without a config file."""
    recorder, _ = _deploy_call_recorder(mocker)

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        strategy="rolling",
    )

    assert recorder.create_deployment.call_args.kwargs["strategy"] == "rolling"


def test_deploy_applies_full_deploy_before_reserving_the_hostname(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """The hosting mode is written first: the reserved URL is compiled in."""
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app", provider="gcp"),
    )
    client.api.apps.set_full_deploy.return_value = FullDeployChange(
        full_deploy=True, stopped=False, stop_confirmed=True
    )
    client.api.apps.reserve_hostname.return_value = _RESERVATION
    recorder = MagicMock()
    recorder.attach_mock(client.api.apps.set_full_deploy, "set_app_full_deploy")
    recorder.attach_mock(client.api.apps.reserve_hostname, "get_hostname")

    cli.deploy(
        app_name="fake-app",
        export_fn=mock_export_fn,
        interactive=False,
        full_deploy=True,
    )

    assert [call[0] for call in recorder.mock_calls] == [
        "set_app_full_deploy",
        "get_hostname",
    ]
    recorder.set_app_full_deploy.assert_called_once_with(_APP_ID, True)


def test_deploy_validates_arguments_before_changing_the_hosting_mode(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """A rejected argument must not take a running app down first."""
    client = _common_deploy_mocks(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_app",
        return_value=app_summary("fake-app", provider="gcp"),
    )
    client.api.deployments.check.side_effect = api_error(400, "unknown vmtype")

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            full_deploy=True,
            vmtype="nope",
        )

    client.api.apps.set_full_deploy.assert_not_called()
    # And no hostname was reserved for a deploy that was never going to submit.
    client.api.apps.reserve_hostname.assert_not_called()


def test_apply_full_deploy_skips_the_call_when_turning_it_off_elsewhere(
    mocker: MockFixture,
):
    """`--no-full-deploy` off GCP is a no-op, not a refusal.

    The mode is GCP-only and the provider write clears it for an app leaving
    GCP, so there is nothing to turn off -- and refusing would fail every
    Reflex Cloud deploy driven by a config file carrying `full_deploy: false`.
    """
    client = fake_client()

    assert cli._apply_full_deploy(app("myapp"), False, "fly", client) is (False)
    client.api.apps.set_full_deploy.assert_not_called()


def test_apply_full_deploy_hedges_when_the_response_is_lost(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A dropped connection may still have stopped the app; say so."""
    client = fake_client()
    client.api.apps.set_full_deploy.side_effect = ConnectionError("dropped")

    with pytest.raises(ConnectionError):
        cli._apply_full_deploy(app("myapp"), True, "gcp", client)

    # The warning context is never entered on this path, so the hedge has to
    # come from the call itself.
    assert "Lost contact" in _log_messages(caplog, logging.WARNING)[-1]


def test_deploy_full_deploy_on_reflex_cloud_never_reaches_the_server(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
):
    """Full deploy is a provider capability, so the CLI refuses it up front."""
    recorder, client = _deploy_call_recorder(mocker)

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(
            app_name="fake-app",
            export_fn=mock_export_fn,
            interactive=False,
            full_deploy=True,
        )

    client.api.apps.set_full_deploy.assert_not_called()
    recorder.create_deployment.assert_not_called()


def test_resolve_deploy_provider_explicit_gcp_switches(mocker: MockFixture):
    """--provider gcp on a fly app switches it and returns the new provider."""
    client = fake_client()
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app, "gcp", interactive=False, app_was_created=True, client=client
    )
    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=None, service_name=None
    )


def test_resolve_deploy_provider_hostname_names_the_gcp_service(
    mocker: MockFixture,
):
    """On the deploy that first lands on GCP, --hostname doubles as the service name."""
    client = fake_client()
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app,
        "gcp",
        interactive=False,
        app_was_created=True,
        client=client,
        hostname="Sales-Dashboard",
    )
    assert result == "gcp"
    # Lowercased into the service-name grammar before it is sent.
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=None, service_name="sales-dashboard"
    )


def test_resolve_deploy_provider_unusable_hostname_lets_the_server_mint(
    mocker: MockFixture,
):
    """A hostname the service-name grammar refuses is skipped, not fatal."""
    client = fake_client()
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app,
        "gcp",
        interactive=False,
        app_was_created=True,
        client=client,
        # Valid DNS label, invalid Cloud Run service name (leading digit).
        hostname="2048game",
    )
    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=None, service_name=None
    )


def test_gcp_service_name_from_hostname_grammar():
    """Only hostnames Cloud Run would accept as service names pass through."""
    assert cli._gcp_service_name_from_hostname("sales-dashboard") == "sales-dashboard"
    assert cli._gcp_service_name_from_hostname("MyApp") == "myapp"
    assert cli._gcp_service_name_from_hostname(None) is None
    assert cli._gcp_service_name_from_hostname("") is None
    assert cli._gcp_service_name_from_hostname("2048game") is None
    assert cli._gcp_service_name_from_hostname("-dash") is None
    assert cli._gcp_service_name_from_hostname("dash-") is None
    assert cli._gcp_service_name_from_hostname("a" * 50) is None
    # The derived-name namespace of apps that store no name is reserved.
    assert (
        cli._gcp_service_name_from_hostname("app-8b2f4a1c-1234-5678-9abc-def012345678")
        is None
    )
    assert cli._gcp_service_name_from_hostname("app-metrics") == "app-metrics"


def test_resolve_deploy_provider_reflex_cloud_no_switch(mocker: MockFixture):
    """--provider reflex-cloud on a fly app is a no-op (already Reflex Cloud)."""
    client = fake_client()
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app, "reflex-cloud", interactive=False, app_was_created=False, client=client
    )
    assert result == "fly"
    client.api.apps.set_provider.assert_not_called()


def test_resolve_deploy_provider_non_interactive_keeps_current(mocker: MockFixture):
    """Non-interactive with no --provider keeps the app's provider, no prompt."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.gcp_deploy_available",
        return_value=GcpStatus(
            configured=True, allowed=True, project_id=None, region=None, connections=[]
        ),
    )
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app, None, interactive=False, app_was_created=False, client=client
    )
    assert result == "fly"
    client.api.apps.set_provider.assert_not_called()


def test_resolve_deploy_provider_switch_failure_exits(mocker: MockFixture):
    """A rejected provider switch aborts the deploy."""
    client = fake_client()
    client.api.apps.set_provider.side_effect = api_error(403, "Enterprise required")
    the_app = app("myapp", provider="fly")
    with pytest.raises(click.exceptions.Exit):
        cli._resolve_deploy_provider(
            the_app, "gcp", interactive=False, app_was_created=True, client=client
        )


def test_resolve_deploy_provider_switch_confirm_defaults_to_cancel(
    mocker: MockFixture,
):
    """Switching a deployed app's provider requires an explicit yes (default n)."""
    client = fake_client()
    ask = mocker.patch("reflex_cli.utils.console.ask", return_value="n")
    the_app = app("myapp", provider="fly")

    with pytest.raises(click.exceptions.Exit):
        cli._resolve_deploy_provider(
            the_app, "gcp", interactive=True, app_was_created=False, client=client
        )

    client.api.apps.set_provider.assert_not_called()
    # The teardown confirmation must default to "n" so Enter alone cancels.
    assert ask.call_args.kwargs.get("default") == "n"


def test_resolve_deploy_provider_interactive_prompt_selects_gcp(mocker: MockFixture):
    """When GCP is available and the user picks it, the app switches to GCP."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.gcp_deploy_available",
        return_value=GcpStatus(
            configured=True,
            allowed=True,
            project_id=None,
            region="us-central1",
            connections=[],
        ),
    )
    mocker.patch("reflex_cli.utils.console.ask", return_value="gcp")
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="fly")
    result = cli._resolve_deploy_provider(
        the_app, None, interactive=True, app_was_created=True, client=client
    )
    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once()


def test_restore_provider_on_failure_restores_on_error(mocker: MockFixture):
    """A failure after a switch re-pins the previous provider, then re-raises."""
    client = fake_client()
    client.api.apps.set_provider.return_value = ProviderChange(provider="fly")
    the_app = app("myapp")
    error = ValueError("boom")

    with (
        pytest.raises(ValueError),
        cli._restore_provider_on_failure(the_app, "fly", client),
    ):
        raise error

    client.api.apps.set_provider.assert_called_once_with(_APP_ID, "fly")


def test_restore_provider_on_failure_noop_without_switch(mocker: MockFixture):
    """With no prior switch, a failure leaves the provider untouched."""
    client = fake_client()
    the_app = app("myapp")
    error = ValueError("boom")

    with (
        pytest.raises(ValueError),
        cli._restore_provider_on_failure(the_app, None, client),
    ):
        raise error

    client.api.apps.set_provider.assert_not_called()


def test_restore_provider_on_failure_noop_on_success(mocker: MockFixture):
    """On success the provider is left as the newly-switched one."""
    client = fake_client()
    the_app = app("myapp")

    with cli._restore_provider_on_failure(the_app, "fly", client):
        pass

    client.api.apps.set_provider.assert_not_called()


def test_resolve_deploy_provider_named_connection_is_pinned(mocker: MockFixture):
    """--gcp-connection resolves to a connection id and rides the switch."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        return_value=[
            GcpConnection(
                id=uuid.UUID(int=61),
                name="eu-prod",
                is_default=False,
                project_id="p2",
                region="europe-west1",
            )
        ],
    )
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="fly")

    result = cli._resolve_deploy_provider(
        the_app,
        "gcp",
        interactive=False,
        app_was_created=True,
        client=client,
        gcp_connection="eu-prod",
    )

    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=uuid.UUID(int=61), service_name=None
    )


def test_resolve_deploy_provider_repoints_without_a_provider_switch(
    mocker: MockFixture,
):
    """An app already on GCP is still repointed when a connection is named."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        return_value=[
            GcpConnection(
                id=uuid.UUID(int=62),
                name="eu-prod",
                is_default=False,
                project_id="p",
                region="europe-west1",
            )
        ],
    )
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="gcp")

    result = cli._resolve_deploy_provider(
        the_app,
        "gcp",
        interactive=False,
        app_was_created=False,
        client=client,
        gcp_connection="eu-prod",
    )

    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=uuid.UUID(int=62), service_name=None
    )


def test_resolve_deploy_provider_gcp_redeploy_keeps_the_pinned_name(
    mocker: MockFixture,
):
    """An app already on GCP never re-sends a service name.

    The name is pinned to a live service by then, so a --hostname on a later
    deploy must not reach the server as a rename request.
    """
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        return_value=[
            GcpConnection(
                id=uuid.UUID(int=62),
                name="eu-prod",
                is_default=False,
                project_id="p",
                region="europe-west1",
            )
        ],
    )
    client.api.apps.set_provider.return_value = ProviderChange(provider="gcp")
    the_app = app("myapp", provider="gcp")

    result = cli._resolve_deploy_provider(
        the_app,
        "gcp",
        interactive=False,
        app_was_created=False,
        client=client,
        gcp_connection="eu-prod",
        hostname="sales-dashboard",
    )

    assert result == "gcp"
    client.api.apps.set_provider.assert_called_once_with(
        _APP_ID, "gcp", provider_account_id=uuid.UUID(int=62), service_name=None
    )


def test_resolve_deploy_provider_unknown_connection_aborts(mocker: MockFixture):
    """A connection name nothing matches stops the deploy before it starts."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        return_value=[
            GcpConnection(
                id=uuid.UUID(int=61),
                name="us-prod",
                is_default=False,
                project_id="p",
                region="europe-west1",
            )
        ],
    )
    the_app = app("myapp", provider="fly")

    with pytest.raises(click.exceptions.Exit):
        cli._resolve_deploy_provider(
            the_app,
            "gcp",
            interactive=False,
            app_was_created=True,
            client=client,
            gcp_connection="eu-prod",
        )

    client.api.apps.set_provider.assert_not_called()


def test_resolve_deploy_provider_connection_requires_gcp(mocker: MockFixture):
    """--gcp-connection on a Reflex Cloud deploy is refused, not ignored."""
    client = fake_client()
    mock_list = mocker.patch("reflex_cli.utils.hosting.list_gcp_connections")
    the_app = app("myapp", provider="fly")

    with pytest.raises(click.exceptions.Exit):
        cli._resolve_deploy_provider(
            the_app,
            "reflex-cloud",
            interactive=False,
            app_was_created=False,
            client=client,
            gcp_connection="eu-prod",
        )

    mock_list.assert_not_called()
    client.api.apps.set_provider.assert_not_called()


def test_resolve_deploy_provider_unreadable_connections_abort(mocker: MockFixture):
    """A failed connection lookup aborts rather than silently using the default."""
    client = fake_client()
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections", side_effect=Exception("boom")
    )
    the_app = app("myapp", provider="gcp")

    with pytest.raises(click.exceptions.Exit):
        cli._resolve_deploy_provider(
            the_app,
            "gcp",
            interactive=False,
            app_was_created=False,
            client=client,
            gcp_connection="eu-prod",
        )

    client.api.apps.set_provider.assert_not_called()


def test_apply_full_deploy_noop_when_unset(mocker: MockFixture):
    """No --full-deploy flag leaves the app's hosting mode alone."""
    client = fake_client()
    the_app = app("myapp")

    assert cli._apply_full_deploy(the_app, None, "gcp", client) is False
    client.api.apps.set_full_deploy.assert_not_called()


def test_apply_full_deploy_requires_gcp(mocker: MockFixture):
    """--full-deploy on a Reflex Cloud deploy is refused before any call."""
    client = fake_client()
    the_app = app("myapp")

    with pytest.raises(click.exceptions.Exit):
        cli._apply_full_deploy(the_app, True, "fly", client)

    client.api.apps.set_full_deploy.assert_not_called()


def test_apply_full_deploy_reports_a_stopped_app(mocker: MockFixture):
    """A flip that stopped the app says so, for the failure warning to use."""
    client = fake_client()
    client.api.apps.set_full_deploy.return_value = FullDeployChange(
        full_deploy=True, stopped=True, stop_confirmed=True
    )
    the_app = app("myapp")

    assert cli._apply_full_deploy(the_app, True, "gcp", client) is True
    client.api.apps.set_full_deploy.assert_called_once_with(_APP_ID, True)


def test_apply_full_deploy_warns_on_an_unconfirmed_stop(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An unconfirmed teardown is surfaced: the deploy may be refused."""
    client = fake_client()
    client.api.apps.set_full_deploy.return_value = FullDeployChange(
        full_deploy=True, stopped=True, stop_confirmed=False
    )

    assert cli._apply_full_deploy(app("myapp"), True, "gcp", client)
    assert "did not confirm" in _log_messages(caplog, logging.WARNING)[-1]


def test_apply_full_deploy_refusal_aborts(mocker: MockFixture):
    """A server refusal stops the deploy instead of exporting for the old mode."""
    client = fake_client()
    client.api.apps.set_full_deploy.side_effect = api_error(403, "Enterprise required")

    with pytest.raises(click.exceptions.Exit):
        cli._apply_full_deploy(app("myapp"), True, "gcp", client)


def test_warn_if_full_deploy_outlives_deploy(caplog: pytest.LogCaptureFixture):
    """A stopped app whose deploy then failed is reported as still down."""
    error = RuntimeError("export failed")

    with (
        pytest.raises(RuntimeError),
        cli._warn_if_full_deploy_outlives_deploy("myapp", True),
    ):
        raise error

    assert "stays down" in _log_messages(caplog, logging.WARNING)[-1]


def test_warn_if_full_deploy_outlives_deploy_stays_quiet_when_nothing_stopped(
    caplog: pytest.LogCaptureFixture,
):
    """Nothing was stopped, so a failed deploy left nothing behind to report."""
    error = RuntimeError("export failed")

    with (
        pytest.raises(RuntimeError),
        cli._warn_if_full_deploy_outlives_deploy("myapp", False),
    ):
        raise error

    assert _log_messages(caplog, logging.WARNING) == []


def test_deploy_expired_token_says_to_log_in(
    mocker: MockerFixture,
    mock_export_fn: Callable[[str, str, str, bool, bool, bool, bool], None],
    caplog: pytest.LogCaptureFixture,
):
    """A token that expires mid-deploy is named as one, not as a deploy failure.

    Args:
        mocker: The pytest-mock fixture.
        mock_export_fn: The export the deploy drives.
        caplog: The pytest log capture fixture.
    """
    client = _common_deploy_mocks(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_app", return_value=None)
    client.api.apps.create.side_effect = api_error(401, "expired")

    with pytest.raises(click.exceptions.Exit):
        cli.deploy(app_name="fake-app", export_fn=mock_export_fn, interactive=False)

    assert _log_messages(caplog, logging.ERROR) == [
        "You are not authenticated. Run `reflex login` to authenticate."
    ]
