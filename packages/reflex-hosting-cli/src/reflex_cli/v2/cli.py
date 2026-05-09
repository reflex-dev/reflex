"""CLI for the hosting service."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from packaging import version

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.dependency import extract_domain


def login(
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
) -> dict[str, Any]:
    """Authenticate with Reflex hosting service.

    Args:
        loglevel: The log level to use.

    Returns:
        Information about the logged in user.

    Raises:
        SystemExit: If the command fails.

    """
    from reflex_cli.utils import hosting

    # Set the log level.
    console.set_log_level(loglevel)

    access_token, validated_info = hosting.authenticated_token()
    if access_token:
        console.print("You already logged in.")
        return validated_info

    # If not already logged in, open a browser window/tab to the login page.
    access_token, validated_info = hosting.authenticate_on_browser()

    if not access_token:
        console.error("Unable to authenticate. Please try again or contact support.")
        raise SystemExit(1)

    console.print("Successfully logged in.")
    return validated_info


def logout(
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
):
    """Log out of access to Reflex hosting service.

    Args:
        loglevel: The log level to use.

    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    console.debug("Deleting access token from config locally")
    hosting.delete_token_from_config()
    console.success("Successfully logged out.")


def deploy(
    export_fn: Callable[[str, str, str, bool, bool, bool, bool], None]
    | Callable[[str, str, str, bool, bool, bool], None],
    app_name: str | None = None,
    description: str | None = None,
    regions: list[str] | None = None,
    project: str | None = None,
    envs: list[str] | None = None,
    vmtype: str | None = None,
    hostname: str | None = None,
    interactive: bool = True,
    envfile: str | None = None,
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
    token: str | None = None,
    config_path: str | None = None,
    env: str | None = None,
    project_name: str | None = None,
    app_id: str | None = None,
    **kwargs,
):
    """Deploy the app to the Reflex hosting service.

    Args:
        app_name: The name of the app.
        export_fn: The function from the Reflex main framework to export the app.
        description: The app's description.
        regions: The regions to deploy to.
        project: The project to deploy to.
        envs: The environment variables to set.
        vmtype: The VM type to allocate.
        hostname: The hostname to use for the frontend.
        interactive: Whether to use interactive mode.
        envfile: The path to an env file to use. Will override any envs set manually.
        loglevel: The log level to use.
        token: The authentication token.
        config_path: The path to the config file.
        env: The environment to use for deployment.
        project_name: The name of the project.
        app_id: The ID of the app.
        **kwargs: Additional keyword arguments.

    Raises:
        Exit: If the command fails.

    """
    import httpx

    from reflex_cli.utils import hosting

    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    # Set the log level.
    console.set_log_level(loglevel)
    project_id = project
    config = {}
    config_from_file = hosting.read_config(config_path, env=env)
    if config_from_file:
        config = dataclasses.asdict(config_from_file)

    packages = None
    strategy = None
    include_db = False
    # If a config file is provided, use values from the file that are not provided as arguments.
    if config:
        if not regions:
            regions = config.get("regions", None)
        if not vmtype:
            vmtype = config.get("vmtype", None)
        if not hostname:
            hostname = config.get("hostname", None)
        if not envfile:
            envfile = config.get("envfile", None)
        if not project_id:
            project_id = config.get("project", None)
        if not project_name:
            project_name = config.get("projectname", None)
        if not app_id:
            app_id = config.get("appid", None)
            if not isinstance(app_id, (str, type(None))):
                console.error(
                    "app_id must be a string or None. Please check your config file."
                )
                raise SystemExit(1)
        if not packages:
            packages = config.get("packages", None)
        if not include_db:
            include_db = config.get("include_db", False)
        if not strategy:
            strategy = config.get("strategy", None)
        app_name = config.get("name", app_name)
        if not isinstance(app_name, (str, type(None))):
            console.error(
                "app_name must be a string or None. Please check your config file."
            )
            raise SystemExit(1)
        if app_name == "default":
            # not sure if this is the best check?
            console.error(
                "Please set real config values in cloud.yml or pyproject.toml"
            )
            raise SystemExit(1)
        if not description:
            description = config.get("description", None)

    # resolve the project id from the project name.
    if project_name and not project_id:
        result = hosting.search_project(
            project_name, client=authenticated_client, interactive=interactive
        )
        project_id = result.get("id") if result else None

    try:
        # check if provided project exists.
        if project_id:
            hosting.get_project(project_id, client=authenticated_client)
        else:
            project_id = hosting.get_selected_project()
    except httpx.HTTPStatusError as ex:
        try:
            console.error(ex.response.json().get("detail"))
        except json.JSONDecodeError:
            console.error(ex.response.text)
        raise click.exceptions.Exit(1) from ex

    envs = envs or []

    if not app_name and not app_id:
        console.error(
            "Please provide a valid app name or ID for the deployed instance."
        )
        raise click.exceptions.Exit(1)
    try:
        if app_name and not app_id:
            search_project_id = project_id
            if not interactive and not project and not search_project_id:
                search_project_id = hosting.get_selected_project()
            elif interactive and not project:
                search_project_id = None

            app = hosting.search_app(
                app_name=app_name,
                project_id=search_project_id,
                client=authenticated_client,
                interactive=interactive,
            )
        else:
            app = hosting.get_app(app_id or "", client=authenticated_client)
            app_name = app.get("name")
    except click.exceptions.Exit:
        raise
    except Exception as ex:
        console.error(f"Deployment failed: {ex}")
        raise click.exceptions.Exit(1) from ex

    if app and interactive and not project and not app_id:
        default_project_id = hosting.get_selected_project()
        app_project_id = app.get("project_id")

        if app_project_id and (
            not default_project_id or app_project_id != default_project_id
        ):
            app_project = hosting.get_project(
                app_project_id, client=authenticated_client
            )
            app_project_name = app_project.get("name", "Unknown")
            if (
                console.ask(
                    f"Deploy to app '{app['name']}' in project '{app_project_name}'?",
                    choices=["y", "n"],
                    default="y",
                )
                != "y"
            ):
                console.info("Deployment cancelled.")
                raise click.exceptions.Exit(0)

            project_id = app_project_id

    if not app and interactive:
        if (
            console.ask(
                f"No app with {app_name or app_id} found. Do you want to create a new app to deploy?",
                choices=["y", "n"],
                default="y",
            )
            == "y"
        ):
            # Check if we need confirmation for deploying to non-default project
            if not project:
                default_project_id = hosting.get_selected_project()
                if not default_project_id:
                    try:
                        if project_id:
                            target_project = hosting.get_project(
                                project_id, client=authenticated_client
                            )
                            project_name = target_project.get("name", "Unknown")
                        else:
                            token = hosting.get_existing_access_token()
                            default_project_id = hosting.get_default_project(
                                authenticated_client
                            )
                            if default_project_id:
                                default_project = hosting.get_project(
                                    default_project_id, client=authenticated_client
                                )
                                project_name = default_project.get(
                                    "name", "Default Project"
                                )
                            else:
                                project_name = "Default Project"
                    except Exception:
                        project_name = "Unknown"

                    if (
                        console.ask(
                            f"Create and deploy app '{app_name}' in project '{project_name}'?",
                            choices=["y", "n"],
                            default="y",
                        )
                        != "y"
                    ):
                        console.info("Deployment cancelled.")
                        raise click.exceptions.Exit(0)
                elif project_id and project_id != default_project_id:
                    try:
                        target_project = hosting.get_project(
                            project_id, client=authenticated_client
                        )
                        project_name = target_project.get("name", "Unknown")
                    except Exception:
                        project_name = "Unknown"

                    if (
                        console.ask(
                            f"Create and deploy app '{app_name}' in project '{project_name}'?",
                            choices=["y", "n"],
                            default="y",
                        )
                        != "y"
                    ):
                        console.info("Deployment cancelled.")
                        raise click.exceptions.Exit(0)

            if description is None:
                description = console.ask(
                    "App Description (Enter to skip)",
                )
            app = hosting.create_app(
                app_name=app_name or "",
                description=description,
                project_id=project_id,
                client=authenticated_client,
            )
            console.info(f"created app. \nName: {app['name']} \nId: {app['id']}")
        else:
            console.error("Please create an app to deploy.")
            raise click.exceptions.Exit(1)
    elif not app:
        app = hosting.create_app(
            app_name=app_name or "",
            description=description or "",
            project_id=project_id,
            client=authenticated_client,
        )
        console.info(f"created app. \nName: {app['name']} \nId: {app['id']}")

    urls = hosting.get_hostname(
        app_id=app["id"],
        app_name=app["name"],
        hostname=hostname,
        client=authenticated_client,
    )
    if "error" in urls:
        console.error(urls["error"])
        raise click.exceptions.Exit(1)
    server_url = os.getenv("REFLEX_OVERRIDE_BACKEND_URL") or urls["server"]  # backend
    host_url = os.getenv("REFLEX_OVERRIDE_FRONTEND_URL") or urls["hostname"]  # frontend
    processed_envs = hosting.process_envs(envs) if envs else None

    if not app_name:
        console.error("Please set an app name.")
        raise click.exceptions.Exit(1)

    # at this point, if project_id is None, the App should have the correct project_id and
    # we should use that going forward to pass validation checks.
    project_id = project_id or app.get("project_id")

    validation_message = hosting.validate_deployment_args(
        app_name=app_name,
        app_id=app.get("id"),
        project_id=project_id,
        regions=regions,
        vmtype=vmtype,
        hostname=hostname,
        client=authenticated_client,
    )

    if validation_message != "success":
        console.error(validation_message)
        raise click.exceptions.Exit(1)

    if envfile:
        try:
            from dotenv import dotenv_values  # pyright: ignore[reportMissingImports]

            processed_envs = dotenv_values(envfile)
        except ImportError:
            console.error(
                """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
            )
            raise click.exceptions.Exit(1) from None

    # Compile the app in production mode: backend first then frontend.
    temporary_dir = tempfile.TemporaryDirectory()
    temporary_dir_path = Path(temporary_dir.name)

    import importlib.metadata

    rx_version = version.parse(importlib.metadata.version("reflex"))
    breaking_version = version.parse("0.7.6")
    # Try zipping backend first
    try:
        # Check if the reflex version is >= 0.7.6
        if rx_version <= breaking_version:
            export_fn(
                str(temporary_dir_path),
                server_url,
                host_url,
                False,
                True,
                True,
            )  # pyright: ignore[reportCallIssue]
        else:
            export_fn(
                str(temporary_dir_path),
                server_url,
                host_url,
                False,
                True,
                include_db,
                True,  # pyright: ignore[reportCallIssue]
            )
    except Exception as ex:
        console.error(f"Unable to export due to: {ex}")
        if temporary_dir_path.exists():
            shutil.rmtree(temporary_dir_path)
        raise click.exceptions.Exit(1) from ex

    # Zip frontend
    try:
        # Check if the reflex version is >= 0.7.6
        if rx_version <= breaking_version:
            export_fn(str(temporary_dir_path), server_url, host_url, True, False, True)  # pyright: ignore[reportCallIssue]
        else:
            export_fn(
                str(temporary_dir_path),
                server_url,
                host_url,
                True,
                False,
                include_db,
                True,  # pyright: ignore[reportCallIssue]
            )
    except ImportError as ie:
        console.error(
            f"Encountered ImportError, did you install all the dependencies? {ie}"
        )
        if temporary_dir_path.exists():
            shutil.rmtree(temporary_dir_path)
        raise click.exceptions.Exit(1) from ie
    except Exception as ex:
        console.error(f"Unable to export due to: {ex}")
        if temporary_dir_path.exists():
            shutil.rmtree(temporary_dir_path)
        raise click.exceptions.Exit(1) from ex

    result = hosting.create_deployment(
        app_id=app.get("id"),
        app_name=app_name,
        project_id=project_id,
        regions=regions,
        zip_dir=Path(temporary_dir_path),
        hostname=extract_domain(host_url) if hostname else None,
        vmtype=vmtype,
        secrets=processed_envs,
        client=authenticated_client,
        packages=packages,
        strategy=strategy,
    )
    if "failed" in result:
        console.error(result)
        raise click.exceptions.Exit(1)
    hosting_ui_url = f"{constants.Hosting.HOSTING_SERVICE_UI}/project/{app['project_id']}/app/{app['id']}/"
    console.print(
        f"deployment progress can now be viewed on the website: {hosting_ui_url}"
    )
    console.print(
        f"you are now safe to exit this command.\nfollow along with the deployment with the following command: \n  reflex cloud apps status {result} --watch"
    )
    status = hosting.watch_deployment_status(result, client=authenticated_client)
    if status is False:
        raise click.exceptions.Exit(1)
