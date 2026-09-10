"""App commands for the Reflex Cloud CLI."""

from __future__ import annotations

import logging
from typing import Any

import click

from reflex_cli import constants
from reflex_cli.core.config import Config
from reflex_cli.utils import console, log
from reflex_cli.utils.exceptions import (
    ConfigInvalidFieldValueError,
    GetAppError,
    NotAuthenticatedError,
    ResponseError,
    ScaleAppError,
    ScaleParamError,
    ScaleTypeError,
)
from reflex_cli.utils.output import interactive_option, json_option, print_json

logger = logging.getLogger(__name__)


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
        app_id = result.get("id") if result else None

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

        if app_name is not None and app_id is None:
            result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = result.get("id") if result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        history = hosting.get_app_history(app_id=app_id, client=authenticated_client)

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
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


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
    try:
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

        result = hosting.rollback_deployment(
            app_id=app_id, deployment_id=deployment_id, client=authenticated_client
        )
        if result:
            logger.error(result)
            raise click.exceptions.Exit(1)
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
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


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
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        app_id = _resolve_app_id(app_id, app_name, authenticated_client, interactive)

        result = hosting.update_deployment_description(
            app_id=app_id,
            deployment_id=deployment_id,
            description=description,
            client=authenticated_client,
        )
        if result:
            logger.error(result)
            raise click.exceptions.Exit(1)
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
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


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

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        logs = hosting.get_deployment_build_logs(
            deployment_id=deployment_id, client=authenticated_client
        )
        if as_json:
            print_json({"deployment_id": deployment_id, "logs": logs})
            return
        console.print(logs)
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        if watch:
            succeeded = hosting.watch_deployment_status(
                deployment_id=deployment_id, client=authenticated_client
            )
            if as_json:
                # Re-read once the watch ends: the watch itself reports
                # progress through the log stream and returns only whether it
                # got there, which is not a status a caller can act on.
                print_json({
                    "deployment_id": deployment_id,
                    "status": hosting.get_deployment_status(
                        deployment_id=deployment_id, client=authenticated_client
                    ),
                    "success": succeeded,
                })
            if succeeded is False:
                raise click.exceptions.Exit(1)
        else:
            status = hosting.get_deployment_status(
                deployment_id=deployment_id, client=authenticated_client
            )
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
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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

        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        result = hosting.stop_app(app_id=app_id, client=authenticated_client)
        failed = bool(result) and "failed" in result
        if as_json:
            print_json({"app_id": app_id, "stopped": not failed, "message": result})
            return
        if result:
            logger.error(result) if failed else logger.log(log.SUCCESS, result)
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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

        if app_name is not None and app_id is None:
            app_result = hosting.search_app(
                app_name=app_name,
                project_id=None,
                client=authenticated_client,
                interactive=interactive,
            )
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        result = hosting.start_app(app_id=app_id, client=authenticated_client)
        failed = bool(result) and "failed" in result
        if as_json:
            print_json({"app_id": app_id, "started": not failed, "message": result})
            return
        if result:
            logger.error(result) if failed else logger.log(log.SUCCESS, result)
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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
            app_id = app_result.get("id") if app_result else None
            app_name_from_search = app_result.get("name") if app_result else app_name

        if app_name_from_search is None and app_id:
            try:
                app_result = hosting.get_app(
                    client=authenticated_client,
                    app_id=app_id,
                )
            except GetAppError:
                logger.warning(f"No application found with ID '{app_id}'")
                if as_json:
                    print_json({
                        "app_id": app_id,
                        "deleted": False,
                        "message": f"No application found with ID '{app_id}'",
                    })
                return
            if not app_result:
                logger.warning(f"App with ID '{app_id}' not found.")
                if as_json:
                    # The one exit here that is zero, so nothing else says the
                    # app was not deleted. The branches that exit non-zero
                    # answer through their status.
                    print_json({
                        "app_id": app_id,
                        "deleted": False,
                        "message": f"App with ID '{app_id}' not found.",
                    })
                raise click.exceptions.Exit(0)

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
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
                logger.info("Deletion cancelled.")
                if as_json:
                    print_json({
                        "app_id": app_id,
                        "deleted": False,
                        "cancelled": True,
                    })
                return

        result = hosting.delete_app(app_id=app_id, client=authenticated_client)
        if as_json:
            # A refusal comes back as a message rather than as an exception, so
            # the document has to read it too: reporting the call as a deletion
            # is how a caller ends up believing an app is gone.
            failed = result is None or (isinstance(result, str) and "failed" in result)
            print_json({
                "app_id": app_id,
                "deleted": not failed,
                "message": result,
            })
            return
        if result:
            logger.warning(result)
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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
@json_option
@interactive_option
@click.option("--cursor", type=str, help="The cursor for pagination.")
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
    cursor: str | None = None,
    pretty: bool = False,
    follow: bool = False,
):
    """Retrieve logs for a given application."""
    import pprint

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
            app_id = app_result.get("id") if app_result else None

        if not app_id:
            logger.error("No valid app_id or app_name provided.")
            raise click.exceptions.Exit(1)

        if offset is None and start is None and end is None:
            offset = 3600
        if not offset and not (start and end):
            logger.error("must provide both start and end")
            raise click.exceptions.Exit(1)

        # Following means prompting between pages, which never returns on its
        # own, so it needs somebody at the terminal and a stream that is not
        # carrying a JSON document.
        following = follow and interactive and not as_json

        while True:
            logger.debug(f"fetching logs with cursor: {cursor}")
            result = hosting.get_app_logs(
                app_id=app_id,
                offset=offset,
                start=start,
                end=end,
                client=authenticated_client,
                cursor=cursor,
            )
            if not isinstance(result, list):
                # A string is the server's own reason; None is a request or a
                # decode that failed, which has none to give.
                reason = (
                    result if isinstance(result, str) else "Unable to retrieve logs."
                )
                logger.warning(reason)
                if as_json:
                    # Kept apart from an empty page: "we could not read them"
                    # and "there are none" call for different next steps.
                    print_json({
                        "app_id": app_id,
                        "entries": [],
                        "cursor": None,
                        "error": reason,
                    })
                return
            if len(result) == 2 and isinstance(result[1], str):
                cursor = result[1]
                result = result[0]
            else:
                cursor = None
            if not result:
                logger.warning("No logs found for the specified criteria.")
                if as_json:
                    print_json({
                        "app_id": app_id,
                        "entries": [],
                        "cursor": cursor,
                        "error": None,
                    })
                return
            result.reverse()
            if as_json:
                # One page per invocation, with the cursor to ask for the next:
                # a document is only a document once it is complete, so paging
                # is the caller's loop rather than ours.
                print_json({
                    "app_id": app_id,
                    "entries": result,
                    "cursor": cursor,
                    "error": None,
                })
                return
            for log in result:
                if pretty:
                    log = pprint.pformat(log, indent=2)
                logger.info(log)
            if not following:
                return
            from rich.prompt import Prompt

            prompt = Prompt.ask(
                "Press Enter to fetch next 100 logs or type 'exit' to quit",
                default="",
                show_default=False,
            )
            if prompt.lower() == "exit":
                logger.info("Exiting log retrieval.")
                return
    except ResponseError as err:
        logger.error(f"Error retrieving logs: {err}")
        raise click.exceptions.Exit(1) from err
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
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

        if project_id is not None and not as_json:
            try:
                project = hosting.get_project(project_id, client=authenticated_client)
                logger.info(
                    f"Listing apps for project '{project['name']}' ({project_id})"
                )
            except Exception:
                pass

        deployments = hosting.list_apps(project=project_id, client=authenticated_client)
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
    except Exception as ex:
        logger.error("Unable to list deployments")
        raise click.exceptions.Exit(1) from ex

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

    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
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

        if not app_id:
            logger.error(
                "No valid app_id provided or found in cloud.yml or pyproject.toml."
            )
            raise click.exceptions.Exit(1)

        app_info = hosting.get_app(app_id=app_id, client=authenticated_client)

        if as_json:
            print_json(app_info)
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
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
