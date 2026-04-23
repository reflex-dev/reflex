"""Project commands for the Reflex Cloud CLI."""

import json

import click

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import NotAuthenticatedError


@click.group()
def project_cli():
    """Commands for managing projects."""
    pass


@project_cli.command(name="create")
@click.argument("name", required=True)
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def create_project(
    name: str,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Create a new project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        project = hosting.create_project(name=name, client=authenticated_client)
    except ValueError as err:
        console.error(str(err))
        raise click.exceptions.Exit(1) from err
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err

    if as_json:
        console.print(json.dumps(project))
        return
    if project:
        project = [project]
        headers = list(project[0].keys())
        table = [
            [str(value) if value is not None else "" for value in p.values()]
            for p in project
        ]
        console.print_table(table, headers=headers)
    else:
        console.print(str(project))


@project_cli.command(name="invite")
@click.argument("role", required=True)
@click.argument("user", required=True)
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def invite_user_to_project(
    role: str,
    user: str,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Invite a user to a project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        result = hosting.invite_user_to_project(
            role_id=role, user_id=user, client=authenticated_client
        )
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err

    if "failed" in result:
        console.error(f"Unable to invite user to project: {result}")
        raise click.exceptions.Exit(1)
    console.success("Successfully invited user to project.")


@project_cli.command(name="select")
@click.argument("project_id", required=False)
@click.option("--project-name", help="The name of the project. ")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
def select_project(
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Select a project."""
    import httpx

    from reflex_cli.utils import hosting

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        # check if provided project exists.
        if project_id:
            hosting.get_project(project_id, client=authenticated_client)
    except httpx.HTTPStatusError as ex:
        try:
            console.error(ex.response.json().get("detail"))
        except json.JSONDecodeError:
            console.error(ex.response.text)
        raise click.exceptions.Exit(1) from ex

    if project_name and not project_id:
        result = hosting.search_project(
            project_name, interactive=interactive, client=authenticated_client
        )
        project_id = result.get("id") if result else None

    if not project_id:
        console.error("No project selected. Please provide a valid project ID or name.")
        raise click.exceptions.Exit(1)

    console.set_log_level(loglevel)
    result = hosting.select_project(project=project_id, token=token)
    if "failed" in result:
        console.error(result)
        raise click.exceptions.Exit(1)
    console.success(result)


@project_cli.command(name="selected")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option("--token", help="The authentication token.")
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def get_select_project(
    loglevel: str,
    token: str | None,
    interactive: bool,
):
    """Get the currently selected project."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    project = hosting.get_selected_project()
    if project:
        try:
            authenticated_client = hosting.get_authenticated_client(
                token=token, interactive=interactive
            )
            project_details = hosting.get_project(
                project_id=project, client=authenticated_client
            )
            console.print_table(
                [[project, project_details["name"]]],
                headers=["Selected Project ID", "Project Name"],
            )
        except NotAuthenticatedError:
            console.error(
                "You are not authenticated. Run `reflex login` to authenticate."
            )
            click.exceptions.Exit(1)
        except Exception as e:
            console.error(f"Unable to get the currently selected project: {e}")
    else:
        console.warn(
            "no selected project. run `reflex cloud project select` to set one."
        )


@project_cli.command(name="list")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def get_projects(
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve a list of projects."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        projects = hosting.get_projects(client=authenticated_client)
        if as_json:
            console.print(json.dumps(projects))
            return
        if projects:
            headers = list(projects[0].keys())
            table = []
            for project in projects:
                row = []
                for value in project.values():
                    if isinstance(value, (dict, list)):
                        row.append(json.dumps(value))
                    else:
                        row.append(str(value))
                table.append(row)
            console.print_table(table, headers=headers)
        else:
            # If returned empty list, print the empty
            console.print(str(projects))
    except NotAuthenticatedError:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        click.exceptions.Exit(1)
    except Exception as e:
        console.error(f"Unable to get projects: {e}")
        raise click.exceptions.Exit(1) from e


@project_cli.command(name="roles")
@click.option(
    "--project-id",
    help="The ID of the project. If not provided, the selected project will be used. If no project_id is provided or selected throws an error.",
)
@click.option("--project-name", help="The name of the project. ")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
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

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if project_name and not project_id:
            result = hosting.search_project(
                project_name, client=authenticated_client, interactive=interactive
            )
            project_id = result.get("id") if result else None
        if project_id is None:
            project_id = hosting.get_selected_project()
        if project_id is None:
            console.error(
                "no project_id provided or selected. Set it with `reflex cloud project roles --project-id \\[project_id]`"
            )
            raise click.exceptions.Exit(1)

        roles = hosting.get_project_roles(
            project_id=project_id, client=authenticated_client
        )

        if as_json:
            console.print(json.dumps(roles))
            return
        if roles:
            headers = list(roles[0].keys())
            table = [
                [str(value) if value is not None else "" for value in role.values()]
                for role in roles
            ]
            console.print_table(table, headers=headers)
        else:
            # If returned empty list, print the empty
            console.print(str(roles))
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@project_cli.command(name="role-permissions")
@click.argument("role_id", required=True)
@click.option(
    "--project-id",
    help="The ID of the project. If not provided, the selected project will be used. If no project is selected, it throws an error.",
)
@click.option("--project-name", help="The name of the project. ")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
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
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if project_name and not project_id:
            result = hosting.search_project(
                project_name, client=authenticated_client, interactive=interactive
            )
            project_id = result.get("id") if result else None
        if project_id is None:
            project_id = hosting.get_selected_project()
        if project_id is None:
            console.error(
                "no project_id provided or selected. Set it with `reflex cloud project role-permissions --project-id \\[project_id]`."
            )
            raise click.exceptions.Exit(1)

        permissions = hosting.get_project_role_permissions(
            project_id=project_id, role_id=role_id, client=authenticated_client
        )

        if as_json:
            console.print(json.dumps(permissions))
            return
        if permissions:
            headers = list(permissions[0].keys())
            table = [
                [
                    str(value) if value is not None else ""
                    for value in permission.values()
                ]
                for permission in permissions
            ]
            console.print_table(table, headers=headers)
        else:
            # If returned empty list, print the empty
            console.print(str(permissions))
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@project_cli.command(name="users")
@click.option(
    "--project-id",
    help="The ID of the project. If not provided, the selected project will be used. If no project is selected, it throws an error.",
)
@click.option("--project-name", help="The name of the project. ")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
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

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if project_name and not project_id:
            result = hosting.search_project(
                project_name, client=authenticated_client, interactive=interactive
            )
            project_id = result.get("id") if result else None
        if project_id is None:
            project_id = hosting.get_selected_project()
        if project_id is None:
            console.error(
                "no project_id provided or selected. Set it with `reflex cloud project users --project-id \\[project_id]`"
            )
            raise click.exceptions.Exit(1)

        users = hosting.get_project_role_users(
            project_id=project_id, client=authenticated_client
        )

        if as_json:
            console.print(json.dumps(users))
            return
        if users:
            headers = list(users[0].keys())
            table = [
                [str(value) if value is not None else "" for value in user.values()]
                for user in users
            ]
            console.print_table(table, headers=headers)
        else:
            # If returned empty list, print the empty
            console.print(str(users))
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
