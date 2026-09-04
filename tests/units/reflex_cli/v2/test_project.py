import json
import logging

import httpx
import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_cli.utils import hosting
from reflex_cli.utils.exceptions import NotAuthenticatedError
from reflex_cli.v2.deployments import hosting_cli

from .utils import as_click_command

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()


def _log_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def test_create_project_with_valid_token(mocker: MockFixture):
    mock_create_project = mocker.patch(
        "reflex_cli.utils.hosting.create_project",
        return_value={"name": "test_project", "id": 1},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    project_name = "test_project"
    token = "valid_token"

    args = ["project", "create", project_name, "--token", token]

    result = runner.invoke(hosting_cli, args)

    mock_create_project.assert_called_once_with(
        name=project_name,
        client=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )

    headers = list({"name": "test_project", "id": 1}.keys())
    table = [
        [
            str(value) if value is not None else ""
            for value in {"name": "test_project", "id": 1}.values()
        ]
    ]
    mock_print_table.assert_called_once_with(table, headers=headers)

    # Asserting the result's exit code is 0 (indicating success)
    assert result.exit_code == 0, result.output


def test_create_project_with_json_output(mocker: MockFixture):
    mock_create_project = mocker.patch(
        "reflex_cli.utils.hosting.create_project",
        return_value={"name": "test_project", "id": 1},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )
    project_name = "test_project"
    token = "valid_token"

    args = ["project", "create", project_name, "--token", token, "--json"]

    result = runner.invoke(hosting_cli, args)

    mock_create_project.assert_called_once_with(
        name=project_name,
        client=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )

    assert json.loads(result.stdout) == {"name": "test_project", "id": 1}

    assert result.exit_code == 0, result.output


def test_create_project_without_token(mocker: MockFixture):
    mock_create_project = mocker.patch(
        "reflex_cli.utils.hosting.create_project", return_value=None
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    project_name = "test_project"

    args = ["project", "create", project_name]

    result = runner.invoke(hosting_cli, args)

    mock_create_project.assert_called_once_with(
        name=project_name,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_print.assert_called_once_with(str(None))
    assert result.exit_code == 0, result.output


def test_invite_user_to_project_success(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mock_invite = mocker.patch(
        "reflex_cli.utils.hosting.invite_user_to_project", return_value="success"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )

    role = "admin"
    user = "user123"
    token = "valid_token"

    args = ["project", "invite", role, user, "--token", token]

    result = runner.invoke(hosting_cli, args)

    mock_invite.assert_called_once_with(
        role_id=role,
        user_id=user,
        client=hosting.AuthenticatedClient(
            token="valid_token", validated_data={"foo": "bar"}
        ),
    )

    assert _log_messages(caplog, SUCCESS) == ["Successfully invited user to project."]
    assert _log_messages(caplog, logging.ERROR) == []

    assert result.exit_code == 0, result.output


def test_invite_user_to_project_failure(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mock_invite = mocker.patch(
        "reflex_cli.utils.hosting.invite_user_to_project",
        return_value="user invite failed: Unauthorized",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    role = "admin"
    user = "user123"

    args = ["project", "invite", role, user]

    result = runner.invoke(hosting_cli, args)

    mock_invite.assert_called_once_with(
        role_id=role,
        user_id=user,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    assert _log_messages(caplog, logging.ERROR) == [
        "Unable to invite user to project: user invite failed: Unauthorized"
    ]
    assert _log_messages(caplog, SUCCESS) == []

    assert result.exit_code == 1


def test_invite_user_to_project_missing_token(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mock_invite = mocker.patch(
        "reflex_cli.utils.hosting.invite_user_to_project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )

    role = "admin"
    user = "user123"

    args = ["project", "invite", role, user]

    result = runner.invoke(hosting_cli, args)

    mock_invite.assert_called_once_with(
        role_id=role,
        user_id=user,
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert _log_messages(caplog, SUCCESS) == ["Successfully invited user to project."]
    assert _log_messages(caplog, logging.ERROR) == []
    assert result.exit_code == 0, result.output


def test_select_project_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful project selection.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mock_select_project = mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value="TestProject is now selected.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch("reflex_cli.utils.hosting.get_project")

    project = "TestProject"

    args = ["project", "select", project]

    result = runner.invoke(hosting_cli, args)

    mock_select_project.assert_called_once_with(project=project, token=None)

    assert _log_messages(caplog, SUCCESS) == ["TestProject is now selected."]
    assert _log_messages(caplog, logging.ERROR) == []

    assert result.exit_code == 0, result.output


def test_select_project_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test failure during project selection.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mock_select_project = mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value="failed to select project.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    get_project = mocker.patch("reflex_cli.utils.hosting.get_project")
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=mocker.Mock(),
        response=mocker.Mock(
            json=lambda: {
                "detail": "no project with given id found that user has access to."
            }
        ),
    )
    get_project.return_value = mock_response

    project = "InvalidProject"

    args = ["project", "select", project]

    result = runner.invoke(hosting_cli, args)

    mock_select_project.assert_called_once_with(project=project, token=None)

    assert _log_messages(caplog, logging.ERROR) == ["failed to select project."]
    assert _log_messages(caplog, SUCCESS) == []

    assert result.exit_code == 1


def test_select_project_valid_project_name(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test successful project selection using project name.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    mock_select_project = mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value="test_project_id is now selected.",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value={"id": "test_project_id"},
    )
    get_project = mocker.patch(
        "reflex_cli.utils.hosting.get_project",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    token = "test_token"

    args = ["project", "select", "--project-name", "TestProject", "--token", token]

    result = runner.invoke(hosting_cli, args)

    mock_select_project.assert_called_once_with(project="test_project_id", token=token)

    assert _log_messages(caplog, SUCCESS) == ["test_project_id is now selected."]
    assert _log_messages(caplog, logging.ERROR) == []
    get_project.assert_not_called()

    assert result.exit_code == 0, result.output


def test_select_project_invalid_id(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
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
        response=mocker.Mock(
            json=lambda: {
                "detail": "no project with given id found that user has access to."
            }
        ),
    )
    mock_get.return_value = mock_response
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )

    project = "InvalidProject"

    args = ["project", "select", project]

    result = runner.invoke(hosting_cli, args)

    assert _log_messages(caplog, logging.ERROR) == [
        "no project with given id found that user has access to."
    ]
    assert result.exit_code == 1


def test_select_project_invalid_project_name(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    mocker.patch(
        "reflex_cli.utils.hosting.requires_authenticated", return_value="fake_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authorization_header",
        return_value={"X-API-TOKEN": "fake_token"},
    )
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=None,
    )

    args = [
        "project",
        "select",
        "--project-name",
        "invalid_project",
        "--token",
        "test_token",
    ]

    result = runner.invoke(hosting_cli, args)

    assert _log_messages(caplog, logging.ERROR) == [
        "No project selected. Please provide a valid project ID or name."
    ]
    assert result.exit_code == 1


def test_get_project_roles_with_project_id(mocker: MockFixture):
    """Test retrieving project roles with a provided project ID."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_roles = mocker.patch(
        "reflex_cli.utils.hosting.get_project_roles",
        return_value=[
            {"role": "admin", "user": "user1@example.com"},
            {"role": "viewer", "user": "user2@example.com"},
        ],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli,
        ["project", "roles", "--project-id", "test_project_id"],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_roles.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print_table.assert_called_once()


def test_get_project_roles_no_project_selected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test retrieving project roles when no project ID is provided or selected.

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
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project", return_value=None
    )

    result = runner.invoke(hosting_cli, ["project", "roles"])

    assert result.exit_code == 1
    mock_get_selected_project.assert_called_once()
    assert _log_messages(caplog, logging.ERROR) == [
        "no project_id provided or selected. Set it with `reflex cloud project roles --project-id \\[project_id]`"
    ]


def test_get_project_roles_as_json(mocker: MockFixture):
    """Test retrieving project roles with JSON output."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_roles = mocker.patch(
        "reflex_cli.utils.hosting.get_project_roles",
        return_value=[
            {"role": "admin", "user": "user1@example.com"},
            {"role": "viewer", "user": "user2@example.com"},
        ],
    )
    result = runner.invoke(
        hosting_cli,
        ["project", "roles", "--project-id", "test_project_id", "--json"],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_roles.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert json.loads(result.stdout) == [
        {"role": "admin", "user": "user1@example.com"},
        {"role": "viewer", "user": "user2@example.com"},
    ]


def test_get_project_roles_empty_roles(mocker: MockFixture):
    """Test retrieving project roles when the result is an empty list."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_roles = mocker.patch(
        "reflex_cli.utils.hosting.get_project_roles",
        return_value=[],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["project", "roles", "--project-id", "test_project_id"],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_roles.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with("[]")


def test_get_project_role_permissions_with_role_and_project_id(mocker: MockFixture):
    """Test retrieving role permissions with provided role_id and project_id."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_permissions = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_permissions",
        return_value=[
            {"permission": "read", "resource": "resource1"},
            {"permission": "write", "resource": "resource2"},
        ],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli,
        [
            "project",
            "role-permissions",
            "test_role_id",
            "--project-id",
            "test_project_id",
        ],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_permissions.assert_called_once_with(
        project_id="test_project_id",
        role_id="test_role_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print_table.assert_called_once()


def test_get_project_role_permissions_no_project_selected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test retrieving role permissions when no project_id is provided or selected.

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
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project", return_value=None
    )

    result = runner.invoke(hosting_cli, ["project", "role-permissions", "test_role_id"])

    assert result.exit_code == 1
    mock_get_selected_project.assert_called_once()
    assert _log_messages(caplog, logging.ERROR) == [
        "no project_id provided or selected. Set it with `reflex cloud project role-permissions --project-id \\[project_id]`."
    ]


def test_get_project_role_permissions_not_authenticated(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test retrieving role permissions when the user is not authenticated.

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
    mock_get_project_role_permissions = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_permissions",
        side_effect=NotAuthenticatedError("not authenticated"),
    )
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project",
        return_value="test_project_id",
    )

    result = runner.invoke(hosting_cli, ["project", "role-permissions", "test_role_id"])

    assert result.exit_code == 1
    mock_get_selected_project.assert_called_once()
    mock_get_project_role_permissions.assert_called_once_with(
        project_id="test_project_id",
        role_id="test_role_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert _log_messages(caplog, logging.ERROR) == [
        "You are not authenticated. Run `reflex login` to authenticate."
    ]


def test_get_project_role_permissions_as_json(mocker: MockFixture):
    """Test retrieving role permissions with JSON output."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_permissions = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_permissions",
        return_value=[
            {"permission": "read", "resource": "resource1"},
            {"permission": "write", "resource": "resource2"},
        ],
    )
    result = runner.invoke(
        hosting_cli,
        [
            "project",
            "role-permissions",
            "test_role_id",
            "--project-id",
            "test_project_id",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_permissions.assert_called_once_with(
        project_id="test_project_id",
        role_id="test_role_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert json.loads(result.stdout) == [
        {"permission": "read", "resource": "resource1"},
        {"permission": "write", "resource": "resource2"},
    ]


def test_get_project_role_permissions_empty_permissions(mocker: MockFixture):
    """Test retrieving role permissions when the result is an empty list."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_permissions = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_permissions",
        return_value=[],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        [
            "project",
            "role-permissions",
            "test_role_id",
            "--project-id",
            "test_project_id",
        ],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_permissions.assert_called_once_with(
        project_id="test_project_id",
        role_id="test_role_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with("[]")


def test_get_project_role_users_with_project_id(mocker: MockFixture):
    """Test retrieving users with a provided project_id."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_users = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_users",
        return_value=[
            {"user_id": "user1", "role": "admin"},
            {"user_id": "user2", "role": "developer"},
        ],
    )
    mock_console_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli,
        ["project", "users", "--project-id", "test_project_id"],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_users.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print_table.assert_called_once()


def test_get_project_role_users_no_project_selected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """Test retrieving users when no project_id is provided or selected.

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
    mock_get_selected_project = mocker.patch(
        "reflex_cli.utils.hosting.get_selected_project", return_value=None
    )

    result = runner.invoke(hosting_cli, ["project", "users"])

    assert result.exit_code == 1
    mock_get_selected_project.assert_called_once()
    assert _log_messages(caplog, logging.ERROR) == [
        "no project_id provided or selected. Set it with `reflex cloud project users --project-id \\[project_id]`"
    ]


def test_get_project_role_users_as_json(mocker: MockFixture):
    """Test retrieving users with JSON output."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_users = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_users",
        return_value=[
            {"user_id": "user1", "role": "admin"},
            {"user_id": "user2", "role": "developer"},
        ],
    )
    result = runner.invoke(
        hosting_cli,
        [
            "project",
            "users",
            "--project-id",
            "test_project_id",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_users.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    assert json.loads(result.stdout) == [
        {"user_id": "user1", "role": "admin"},
        {"user_id": "user2", "role": "developer"},
    ]


def test_get_project_role_users_empty_users(mocker: MockFixture):
    """Test retrieving users when the result is an empty list."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_get_project_role_users = mocker.patch(
        "reflex_cli.utils.hosting.get_project_role_users",
        return_value=[],
    )
    mock_console_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["project", "users", "--project-id", "test_project_id"],
    )

    assert result.exit_code == 0, result.output
    mock_get_project_role_users.assert_called_once_with(
        project_id="test_project_id",
        client=hosting.AuthenticatedClient(
            token="fake-token", validated_data={"foo": "bar"}
        ),
    )
    mock_console_print.assert_called_once_with("[]")


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


def test_invite_user_to_project_json_output(mocker: MockFixture):
    """An invite reports who was invited to what role."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.invite_user_to_project", return_value="ok")

    result = runner.invoke(
        hosting_cli, ["project", "invite", "role-1", "user-1", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "role_id": "role-1",
        "user_id": "user-1",
        "invited": True,
    }


def test_select_project_json_output(mocker: MockFixture):
    """Selecting a project reports the project it selected."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_project", return_value={"id": "p1"})
    mocker.patch("reflex_cli.utils.hosting.select_project", return_value="selected p1")

    result = runner.invoke(hosting_cli, ["project", "select", "p1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": "p1",
        "selected": True,
        "message": "selected p1",
    }


def test_get_selected_project_json_output(mocker: MockFixture):
    """The selected project comes back as a document rather than a table."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value="p1")
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        return_value={"id": "p1", "name": "My Project"},
    )

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": "p1",
        "name": "My Project",
        "error": None,
    }


def test_get_selected_project_json_output_when_none(mocker: MockFixture):
    """No selection is a document saying so, not a warning to parse."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value=None)

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": None,
        "name": None,
        "error": None,
    }


def test_get_selected_project_json_output_when_the_lookup_fails(mocker: MockFixture):
    """A failed lookup is not the same document as nothing being selected."""
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value="p1")
    mocker.patch(
        "reflex_cli.utils.hosting.get_project",
        side_effect=RuntimeError("project service unavailable"),
    )

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "project_id": "p1",
        "name": None,
        "error": "project service unavailable",
    }
