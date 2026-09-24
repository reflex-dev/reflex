"""App commands for the Reflex Cloud CLI."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import click

from reflex_cli import constants
from reflex_cli.core.config import Config
from reflex_cli.utils import console, log
from reflex_cli.utils.exceptions import (
    ConfigInvalidFieldValueError,
    ResponseError,
    ScaleAppError,
    ScaleParamError,
    ScaleTypeError,
)
from reflex_cli.utils.output import interactive_option, json_option, print_json

logger = logging.getLogger(__name__)

# How many log lines `apps logs --follow` prints before prompting for more.
_LOGS_PAGE_SIZE = 100


@click.group()
def apps_cli():
    """Commands for managing apps."""


def _resolve_app_id(
    app_id: str | None,
    app_name: str | None,
    client: Any,
    interactive: bool,
) -> str:
    """Resolve an app id from --app-id, --app-name, or the cloud config.

    Args:
        app_id: The explicit app id, if given.
        app_name: The app name to look up, if given.
        client: The authenticated client.
        interactive: Whether to interactively resolve name conflicts.

    Returns:
        The resolved app id.

    Raises:
        Exit: If no app id can be resolved.

    """
    from reflex_cli.utils import hosting

    # Explicit --app-id wins, then an explicit --app-name lookup, and only then
    # the cloud.yml/pyproject appid — so passing --app-name always overrides a
    # configured appid rather than being silently ignored.
    if not app_id and app_name is not None:
        result = hosting.search_app(
            app_name=app_name,
            project_id=None,
            client=client,
            interactive=interactive,
        )
        app_id = str(result.id) if result else None

    if not app_id and app_name is None:
        config = hosting.read_config()
        if config:
            app_id = config.appid
            if not isinstance(app_id, (str, type(None))):
                logger.error(
                    "app_id must be a string or None. Please check your config file."
                )
                raise click.exceptions.Exit(1)

    if not app_id:
        logger.error("No valid app_id or app_name provided.")
        raise click.exceptions.Exit(1)
    return app_id


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
@json_option
@interactive_option
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
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
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
            app_id = str(result.id) if result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        history = [
            {
                "id": str(deployment.id),
                "status": deployment.status,
                "url": deployment.url,
                "python version": deployment.python_version,
                "reflex version": deployment.reflex_version,
                "vm type": deployment.vm_type.name if deployment.vm_type else None,
                "timestamp": deployment.created_at.isoformat(),
                "description": deployment.description or "",
                "can rollback": deployment.can_rollback,
            }
            for deployment in authenticated_client.api.apps.history(app_id)
        ]

        if as_json:
            print_json(history)
            return
        if history:
            headers = list(history[0].keys())
            table = [
                [str(value) for value in deployment.values()] for deployment in history
            ]
            console.print_table(table, headers=headers)
        else:
            console.print(str(history))


@apps_cli.command(name="rollback")
@click.argument("deployment_id", required=True)
@click.option("--app-id", help="The ID of the application.")
@click.option("--app-name", help="The name of the application.")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@json_option
@interactive_option
def app_rollback(
    deployment_id: str,
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Roll an app back to a previous deployment.

    Redeploys the target deployment's already-built image and makes it current
    again, without rebuilding from source. DEPLOYMENT_ID is a past deployment
    from `reflex cloud apps history` whose "can rollback" is True. Identify the
    app with --app-id/--app-name or a cloud.yml/pyproject.toml appid.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        app_id = _resolve_app_id(app_id, app_name, authenticated_client, interactive)

        if (
            interactive
            and console.ask(
                f"Roll back to deployment {deployment_id}? The current deployment "
                "will be replaced.",
                choices=["y", "n"],
                default="n",
            )
            != "y"
        ):
            logger.info("Rollback cancelled.")
            if as_json:
                print_json({
                    "app_id": app_id,
                    "deployment_id": deployment_id,
                    "rolled_back": False,
                    "cancelled": True,
                })
            return

        authenticated_client.api.apps.rollback(app_id, deployment_id)
        if as_json:
            print_json({
                "app_id": app_id,
                "deployment_id": deployment_id,
                "rolled_back": True,
                "cancelled": False,
            })
            return
        logger.log(log.SUCCESS, f"Rollback to deployment {deployment_id} started.")
        console.print(
            f"Track progress with `reflex cloud apps status {deployment_id} "
            "--watch` or the Reflex Cloud dashboard."
        )


@apps_cli.command(name="describe")
@click.argument("deployment_id", required=True)
@click.option(
    "--description",
    required=True,
    help='The changelog note to set. Pass --description "" to clear it.',
)
@click.option("--app-id", help="The ID of the application.")
@click.option("--app-name", help="The name of the application.")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@json_option
@interactive_option
def app_describe(
    deployment_id: str,
    description: str,
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Set or clear the changelog note on a past deployment.

    The note is shown in `reflex cloud apps history`. Identify the app with
    --app-id/--app-name or a cloud.yml/pyproject.toml appid.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        app_id = _resolve_app_id(app_id, app_name, authenticated_client, interactive)

        authenticated_client.api.deployments.set_description(
            app_id, deployment_id, description
        )
        if as_json:
            print_json({
                "app_id": app_id,
                "deployment_id": deployment_id,
                "description": description,
            })
            return
        if description.strip():
            logger.log(
                log.SUCCESS, f"Updated description for deployment {deployment_id}."
            )
        else:
            logger.log(
                log.SUCCESS, f"Cleared description for deployment {deployment_id}."
            )


@apps_cli.command("build-logs")
@click.argument("deployment_id", required=True)
@click.option("--token", help="The authentication token.")
@json_option
@interactive_option
def deployment_build_logs(
    deployment_id: str,
    token: str | None,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the build logs for a specific deployment."""
    from reflex_cli.utils import hosting

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        logs = authenticated_client.api.deployments.build_logs(deployment_id)
        if as_json:
            print_json({"deployment_id": deployment_id, "logs": logs})
            return
        console.print(logs)


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
@json_option
@interactive_option
def deployment_status(
    deployment_id: str,
    watch: bool,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve the status of a specific deployment."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if watch:
            result = hosting.watch_deployment_status(
                deployment_id=deployment_id, client=authenticated_client
            )
            if as_json:
                # The watch hands back the last status it saw, so there is
                # nothing to ask the API again -- which matters most where the
                # watch stopped because the API could not be reached.
                print_json({
                    "deployment_id": deployment_id,
                    "status": result.status,
                    # None, not False, for a watch that stopped early: the
                    # deployment is still running and this command did not see
                    # how it ended.
                    "success": None
                    if result.outcome is hosting.WatchOutcome.UNFINISHED
                    else result.outcome is hosting.WatchOutcome.SUCCEEDED,
                })
            if result.failed:
                raise click.exceptions.Exit(1)
        else:
            status = authenticated_client.api.deployments.status(deployment_id)
            failed = hosting.deployment_status_failed(status)
            if as_json:
                # Classified by the predicate --watch settles on, rather than
                # by a substring of its own: a "build error" answered
                # `"success": true` here while --watch called the same string a
                # failure, and it is this path an agent polls.
                print_json({
                    "deployment_id": deployment_id,
                    "status": status,
                    "success": not failed,
                })
                return
            logger.error(status) if failed else console.print(status)


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
@json_option
@interactive_option
def stop_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Stop a running application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
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
            app_id = str(app_result.id) if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        authenticated_client.api.apps.stop(app_id)
        message = "app stopped"
        if as_json:
            print_json({"app_id": app_id, "stopped": True, "message": message})
            return
        logger.log(log.SUCCESS, message)


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
@json_option
@interactive_option
def start_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Start a stopped application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
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
            app_id = str(app_result.id) if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        authenticated_client.api.apps.start(app_id)
        message = "app started"
        if as_json:
            print_json({"app_id": app_id, "started": True, "message": message})
            return
        logger.log(log.SUCCESS, message)


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
@json_option
@interactive_option
def delete_app(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Delete an application."""
    from reflex_build_sdk import NotFoundError

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
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
                logger.warning(f"App '{app_name}' not found.")
                raise click.exceptions.Exit(1)
            app_id = str(app_result.id) if app_result else None
            app_name_from_search = app_result.name

        if app_name_from_search is None and app_id:
            try:
                app_name_from_search = authenticated_client.api.apps.get(app_id).name
            except NotFoundError as err:
                logger.error(f"No application found with ID '{app_id}'")
                raise click.exceptions.Exit(1) from err

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        if interactive:
            app_name_display = "Unknown"

            if app_name_from_search is not None:
                app_name_display = app_name_from_search
            elif app_name is not None:
                app_name_display = app_name

            app_id_display = app_id

            if (
                console.ask(
                    f"Are you sure you want to delete app '{app_name_display}' (ID: {app_id_display})?",
                    choices=["y", "n"],
                    default="n",
                )
                != "y"
            ):
                logger.info("Deletion cancelled.")
                if as_json:
                    print_json({
                        "app_id": app_id,
                        "deleted": False,
                        "cancelled": True,
                    })
                return

        authenticated_client.api.apps.delete(app_id)
        if as_json:
            print_json({
                "app_id": app_id,
                "deleted": True,
                "message": "app deleted",
            })
            return
        logger.log(log.SUCCESS, "app deleted")


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
@json_option
@interactive_option
@click.option("--pretty", type=bool, help="Use pretty printing for logs.")
@click.option(
    "--follow",
    type=bool,
    default=False,
    help="After printing a page, prompt to fetch the next one. Off by default: "
    "the prompt never returns on its own, so a script or an agent that asked "
    "for logs would hang instead of exiting.",
)
def app_logs(
    app_id: str | None,
    app_name: str | None,
    token: str | None,
    offset: int | None,
    start: int | None,
    end: int | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
    pretty: bool = False,
    follow: bool = False,
):
    """Retrieve logs for a given application."""
    import pprint

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
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
            app_id = str(app_result.id) if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        since: datetime.datetime | None = None
        until: datetime.datetime | None = None
        if offset:
            until = datetime.datetime.now(datetime.timezone.utc)
            since = until - datetime.timedelta(seconds=offset)
        elif start or end:
            if not (start and end):
                logger.error("must provide both start and end")
                raise click.exceptions.Exit(1)
            since = datetime.datetime.fromtimestamp(start, datetime.timezone.utc)
            until = datetime.datetime.fromtimestamp(end, datetime.timezone.utc)
        # Asked for no window at all: send none, so the span is the API's own
        # rather than one this command invented. A window of its own would
        # report nothing for an app whose last line predates it, where the
        # command has always answered with the most recent lines it could find.

        # Following means prompting between pages, which never returns on its
        # own, so it needs somebody at the terminal and a stream that is not
        # carrying a JSON document.
        following = follow and interactive and not as_json

        records = authenticated_client.api.apps.logs(
            app_id, start=since, end=until, order="newest_first"
        )

        if as_json:
            # The whole window in one document: paging is the client's, so a
            # caller gets every line it asked for rather than a page and a
            # cursor it had no way to send back.
            print_json({
                "app_id": app_id,
                "entries": [hosting.as_json_document(record) for record in records],
                "cursor": None,
                "error": None,
            })
            return

        printed = 0
        for record in records:
            entry = hosting.as_json_document(record)
            logger.info(pprint.pformat(entry, indent=2) if pretty else entry)
            printed += 1
            if printed % _LOGS_PAGE_SIZE:
                continue
            # A page at a time, as before: the SDK would otherwise walk the
            # whole window, which is not what an unattended `apps logs` asked
            # for.
            if not following:
                return
            from rich.prompt import Prompt

            prompt = Prompt.ask(
                f"Press Enter to fetch next {_LOGS_PAGE_SIZE} logs or type 'exit' to quit",
                default="",
                show_default=False,
            )
            if prompt.lower() == "exit":
                logger.info("Exiting log retrieval.")
                return
        if not printed:
            logger.warning("No logs found for the specified criteria.")


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
@json_option
@interactive_option
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

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if project_name and not project_id:
            result = hosting.search_project(
                project_name, client=authenticated_client, interactive=interactive
            )
            project_id = str(result.id) if result else None

        if project_id is None:
            project_id = hosting.get_selected_project()

        if project_id is not None and not as_json:
            try:
                project = authenticated_client.api.projects.get(project_id)
                logger.info(f"Listing apps for project '{project.name}' ({project_id})")
            except Exception:
                pass

        deployments = [
            hosting.as_json_document(app)
            for app in authenticated_client.api.apps.list(project_id=project_id)
        ]

    if as_json:
        print_json(deployments)
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
@json_option
@interactive_option
def scale_app(
    app_id: str | None,
    app_name: str | None,
    vmtype: str | None,
    regions: tuple[str, ...],
    token: str | None,
    loglevel: str,
    scale_type: str | None,
    as_json: bool,
    interactive: bool,
):
    """Scale an application by changing the VM type or adding/removing regions."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        try:
            authenticated_client = hosting.get_authenticated_client(
                token=token, interactive=interactive
            )

            if not app_id:
                config = hosting.read_config()
                if config:
                    app_id = config.appid
                    if not isinstance(app_id, (str, type(None))):
                        logger.error(
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
                logger.error(
                    "specify either --vmtype or --regions or add them to the cloud.yml or pyproject.toml file"
                )
                raise click.exceptions.Exit(1)

            if config.exists() and cli_args.is_valid:
                logger.warning(
                    "CLI arguments will override the values in the cloud.yml or pyproject.toml file."
                )
            scale_params = hosting.ScaleParams.from_config(
                config
            ).set_type_from_cli_args(cli_args)

            # If app_name is provided, find the app_id
            if app_name is not None and app_id is None:
                app_result = hosting.search_app(
                    app_name=app_name,
                    project_id=None,
                    client=authenticated_client,
                    interactive=interactive,
                )
                app_id = str(app_result.id) if app_result else None

            if not app_id:
                logger.error("No valid app_id or app_name provided.")
                raise click.exceptions.Exit(1)

            hosting.scale_app(
                app_id=app_id, scale_params=scale_params, client=authenticated_client
            )
            if as_json:
                print_json({
                    "app_id": app_id,
                    "scaled": True,
                    "vmtype": scale_params.vm_type,
                    "regions": list(scale_params.regions),
                    "scale_type": scale_params.type,
                })
                return
            logger.log(log.SUCCESS, "Successfully scaled the app.")

        except (
            ScaleAppError,
            ResponseError,
            ConfigInvalidFieldValueError,
            ScaleTypeError,
            ScaleParamError,
        ) as err:
            logger.error(err.args[0])
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
@json_option
@interactive_option
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
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            logger.error(
                "No valid app_id provided or found in cloud.yml or pyproject.toml."
            )
            raise click.exceptions.Exit(1)

        app_info = hosting.as_json_document(authenticated_client.api.apps.get(app_id))

        if as_json:
            print_json(app_info)
            return

        console.print_table(
            [[str(value) for value in app_info.values()]],
            headers=list(app_info.keys()),
        )
