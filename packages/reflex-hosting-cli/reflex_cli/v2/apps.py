"""App commands for the Reflex Cloud CLI."""

from __future__ import annotations

import json

import click

from reflex_cli import constants
from reflex_cli.core.config import Config
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import (
    ConfigInvalidFieldValueError,
    GetAppError,
    NotAuthenticatedError,
    ResponseError,
    ScaleAppError,
    ScaleParamError,
    ScaleTypeError,
)


@click.group()
def apps_cli():
    """Commands for managing apps."""
    pass


@apps_cli.command(name="history")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the application.")
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
def app_history(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the deployment history for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if app_name is not None and app_id is None:
            result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = result.get("id") if result else None

        if not app_id:
            console.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        history = hosting.get_app_history(app_id=app_id, client=authenticated_client)

        if as_json:
            console.print(json.dumps(history))
            return
        if history:
            headers = list(history[0].keys())
            table = [
                [str(value) for value in deployment.values()] for deployment in history
            ]
            console.print_table(table, headers=headers)
        else:
            console.print(str(history))
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command("build-logs")
@click.argument("deployment_id", required=True)
@click.option("--token", help="The authentication token.")
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def deployment_build_logs(
    deployment_id: str,
    token: str | None,
    interactive: bool,
):
    """Retrieve the build logs for a specific deployment."""
    from reflex_cli.utils import hosting

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        logs = hosting.get_deployment_build_logs(
            deployment_id=deployment_id, client=authenticated_client
        )
        console.print(logs)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="status")
@click.argument("deployment_id", required=True)
@click.option(
    "--watch/--no-watch", is_flag=True, help="Whether to continuously watch the status."
)
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
def deployment_status(
    deployment_id: str,
    watch: bool,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Retrieve the status of a specific deployment."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if watch:
            status = hosting.watch_deployment_status(
                deployment_id=deployment_id, client=authenticated_client
            )
            if status is False:
                raise click.exceptions.Exit(1)
        else:
            status = hosting.get_deployment_status(
                deployment_id=deployment_id, client=authenticated_client
            )
            console.error(status) if "failed" in status else console.print(status)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="stop")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the application.")
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
def stop_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Stop a running application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            console.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        result = hosting.stop_app(app_id=app_id, client=authenticated_client)
        if result:
            console.error(result) if "failed" in result else console.success(result)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="start")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the application.")
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
def start_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Start a stopped application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            console.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        result = hosting.start_app(app_id=app_id, client=authenticated_client)
        if result:
            console.error(result) if "failed" in result else console.success(result)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="delete")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the application.")
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
def delete_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Delete an application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        app_name_from_search = None
        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            if not app_result:
                console.warn(f"App '{app_name}' not found.")
                raise click.exceptions.Exit(1)
            app_id = app_result.get("id") if app_result else None
            app_name_from_search = app_result.get("name") if app_result else app_name

        if app_name_from_search is None and app_id:
            try:
                app_result = hosting.get_app(
                    client=authenticated_client,
                    app_id=app_id,
                )
            except GetAppError:
                console.warn(f"No application found with ID '{app_id}'")
                return
            if not app_result:
                console.warn(f"App with ID '{app_id}' not found.")
                raise click.exceptions.Exit(0)

        if not app_id:
            console.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        if interactive:
            app_name_display = "Unknown"

            if app_name_from_search is not None:
                app_name_display = app_name_from_search
            elif app_name is not None:
                app_name_display = app_name
            else:
                try:
                    app_details = hosting.get_app(
                        app_id=app_id, client=authenticated_client
                    )
                    app_name_display = app_details.get("name", "Unknown")
                except Exception:
                    app_name_display = "Unknown"

            app_id_display = app_id

            if (
                console.ask(
                    f"Are you sure you want to delete app '{app_name_display}' (ID: {app_id_display})?",
                    choices=["y", "n"],
                    default="n",
                )
                != "y"
            ):
                console.info("Deletion cancelled.")
                return

        result = hosting.delete_app(app_id=app_id, client=authenticated_client)
        if result:
            console.warn(result)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="logs")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the application.")
@click.option("--token", help="The authentication token.")
@click.option("--offset", type=int, help="The offset in seconds from the current time.")
@click.option("--start", type=int, help="The start time in Unix epoch format.")
@click.option("--end", type=int, help="The end time in Unix epoch format.")
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
@click.option("--cursor", type=str, help="The cursor for pagination.")
@click.option("--pretty", type=bool, help="Use pretty printing for logs.")
@click.option(
    "--follow", type=bool, default=True, help="Asks to continue to query logs."
)
def app_logs(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    offset: int | None,
    start: int | None,
    end: int | None,
    loglevel: str,
    interactive: bool,
    cursor: str | None = None,
    pretty: bool = False,
    follow: bool = True,
):
    """Retrieve logs for a given application."""
    from reflex_cli.utils import hosting

    if pretty:
        try:
            import pprint
        except ImportError:
            console.error(
                "pprint module is not available. Please install pprint to use pretty printing."
            )
            raise click.exceptions.Exit(1) from ImportError

    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    if not app_id:
        config = hosting.read_config()
        if config:
            app_id = config.appid
            if not isinstance(app_id, (str, type(None))):
                console.error(
                    "app_id must be a string or None. Please check your config file."
                )
                raise click.exceptions.Exit(1)

    if app_name is not None and app_id is None:
        app_result = hosting.search_app(
            app_name=app_name,
            project_id=None,
            client=authenticated_client,
            interactive=interactive,
        )
        app_id = app_result.get("id") if app_result else None

    if not app_id:
        console.error("No valid app_id or app_name provided.")
        raise click.exceptions.Exit(1)

    if offset is None and start is None and end is None:
        offset = 3600
    if not offset and not (start and end):
        console.error("must provide both start and end")
        raise click.exceptions.Exit(1)

    console.set_log_level(loglevel)

    try:
        console.debug(f"fetching logs with cursor: {cursor}")
        result = hosting.get_app_logs(
            app_id=app_id,
            offset=offset,
            start=start,
            end=end,
            client=authenticated_client,
            cursor=cursor,
        )
        if isinstance(result, list):
            if len(result) == 2:
                cursor = result[1]
                result = result[0]
            if not result:
                console.warn("No logs found for the specified criteria.")
                return
            result.reverse()
            for log in result:
                if pretty:
                    log = pprint.pformat(log, indent=2)  # type: ignore  # noqa: PGH003
                console.info(log)
        else:
            console.warn("Unable to retrieve logs.")
            return
        if interactive and follow:
            from rich.prompt import Prompt

            prompt = Prompt.ask(
                "Press Enter to fetch next 100 logs or type 'exit' to quit",
                default="",
                show_default=False,
            )
            if prompt.lower() == "exit":
                console.info("Exiting log retrieval.")
                raise click.exceptions.Exit(0)
            else:
                ctx = click.get_current_context()
                ctx.invoke(
                    app_logs,
                    app_id=app_id,
                    app_name=None,  # Don't pass app_name again since we have app_id
                    token=token,
                    offset=offset,
                    start=start,
                    end=end,
                    loglevel=loglevel,
                    interactive=interactive,
                    cursor=cursor,
                    pretty=pretty,
                )
    except ResponseError as err:
        console.error(f"Error retrieving logs: {err}")
        raise click.exceptions.Exit(1) from err
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="list")
@click.option("--project", "project_id", help="The project ID to filter deployments.")
@click.option("--project-name", help="The name of the project.")
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
    help="Whether to output the result in JSON format.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
def list_apps(
    project_id: str | None,
    project_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """List all the hosted deployments of the authenticated user. Will exit if unable to list deployments."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

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

    if project_id is not None and not as_json:
        try:
            project = hosting.get_project(project_id, client=authenticated_client)
            console.info(f"Listing apps for project '{project['name']}' ({project_id})")
        except Exception:
            pass

    try:
        deployments = hosting.list_apps(project=project_id, client=authenticated_client)
    except Exception as ex:
        console.error("Unable to list deployments")
        raise click.exceptions.Exit(1) from ex

    if as_json:
        console.print(json.dumps(deployments))
        return
    if deployments:
        headers = list(deployments[0].keys())
        table = [
            [str(value) for value in deployment.values()] for deployment in deployments
        ]
        console.print_table(table, headers=headers)
    else:
        console.print(str(deployments))


@apps_cli.command(name="scale")
@click.argument("app_id", required=False)
@click.option("--app-name", help="The name of the app.")
@click.option("--vmtype", help="The virtual machine type to scale to.")
@click.option("--regions", "-r", multiple=True, help="Region to scale the app to.")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option("--scale-type", help="The type of scaling.")
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def scale_app(
    app_id: str | None,
    app_name: str | None,
    vmtype: str | None,
    regions: tuple[str, ...],
    token: str | None,
    loglevel: str,
    scale_type: str | None,
    interactive: bool,
):
    """Scale an application by changing the VM type or adding/removing regions."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        cli_args = hosting.ScaleAppCliArgs.create(
            regions=list(regions), vm_type=vmtype, scale_type=scale_type
        )
        config = Config.from_yaml_or_toml_or_default().with_overrides(
            vmtype=cli_args.vm_type,
            regions=cli_args.regions,
        )

        if not config.exists() and not cli_args.is_valid:
            console.error(
                "specify either --vmtype or --regions or add them to the cloud.yml or pyproject.toml file"
            )
            raise click.exceptions.Exit(1)

        if config.exists() and cli_args.is_valid:
            console.warn(
                "CLI arguments will override the values in the cloud.yml or pyproject.toml file."
            )
        scale_params = hosting.ScaleParams.from_config(config).set_type_from_cli_args(
            cli_args
        )

        # If app_name is provided, find the app_id
        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            console.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        hosting.scale_app(
            app_id=app_id, scale_params=scale_params, client=authenticated_client
        )
        console.success("Successfully scaled the app.")

    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
    except (
        ScaleAppError,
        ResponseError,
        ConfigInvalidFieldValueError,
        ScaleTypeError,
        ScaleParamError,
    ) as err:
        console.error(err.args[0])
        raise click.exceptions.Exit(1) from err


@apps_cli.command(name="inspect")
@click.argument("app_id", required=False)
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
    help="Whether to output the result in JSON format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def inspect_app(
    app_id: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve detailed information about a specific application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            console.error(
                "No valid app_id provided or found in cloud.yml or pyproject.toml."
            )
            raise click.exceptions.Exit(1)

        app_info = hosting.get_app(app_id=app_id, client=authenticated_client)

        if as_json:
            console.print(json.dumps(app_info))
            return

        if app_info:
            if isinstance(app_info, dict):
                headers = list(app_info.keys())
                values = [[str(value) for value in app_info.values()]]
                console.print_table(values, headers=headers)
            else:
                console.print(str(app_info))
        else:
            console.print("No app information found.")
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
