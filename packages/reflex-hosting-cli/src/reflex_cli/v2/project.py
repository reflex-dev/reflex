"""Project commands for the Reflex Cloud CLI."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import click

from reflex_cli import constants
from reflex_cli.utils import console, log
from reflex_cli.utils.output import interactive_option, json_option, print_json

if TYPE_CHECKING:
    from reflex_cli.utils.hosting import AuthenticatedClient

logger = logging.getLogger(__name__)

_Command = TypeVar("_Command", bound=Callable[..., Any])

_loglevel_option = click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
# What every command that reads one project's settings takes.
_PROJECT_OPTIONS = (
    click.option(
        "--project-id",
        help="The ID of the project. If not provided, the selected project will be used. If no project is selected, it throws an error.",
    ),
    click.option("--project-name", help="The name of the project. "),
    click.option("--token", help="The authentication token."),
    _loglevel_option,
    json_option,
    interactive_option,
)


def project_options(command: _Command) -> _Command:
    """Apply the options every command that reads one project takes.

    Args:
        command: The command to decorate.

    Returns:
        The decorated command.

    """
    for option in reversed(_PROJECT_OPTIONS):
        command = option(command)
    return command


@click.group()
def project_cli():
    """Commands for managing projects."""


def _resolve_project_id(
    project_id: str | None,
    project_name: str | None,
    client: AuthenticatedClient,
    interactive: bool,
    command: str,
) -> str:
    """Resolve a project id from --project-id, --project-name, or the selection.

    Args:
        project_id: The explicit project id, if given.
        project_name: The project name to look up, if given.
        client: The authenticated client.
        interactive: Whether to interactively resolve name conflicts.
        command: The command asking, named in the error when nothing resolves.

    Returns:
        The resolved project id.

    Raises:
        Exit: If no project id can be resolved.

    """
    from reflex_cli.utils import hosting

    if project_name and not project_id:
        project = hosting.search_project(
            project_name, client=client, interactive=interactive
        )
        project_id = str(project.id) if project else None
    project_id = project_id or hosting.get_selected_project()
    if project_id is None:
        logger.error(
            f"no project_id provided or selected. Set it with `reflex cloud project {command} --project-id \\[project_id]`"
        )
        raise click.exceptions.Exit(1)
    return project_id


def _print_rows(rows: list[dict[str, Any]], as_json: bool) -> None:
    """Print a listing as a JSON document, or as a table of its fields.

    Args:
        rows: The rows, already rendered as plain data.
        as_json: Whether the caller asked for JSON.

    """
    if as_json:
        print_json(rows)
        return
    if not rows:
        # If returned empty list, print the empty
        console.print(str(rows))
        return
    console.print_table(
        [
            [
                json.dumps(value)
                if isinstance(value, (dict, list))
                else ""
                if value is None
                else str(value)
                for value in row.values()
            ]
            for row in rows
        ],
        headers=list(rows[0].keys()),
    )


@project_cli.command(name="create")
@click.argument("name", required=True)
@click.option("--token", help="The authentication token.")
@_loglevel_option
@json_option
@interactive_option
def create_project(
    name: str,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Create a new project."""
    from reflex_build_sdk import ConflictError

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        try:
            project = authenticated_client.api.projects.create(name)
        except ConflictError as err:
            logger.error(
                f"A project named '{name}' already exists. Please use a different name."
            )
            raise click.exceptions.Exit(1) from err

    document = hosting.as_json_document(project)
    if as_json:
        print_json(document)
        return
    console.print_table(
        [[str(value) for value in document.values()]], headers=list(document)
    )


@project_cli.command(name="invite")
@click.argument("role", required=True)
@click.argument("user", required=True)
@click.option("--token", help="The authentication token.")
@_loglevel_option
@json_option
@interactive_option
def invite_user_to_project(
    role: str,
    user: str,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Invite a user to a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        outcome = authenticated_client.api.projects.members.set_role(
            user_id=user, role_id=role
        )

    if as_json:
        print_json({
            "role_id": role,
            "user_id": user,
            "invited": True,
            "status": outcome,
        })
        return
    if outcome == "pending_approval":
        logger.log(
            log.SUCCESS,
            "Invite submitted; a project admin has to approve it before it takes effect.",
        )
    else:
        logger.log(log.SUCCESS, "Successfully invited user to project.")


@project_cli.command(name="select")
@click.argument("project_id", required=False)
@click.option("--project-name", help="The name of the project. ")
@click.option("--token", help="The authentication token.")
@_loglevel_option
@json_option
@interactive_option
def select_project(
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Select a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        # check if provided project exists.
        if project_id:
            authenticated_client.api.projects.get(project_id)
        elif project_name:
            project = hosting.search_project(
                project_name, interactive=interactive, client=authenticated_client
            )
            project_id = str(project.id) if project else None

    if not project_id:
        logger.error("No project selected. Please provide a valid project ID or name.")
        raise click.exceptions.Exit(1)

    result = hosting.select_project(project=project_id, token=token)
    if "failed" in result:
        logger.error(result)
        raise click.exceptions.Exit(1)
    if as_json:
        print_json({"project_id": project_id, "selected": True, "message": result})
        return
    logger.log(log.SUCCESS, result)


@project_cli.command(name="selected")
@_loglevel_option
@click.option("--token", help="The authentication token.")
@json_option
@interactive_option
def get_select_project(
    loglevel: str,
    token: str | None,
    as_json: bool,
    interactive: bool,
):
    """Get the currently selected project."""
    from reflex_build_sdk import AuthenticationError, MissingTokenError

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    project = hosting.get_selected_project()
    if not project:
        if as_json:
            print_json({"project_id": None, "name": None, "error": None})
        else:
            logger.warning(
                "no selected project. run `reflex cloud project select` to set one."
            )
        return

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        try:
            details = authenticated_client.api.projects.get(project)
        except (AuthenticationError, MissingTokenError):
            # A token that will not authenticate is not a lookup that failed;
            # it has its own answer, and it is the same one everywhere.
            raise
        except Exception as ex:
            logger.error(f"Unable to get the currently selected project: {ex}")
            if as_json:
                # Not the empty-selection document above: silence on stdout
                # with a zero exit reads as "nothing is selected", which is a
                # different answer from "the lookup failed".
                print_json({"project_id": project, "name": None, "error": str(ex)})
            raise click.exceptions.Exit(1) from None

    if as_json:
        print_json({"project_id": project, "name": details.name, "error": None})
        return
    console.print_table(
        [[project, details.name]],
        headers=["Selected Project ID", "Project Name"],
    )


@project_cli.command(name="list")
@click.option("--token", help="The authentication token.")
@_loglevel_option
@json_option
@interactive_option
def get_projects(
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve a list of projects."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        projects = authenticated_client.api.projects.list()

    _print_rows([hosting.as_json_document(project) for project in projects], as_json)


@project_cli.command(name="roles")
@project_options
def get_project_roles(
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the roles for a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        project_id = _resolve_project_id(
            project_id, project_name, authenticated_client, interactive, "roles"
        )
        roles = authenticated_client.api.projects.roles.list(project_id)

    _print_rows([hosting.as_json_document(role) for role in roles], as_json)


@project_cli.command(name="role-permissions")
@click.argument("role_id", required=True)
@project_options
def get_project_role_permissions(
    role_id: str,
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the permissions for a specific role in a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        project_id = _resolve_project_id(
            project_id,
            project_name,
            authenticated_client,
            interactive,
            "role-permissions",
        )
        permissions = authenticated_client.api.projects.roles.permissions(
            project_id, role_id
        )

    if as_json:
        print_json(permissions)
        return
    if permissions:
        console.print_table(
            [[permission] for permission in permissions], headers=["Permission"]
        )
    else:
        # If returned empty list, print the empty
        console.print(str(permissions))


@project_cli.command(name="users")
@project_options
def get_project_role_users(
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the users for a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        project_id = _resolve_project_id(
            project_id, project_name, authenticated_client, interactive, "users"
        )
        users = authenticated_client.api.projects.members.list(project_id)

    _print_rows([hosting.as_json_document(user) for user in users], as_json)
