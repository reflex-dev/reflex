from __future__ import annotations

import json
import logging
import uuid

import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_base.utils.log import SUCCESS
from reflex_build_sdk.types import (
    Project,
    ProjectMember,
    ProjectRef,
    ProjectSummary,
    ProjectTier,
    Role,
)
from reflex_cli.v2.deployments import hosting_cli

from .utils import api_error, as_click_command, fake_client

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()

_PROJECT_ID = uuid.UUID(int=7)


def _log_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


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


def _project(name: str = "test_project") -> Project:
    """Build a project as the API reports one.

    Args:
        name: The project's name.

    Returns:
        The project.
    """
    return Project(
        id=_PROJECT_ID,
        name=name,
        tier=ProjectTier(name="Pro", cpu_quota=4, ram_quota=8, deployment_quota=10),
        owner_id=uuid.UUID(int=13),
        owner_email="owner@example.com",
        seats=1,
        apps=[],
    )


def _role(name: str = "admin") -> Role:
    """Build a project role.

    Args:
        name: The role's name.

    Returns:
        The role.
    """
    return Role(
        id=uuid.UUID(int=11),
        name=name,
        base_tier="admin",
        permissions=["deploy"],
        is_builtin=True,
        member_count=1,
    )


def _member(email: str = "someone@example.com") -> ProjectMember:
    """Build a project member.

    Args:
        email: The member's email address.

    Returns:
        The member.
    """
    return ProjectMember(
        user_id=uuid.UUID(int=12),
        email=email,
        role="admin",
        base_tier="admin",
        permissions=["deploy"],
        is_service_account=False,
    )


def test_create_project_with_valid_token(mocker: MockFixture):
    """Creating a project renders the new project as a one-row table."""
    client = _authed(mocker)
    client.api.projects.create.return_value = ProjectRef(
        id=_PROJECT_ID, name="test_project"
    )
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli, ["project", "create", "test_project", "--token", "valid_token"]
    )

    client.api.projects.create.assert_called_once_with("test_project")
    mock_print_table.assert_called_once_with(
        [[str(_PROJECT_ID), "test_project"]], headers=["id", "name"]
    )
    assert result.exit_code == 0, result.output


def test_create_project_with_json_output(mocker: MockFixture):
    """--json emits the new project as the API reports it."""
    client = _authed(mocker)
    client.api.projects.create.return_value = ProjectRef(
        id=_PROJECT_ID, name="test_project"
    )

    result = runner.invoke(hosting_cli, ["project", "create", "test_project", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {"id": str(_PROJECT_ID), "name": "test_project"}
    ]


def test_create_project_duplicate_name(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A name already in use is reported as such rather than as a raw conflict.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.create.side_effect = api_error(409, "duplicate")

    result = runner.invoke(hosting_cli, ["project", "create", "test_project"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "A project named 'test_project' already exists. Please use a different name."
    ]


def test_invite_user_to_project_success(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An applied invite reports success.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.members.set_role.return_value = "applied"

    result = runner.invoke(
        hosting_cli, ["project", "invite", "admin", "user123", "--token", "t"]
    )

    client.api.projects.members.set_role.assert_called_once_with(
        user_id="user123", role_id="admin"
    )
    assert _log_messages(caplog, SUCCESS) == ["Successfully invited user to project."]
    assert result.exit_code == 0, result.output


def test_invite_user_to_project_pending_approval(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An invite waiting on an admin says so rather than claiming it took effect.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.members.set_role.return_value = "pending_approval"

    result = runner.invoke(hosting_cli, ["project", "invite", "admin", "user123"])

    assert result.exit_code == 0, result.output
    assert _log_messages(caplog, SUCCESS) == [
        "Invite submitted; a project admin has to approve it before it takes effect."
    ]


def test_invite_user_to_project_failure(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A refused invite surfaces the API's explanation and exits non-zero.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.members.set_role.side_effect = api_error(
        403, "failed to invite user."
    )

    result = runner.invoke(hosting_cli, ["project", "invite", "admin", "user123"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == ["failed to invite user."]


def test_invite_user_to_project_json_output(mocker: MockFixture):
    """--json reports who was invited to what, and whether it is pending."""
    client = _authed(mocker)
    client.api.projects.members.set_role.return_value = "applied"

    result = runner.invoke(
        hosting_cli, ["project", "invite", "role-1", "user-1", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "role_id": "role-1",
        "user_id": "user-1",
        "invited": True,
        "status": "applied",
    }


def test_select_project_success(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """Test successful project selection.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    mock_select_project = mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value="TestProject is now selected.",
    )

    result = runner.invoke(hosting_cli, ["project", "select", "TestProject"])

    client.api.projects.get.assert_called_once_with("TestProject")
    mock_select_project.assert_called_once_with(project="TestProject", token=None)
    assert _log_messages(caplog, SUCCESS) == ["TestProject is now selected."]
    assert _log_messages(caplog, logging.ERROR) == []
    assert result.exit_code == 0, result.output


def test_select_project_failure(mocker: MockFixture, caplog: pytest.LogCaptureFixture):
    """A store that could not be written is reported and exits non-zero.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value="failed to select project.",
    )

    result = runner.invoke(hosting_cli, ["project", "select", "InvalidProject"])

    assert _log_messages(caplog, logging.ERROR) == ["failed to select project."]
    assert _log_messages(caplog, SUCCESS) == []
    assert result.exit_code == 1


def test_select_project_valid_project_name(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A project named rather than identified is looked up first.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.search_project",
        return_value=ProjectRef(id=_PROJECT_ID, name="test_project"),
    )
    mock_select_project = mocker.patch(
        "reflex_cli.utils.hosting.select_project",
        return_value=f"{_PROJECT_ID} is now selected.",
    )

    result = runner.invoke(
        hosting_cli, ["project", "select", "--project-name", "test_project"]
    )

    mock_select_project.assert_called_once_with(project=str(_PROJECT_ID), token=None)
    assert _log_messages(caplog, SUCCESS) == [f"{_PROJECT_ID} is now selected."]
    assert result.exit_code == 0, result.output


def test_select_project_invalid_id(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An id the caller cannot read is reported before anything is stored.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.get.side_effect = api_error(
        404, "no project with given id found that user has access to."
    )
    mock_select_project = mocker.patch("reflex_cli.utils.hosting.select_project")

    result = runner.invoke(hosting_cli, ["project", "select", "bad-id"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "no project with given id found that user has access to."
    ]
    mock_select_project.assert_not_called()


def test_select_project_invalid_project_name(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """A name that matches nothing leaves the selection alone.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.search_project", return_value=None)
    mock_select_project = mocker.patch("reflex_cli.utils.hosting.select_project")

    result = runner.invoke(hosting_cli, ["project", "select", "--project-name", "nope"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "No project selected. Please provide a valid project ID or name."
    ]
    mock_select_project.assert_not_called()


def test_select_project_json_output(mocker: MockFixture):
    """--json reports what was selected and the message that was logged."""
    _authed(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.select_project", return_value="proj1 is now selected."
    )

    result = runner.invoke(hosting_cli, ["project", "select", "proj1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": "proj1",
        "selected": True,
        "message": "proj1 is now selected.",
    }


def test_get_projects(mocker: MockFixture):
    """Listing renders a row per project."""
    client = _authed(mocker)
    client.api.projects.list.return_value = [
        ProjectSummary(
            id=_PROJECT_ID,
            name="test_project",
            tier=ProjectTier(name="Pro", cpu_quota=4, ram_quota=8, deployment_quota=10),
            app_count=2,
            deployment_count=3,
            cpu_usage=1.5,
            memory_usage=2.0,
        )
    ]

    result = runner.invoke(hosting_cli, ["project", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "id": str(_PROJECT_ID),
            "name": "test_project",
            "tier": {
                "name": "Pro",
                "cpu_quota": 4,
                "ram_quota": 8,
                "deployment_quota": 10,
            },
            "app_count": 2,
            "deployment_count": 3,
            "cpu_usage": 1.5,
            "memory_usage": 2.0,
        }
    ]


def test_get_project_roles_with_project_id(mocker: MockFixture):
    """Roles are listed for the project named on the command line."""
    client = _authed(mocker)
    client.api.projects.roles.list.return_value = [_role()]
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli, ["project", "roles", "--project-id", str(_PROJECT_ID)]
    )

    assert result.exit_code == 0, result.output
    client.api.projects.roles.list.assert_called_once_with(str(_PROJECT_ID))
    mock_print_table.assert_called_once()


def test_get_project_roles_no_project_selected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """With no project given or selected, the command says how to set one.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value=None)

    result = runner.invoke(hosting_cli, ["project", "roles"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "no project_id provided or selected. Set it with `reflex cloud project roles --project-id \\[project_id]`"
    ]


def test_get_project_roles_as_json(mocker: MockFixture):
    """--json emits the roles as the API reports them."""
    client = _authed(mocker)
    client.api.projects.roles.list.return_value = [_role()]

    result = runner.invoke(
        hosting_cli,
        ["project", "roles", "--project-id", str(_PROJECT_ID), "--json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "id": str(uuid.UUID(int=11)),
            "name": "admin",
            "base_tier": "admin",
            "permissions": ["deploy"],
            "is_builtin": True,
            "member_count": 1,
        }
    ]


def test_get_project_roles_empty_roles(mocker: MockFixture):
    """A project with no roles prints the empty listing rather than a table."""
    client = _authed(mocker)
    client.api.projects.roles.list.return_value = []
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli, ["project", "roles", "--project-id", str(_PROJECT_ID)]
    )

    assert result.exit_code == 0, result.output
    mock_print.assert_called_once_with("[]")


def test_get_project_role_permissions(mocker: MockFixture):
    """A role's permissions are listed one per row."""
    client = _authed(mocker)
    client.api.projects.roles.permissions.return_value = ["deploy", "read"]
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli,
        ["project", "role-permissions", "role-1", "--project-id", str(_PROJECT_ID)],
    )

    assert result.exit_code == 0, result.output
    client.api.projects.roles.permissions.assert_called_once_with(
        str(_PROJECT_ID), "role-1"
    )
    mock_print_table.assert_called_once_with(
        [["deploy"], ["read"]], headers=["Permission"]
    )


def test_get_project_role_permissions_as_json(mocker: MockFixture):
    """--json emits the permission names."""
    client = _authed(mocker)
    client.api.projects.roles.permissions.return_value = ["deploy", "read"]

    result = runner.invoke(
        hosting_cli,
        [
            "project",
            "role-permissions",
            "role-1",
            "--project-id",
            str(_PROJECT_ID),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ["deploy", "read"]


def test_get_project_role_permissions_empty(mocker: MockFixture):
    """A role that grants nothing prints the empty listing."""
    client = _authed(mocker)
    client.api.projects.roles.permissions.return_value = []
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli,
        ["project", "role-permissions", "role-1", "--project-id", str(_PROJECT_ID)],
    )

    assert result.exit_code == 0, result.output
    mock_print.assert_called_once_with("[]")


def test_get_project_role_permissions_not_authenticated(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """An expired token says what to do about it.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    client = _authed(mocker)
    client.api.projects.roles.permissions.side_effect = api_error(401, "expired")

    result = runner.invoke(
        hosting_cli,
        ["project", "role-permissions", "role-1", "--project-id", str(_PROJECT_ID)],
    )

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "You are not authenticated. Run `reflex login` to authenticate."
    ]


def test_get_project_role_users_with_project_id(mocker: MockFixture):
    """Members are listed for the project named on the command line."""
    client = _authed(mocker)
    client.api.projects.members.list.return_value = [_member()]
    mock_print_table = mocker.patch("reflex_cli.utils.console.print_table")

    result = runner.invoke(
        hosting_cli, ["project", "users", "--project-id", str(_PROJECT_ID)]
    )

    assert result.exit_code == 0, result.output
    client.api.projects.members.list.assert_called_once_with(str(_PROJECT_ID))
    mock_print_table.assert_called_once()


def test_get_project_role_users_as_json(mocker: MockFixture):
    """--json emits the members as the API reports them."""
    client = _authed(mocker)
    client.api.projects.members.list.return_value = [_member()]

    result = runner.invoke(
        hosting_cli,
        ["project", "users", "--project-id", str(_PROJECT_ID), "--json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {
            "user_id": str(uuid.UUID(int=12)),
            "email": "someone@example.com",
            "role": "admin",
            "base_tier": "admin",
            "permissions": ["deploy"],
            "is_service_account": False,
        }
    ]


def test_get_project_role_users_empty_users(mocker: MockFixture):
    """A project with no members prints the empty listing."""
    client = _authed(mocker)
    client.api.projects.members.list.return_value = []
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli, ["project", "users", "--project-id", str(_PROJECT_ID)]
    )

    assert result.exit_code == 0, result.output
    mock_print.assert_called_once_with("[]")


def test_get_project_role_users_no_project_selected(
    mocker: MockFixture, caplog: pytest.LogCaptureFixture
):
    """With no project given or selected, the command says how to set one.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
    """
    _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value=None)

    result = runner.invoke(hosting_cli, ["project", "users"])

    assert result.exit_code == 1
    assert _log_messages(caplog, logging.ERROR) == [
        "no project_id provided or selected. Set it with `reflex cloud project users --project-id \\[project_id]`"
    ]


def test_get_selected_project_json_output(mocker: MockFixture):
    """--json names the selected project."""
    client = _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value="proj1")
    client.api.projects.get.return_value = _project("My Project")

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": "proj1",
        "name": "My Project",
        "error": None,
    }


def test_get_selected_project_json_output_when_none(mocker: MockFixture):
    """An empty selection is a document, not silence."""
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value=None)

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "project_id": None,
        "name": None,
        "error": None,
    }


def test_get_selected_project_json_output_when_the_lookup_fails(mocker: MockFixture):
    """A failed lookup is a different answer from nothing being selected."""
    client = _authed(mocker)
    mocker.patch("reflex_cli.utils.hosting.get_selected_project", return_value="proj1")
    client.api.projects.get.side_effect = api_error(500, "boom")

    result = runner.invoke(hosting_cli, ["project", "selected", "--json"])

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["project_id"] == "proj1"
    assert document["name"] is None
    assert document["error"]
