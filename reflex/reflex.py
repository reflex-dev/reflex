"""Reflex CLI to create, run, and deploy apps."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import typer
from alembic.util.exc import CommandError
from tabulate import tabulate

from reflex import constants, model
from reflex.config import get_config
from reflex.utils import (
    build,
    console,
    exec,
    hosting,
    prerequisites,
    processes,
    telemetry,
)

# Create the app.
cli = typer.Typer(add_completion=False)

# Get the config.
config = get_config()


def version(value: bool):
    """Get the Reflex version.

    Args:
        value: Whether the version flag was passed.

    Raises:
        typer.Exit: If the version flag was passed.
    """
    if value:
        console.print(constants.Reflex.VERSION)
        raise typer.Exit()


@cli.callback()
def main(
    version: bool = typer.Option(
        None,
        "-v",
        "--version",
        callback=version,
        help="Get the Reflex version.",
        is_eager=True,
    ),
):
    """Reflex CLI to create, run, and deploy apps."""
    pass


@cli.command()
def init(
    name: str = typer.Option(
        None, metavar="APP_NAME", help="The name of the app to initialize."
    ),
    template: constants.Templates.Kind = typer.Option(
        constants.Templates.Kind.DEFAULT.value,
        help="The template to initialize the app with.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Initialize a new Reflex app in the current directory."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Show system info
    exec.output_system_info()

    # Get the app name.
    app_name = prerequisites.get_default_app_name() if name is None else name
    console.rule(f"[bold]Initializing {app_name}")

    # Set up the web project.
    prerequisites.initialize_frontend_dependencies()

    # Migrate Pynecone projects to Reflex.
    prerequisites.migrate_to_reflex()

    # Set up the app directory, only if the config doesn't exist.
    if not os.path.exists(constants.Config.FILE):
        prerequisites.create_config(app_name)
        prerequisites.initialize_app_directory(app_name, template)
        telemetry.send("init")
    else:
        telemetry.send("reinit")

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()

    # Initialize the requirements.txt.
    prerequisites.initialize_requirements_txt()

    # Finish initializing the app.
    console.success(f"Initialized {app_name}")


@cli.command()
def run(
    env: constants.Env = typer.Option(
        constants.Env.DEV, help="The environment to run the app in."
    ),
    frontend: bool = typer.Option(
        False, "--frontend-only", help="Execute only frontend."
    ),
    backend: bool = typer.Option(False, "--backend-only", help="Execute only backend."),
    frontend_port: str = typer.Option(
        config.frontend_port, help="Specify a different frontend port."
    ),
    backend_port: str = typer.Option(
        config.backend_port, help="Specify a different backend port."
    ),
    backend_host: str = typer.Option(
        config.backend_host, help="Specify the backend host."
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Run the app in the current directory."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Set env mode in the environment
    os.environ["REFLEX_ENV_MODE"] = env.value

    # Show system info
    exec.output_system_info()

    # If no --frontend-only and no --backend-only, then turn on frontend and backend both
    if not frontend and not backend:
        frontend = True
        backend = True

    if not frontend and backend:
        _skip_compile()

    # Check that the app is initialized.
    prerequisites.check_initialized(frontend=frontend)

    # If something is running on the ports, ask the user if they want to kill or change it.
    if frontend and processes.is_process_on_port(frontend_port):
        frontend_port = processes.change_or_terminate_port(frontend_port, "frontend")

    if backend and processes.is_process_on_port(backend_port):
        backend_port = processes.change_or_terminate_port(backend_port, "backend")

    # Apply the new ports to the config.
    if frontend_port != str(config.frontend_port):
        config._set_persistent(frontend_port=frontend_port)
    if backend_port != str(config.backend_port):
        config._set_persistent(backend_port=backend_port)

    console.rule("[bold]Starting Reflex App")

    if frontend:
        # Get the app module.
        prerequisites.get_app()

    # Warn if schema is not up to date.
    prerequisites.check_schema_up_to_date()

    # Get the frontend and backend commands, based on the environment.
    setup_frontend = frontend_cmd = backend_cmd = None
    if env == constants.Env.DEV:
        setup_frontend, frontend_cmd, backend_cmd = (
            build.setup_frontend,
            exec.run_frontend,
            exec.run_backend,
        )
    if env == constants.Env.PROD:
        setup_frontend, frontend_cmd, backend_cmd = (
            build.setup_frontend_prod,
            exec.run_frontend_prod,
            exec.run_backend_prod,
        )
    assert setup_frontend and frontend_cmd and backend_cmd, "Invalid env"

    # Post a telemetry event.
    telemetry.send(f"run-{env.value}")

    # Display custom message when there is a keyboard interrupt.
    atexit.register(processes.atexit_handler)

    # Run the frontend and backend together.
    commands = []

    # Run the frontend on a separate thread.
    if frontend:
        setup_frontend(Path.cwd())
        commands.append((frontend_cmd, Path.cwd(), frontend_port))

    # In prod mode, run the backend on a separate thread.
    if backend and env == constants.Env.PROD:
        commands.append((backend_cmd, backend_host, backend_port))

    # Start the frontend and backend.
    with processes.run_concurrently_context(*commands):
        # In dev mode, run the backend on the main thread.
        if backend and env == constants.Env.DEV:
            backend_cmd(backend_host, int(backend_port))


@cli.command()
def deploy_legacy(
    dry_run: bool = typer.Option(False, help="Whether to run a dry run."),
    loglevel: constants.LogLevel = typer.Option(
        console._LOG_LEVEL, help="The log level to use."
    ),
):
    """Deploy the app to the Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Show system info
    exec.output_system_info()

    # Check if the deploy url is set.
    if config.rxdeploy_url is None:
        console.info("This feature is coming soon!")
        return

    # Compile the app in production mode.
    export(loglevel=loglevel)

    # Exit early if this is a dry run.
    if dry_run:
        return

    # Deploy the app.
    data = {"userId": config.username, "projectId": config.app_name}
    original_response = httpx.get(config.rxdeploy_url, params=data)
    response = original_response.json()
    frontend = response["frontend_resources_url"]
    backend = response["backend_resources_url"]

    # Upload the frontend and backend.
    with open(constants.ComponentName.FRONTEND.zip(), "rb") as f:
        httpx.put(frontend, data=f)  # type: ignore

    with open(constants.ComponentName.BACKEND.zip(), "rb") as f:
        httpx.put(backend, data=f)  # type: ignore


@cli.command()
def export(
    zipping: bool = typer.Option(
        True, "--no-zip", help="Disable zip for backend and frontend exports."
    ),
    frontend: bool = typer.Option(
        True, "--backend-only", help="Export only backend.", show_default=False
    ),
    backend: bool = typer.Option(
        True, "--frontend-only", help="Export only frontend.", show_default=False
    ),
    loglevel: constants.LogLevel = typer.Option(
        console._LOG_LEVEL, help="The log level to use."
    ),
):
    """Export the app to a zip file."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Show system info
    exec.output_system_info()

    # Check that the app is initialized.
    prerequisites.check_initialized(frontend=frontend)

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")

    if frontend:
        # Ensure module can be imported and app.compile() is called.
        prerequisites.get_app()
        # Set up .web directory and install frontend dependencies.
        build.setup_frontend(Path.cwd())

    # Export the app.
    build.export(
        backend=backend,
        frontend=frontend,
        zip=zipping,
        deploy_url=config.deploy_url,
    )

    # Post a telemetry event.
    telemetry.send("export")


@cli.command()
def login(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Authenticate with Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Check if the user is already logged in.
    # Token is the access token, a JWT token obtained from auth provider
    # after user completes authentication on web
    access_token = None
    # For initial hosting offering, it is by invitation only
    # The login page is enabled only after a valid invitation code is entered
    invitation_code = ""
    using_existing_token = False

    with contextlib.suppress(Exception):
        access_token, invitation_code = hosting.get_existing_access_token()
        using_existing_token = True
        console.debug("Existing token found, proceed to validate")

    # If not already logged in, open a browser window/tab to the login page.
    if not using_existing_token:
        access_token, invitation_code = hosting.authenticate_on_browser(invitation_code)

    if not access_token:
        console.error(
            f"Unable to fetch access token. Please try again or contact support."
        )
        raise typer.Exit(1)

    try:
        hosting.validate_token(access_token)
    except Exception as ex:
        console.error(f"Unable to validate token. Please try again or contact support.")
        raise typer.Exit(1) from ex

    if not using_existing_token:
        hosting.save_token_to_config(access_token, invitation_code)
        console.print("Successfully logged in.")
    else:
        console.print("You already logged in.")


@cli.command()
def logout(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Log out of access to Reflex hosting service."""
    console.set_log_level(loglevel)

    hosting.log_out_on_browser()
    console.debug("Deleting access token from config locally")
    hosting.delete_token_from_config()


db_cli = typer.Typer()


def _skip_compile():
    """Skip the compile step."""
    os.environ[constants.SKIP_COMPILE_ENV_VAR] = "yes"


@db_cli.command(name="init")
def db_init():
    """Create database schema and migration configuration."""
    # Check the database url.
    if config.db_url is None:
        console.error("db_url is not configured, cannot initialize.")
        return

    # Check the alembic config.
    if Path(constants.ALEMBIC_CONFIG).exists():
        console.error(
            "Database is already initialized. Use "
            "[bold]reflex db makemigrations[/bold] to create schema change "
            "scripts and [bold]reflex db migrate[/bold] to apply migrations "
            "to a new or existing database.",
        )
        return

    # Initialize the database.
    _skip_compile()
    prerequisites.get_app()
    model.Model.alembic_init()
    model.Model.migrate(autogenerate=True)


@db_cli.command()
def migrate():
    """Create or update database schema from migration scripts."""
    _skip_compile()
    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        return
    model.Model.migrate()
    prerequisites.check_schema_up_to_date()


@db_cli.command()
def makemigrations(
    message: str = typer.Option(
        None, help="Human readable identifier for the generated revision."
    ),
):
    """Create autogenerated alembic migration scripts."""
    _skip_compile()
    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        return
    with model.Model.get_db_engine().connect() as connection:
        try:
            model.Model.alembic_autogenerate(connection=connection, message=message)
        except CommandError as command_error:
            if "Target database is not up to date." not in str(command_error):
                raise
            console.error(
                f"{command_error} Run [bold]reflex db migrate[/bold] to update database."
            )


@cli.command()
def deploy(
    key: Optional[str] = typer.Option(
        None, "-k", "--deployment-key", help="The name of the deployment."
    ),
    app_name: str = typer.Option(
        config.app_name,
        "--app-name",
        help="The name of the App to deploy under.",
    ),
    regions: list[str] = typer.Option(
        list(),
        "-r",
        "--region",
        help="The regions to deploy to.",
    ),
    envs: list[str] = typer.Option(
        list(),
        "--env",
        help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option followed by the env name.",
    ),
    cpus: Optional[int] = typer.Option(None, help="The number of CPUs to allocate."),
    memory_mb: Optional[int] = typer.Option(
        None, help="The amount of memory to allocate."
    ),
    auto_start: Optional[bool] = typer.Option(
        True, help="Whether to auto start the instance."
    ),
    auto_stop: Optional[bool] = typer.Option(
        True, help="Whether to auto stop the instance."
    ),
    frontend_hostname: Optional[str] = typer.Option(
        None, "--frontend-hostname", help="The hostname of the frontend."
    ),
    interactive: Optional[bool] = typer.Option(
        True,
        help="Whether to list configuration options and ask for confirmation.",
    ),
    with_metrics: Optional[str] = typer.Option(
        None,
        help="Setting for metrics scraping for the deployment. Setup required in user code.",
    ),
    with_tracing: Optional[str] = typer.Option(
        None,
        help="Setting to export tracing for the deployment. Setup required in user code.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Deploy the app to the Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    if not interactive and not key:
        console.error("Please provide a deployment key when not in interactive mode.")
        raise typer.Exit(1)

    try:
        hosting.check_requirements_txt_exist()
    except Exception as ex:
        console.error(f"{constants.RequirementsTxt.FILE} required for deployment")
        raise typer.Exit(1) from ex

    # Check if we are set up.
    prerequisites.check_initialized(frontend=True)

    try:
        # Send a request to server to obtain necessary information
        # in preparation of a deployment. For example,
        # server can return confirmation of a particular deployment key,
        # is available, or suggest a new key, or return an existing deployment.
        # Some of these are used in the interactive mode.
        pre_deploy_response = hosting.prepare_deploy(
            app_name, key=key, frontend_hostname=frontend_hostname
        )
    except Exception as ex:
        console.error(f"Unable to prepare deployment due to: {ex}")
        raise typer.Exit(1) from ex

    # The app prefix should not change during the time of preparation
    app_prefix = pre_deploy_response.app_prefix
    overwrite_existing = False
    if not interactive:
        # in this case, the key was supplied for the pre_deploy call, at this point the reply is expected
        if not (reply := pre_deploy_response.reply):
            console.error(f"Unable to deploy at this name {key}.")
            raise typer.Exit(1)
        api_url = reply.api_url
        deploy_url = reply.deploy_url
    else:
        (
            key_candidate,
            api_url,
            deploy_url,
            overwrite_existing,
        ) = hosting.interactive_get_deployment_key_from_user_input(
            pre_deploy_response, app_name, frontend_hostname=frontend_hostname
        )
        if not key_candidate or not api_url or not deploy_url:
            console.error("Unable to find a suitable deployment key.")
            raise typer.Exit(1)

        # Now copy over the candidate to the key
        key = key_candidate

        # Then CP needs to know the user's location, which requires user permission
        region_input = console.ask(
            "Region to deploy to", default=regions[0] if regions else "sjc"
        )
        regions = regions or [region_input]

        # process the envs
        envs_finished = False
        env_key_prompt = "  Env name (enter to skip)"
        console.print("Environment variables ...")
        while not envs_finished:
            env_key = console.ask(env_key_prompt)
            env_key_prompt = "  env name (enter to finish)"
            if not env_key:
                envs_finished = True
                if envs:
                    console.print("Finished adding envs.")
                else:
                    console.print("No envs added. Continuing ...")
                break
            # If it possible to have empty values for env, so we do not check here
            env_value = console.ask("  env value")
            envs.append(f"{env_key}={env_value}")

    # Check the required params are valid
    console.debug(f"{key=}, {regions=}, {app_name=}, {app_prefix=}, {api_url}")
    if not key or not regions or not app_name or not app_prefix or not api_url:
        console.error("Please provide all the required parameters.")
        raise typer.Exit(1)

    processed_envs = hosting.process_envs(envs) if envs else None

    # Compile the app in production mode.
    config.api_url = api_url
    config.deploy_url = deploy_url
    try:
        export(frontend=True, backend=True, zipping=True, loglevel=loglevel)
    except ImportError as ie:
        console.error(
            f"Encountered ImportError, did you install all the dependencies? {ie}"
        )
        raise typer.Exit(1) from ie

    frontend_file_name = constants.ComponentName.FRONTEND.zip()
    backend_file_name = constants.ComponentName.BACKEND.zip()

    console.print("Uploading code and sending request ...")
    deploy_requested_at = datetime.now().astimezone()
    try:
        deploy_response = hosting.deploy(
            frontend_file_name=frontend_file_name,
            backend_file_name=backend_file_name,
            key=key,
            app_name=app_name,
            regions=regions,
            app_prefix=app_prefix,
            cpus=cpus,
            memory_mb=memory_mb,
            auto_start=auto_start,
            auto_stop=auto_stop,
            frontend_hostname=frontend_hostname,
            envs=processed_envs,
            with_metrics=with_metrics,
            with_tracing=with_tracing,
        )
    except Exception as ex:
        console.error(f"Unable to deploy due to: {ex}")
        with contextlib.suppress(Exception):
            hosting.clean_up()
        raise typer.Exit(1) from ex

    # Deployment will actually start when data plane reconciles this request
    console.debug(f"deploy_response: {deploy_response}")
    console.rule("[bold]Deploying production app.")
    console.print(
        "[bold]Deployment will start shortly. Closing this command now will not affect your deployment."
    )

    # It takes a few seconds for the deployment request to be picked up by server
    hosting.wait_for_server_to_pick_up_request()

    console.print("Waiting for server to report progress ...")
    # Display the key events such as build, deploy, etc
    asyncio.get_event_loop().run_until_complete(
        hosting.display_deploy_milestones(key, from_iso_timestamp=deploy_requested_at)
    )

    console.print("Waiting for the new deployment to come up")
    backend_up = frontend_up = False

    with console.status("Checking backend ..."):
        for _ in range(constants.Hosting.BACKEND_POLL_RETRIES):
            if backend_up := hosting.poll_backend(deploy_response.backend_url):
                break
            time.sleep(1)
    if not backend_up:
        console.print("Backend unreachable")
    else:
        console.print("Backend is up")

    with console.status("Checking frontend ..."):
        for _ in range(constants.Hosting.FRONTEND_POLL_RETRIES):
            if frontend_up := hosting.poll_frontend(deploy_response.frontend_url):
                break
            time.sleep(1)
    if not frontend_up:
        console.print("frontend is unreachable")
    else:
        console.print("frontend is up")

    hosting.clean_up()
    if frontend_up and backend_up:
        console.print(
            f"Your site [ {key} ] at {regions} is up: {deploy_response.frontend_url}"
        )
        return
    console.warn(
        "Your deployment is taking unusually long. Check back later on its status: `reflex deployments status`"
    )


deployments_cli = typer.Typer()


@deployments_cli.command(name="list")
def list_deployments(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
    as_json: bool = typer.Option(
        False, "-j", "--json", help="Whether to output the result in json format."
    ),
):
    """List all the hosted deployments of the authenticated user."""
    console.set_log_level(loglevel)
    try:
        deployments = hosting.list_deployments()
    except Exception as ex:
        console.error(f"Unable to list deployments due to: {ex}")
        raise typer.Exit(1) from ex

    if as_json:
        console.print(json.dumps(deployments))
        return
    if deployments:
        headers = list(deployments[0].keys())
        table = [list(deployment.values()) for deployment in deployments]
        console.print(tabulate(table, headers=headers))
    else:
        # If returned empty list, print the empty
        console.print(str(deployments))


@deployments_cli.command(name="delete")
def delete_deployment(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Delete a hosted instance."""
    console.set_log_level(loglevel)
    try:
        hosting.delete_deployment(key)
    except Exception as ex:
        console.error(f"Unable to delete deployment due to: {ex}")
        raise typer.Exit(1) from ex
    console.print(f"Successfully deleted [ {key} ].")


@deployments_cli.command(name="status")
def get_deployment_status(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Check the status of a deployment."""
    console.set_log_level(loglevel)

    try:
        console.print(f"Getting status for [ {key} ] ...\n")
        status = hosting.get_deployment_status(key)

        # TODO: refactor all these tabulate calls
        status.backend.updated_at = hosting.convert_to_local_time(
            status.backend.updated_at or "N/A"
        )
        backend_status = status.backend.dict(exclude_none=True)
        headers = list(backend_status.keys())
        table = list(backend_status.values())
        console.print(tabulate([table], headers=headers))
        # Add a new line in console
        console.print("\n")
        status.frontend.updated_at = hosting.convert_to_local_time(
            status.frontend.updated_at or "N/A"
        )
        frontend_status = status.frontend.dict(exclude_none=True)
        headers = list(frontend_status.keys())
        table = list(frontend_status.values())
        console.print(tabulate([table], headers=headers))
    except Exception as ex:
        console.error(f"Unable to get deployment status due to: {ex}")
        raise typer.Exit(1) from ex


@deployments_cli.command(name="logs")
def get_deployment_logs(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Get the logs for a deployment."""
    console.set_log_level(loglevel)
    console.print("Note: there is a few seconds delay for logs to be available.")
    try:
        asyncio.get_event_loop().run_until_complete(hosting.get_logs(key))
    except Exception as ex:
        console.error(f"Unable to get deployment logs due to: {ex}")
        raise typer.Exit(1) from ex


@deployments_cli.command(name="all-logs")
def get_deployment_all_logs(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Get the logs for a deployment."""
    console.set_log_level(loglevel)

    console.print("Note: there is a few seconds delay for logs to be available.")
    try:
        asyncio.run(hosting.get_logs(key, log_type=hosting.LogType.ALL_LOG))
    except Exception as ex:
        console.error(f"Unable to get deployment logs due to: {ex}")
        raise typer.Exit(1) from ex


@deployments_cli.command(name="deploy-logs")
def get_deployment_deploy_logs(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Get the logs for a deployment."""
    console.set_log_level(loglevel)

    console.print("Note: there is a few seconds delay for logs to be available.")
    try:
        # TODO: we need to pass in the from time stamp
        asyncio.run(hosting.get_logs(key, log_type=hosting.LogType.DEPLOY_LOG))
    except Exception as ex:
        console.error(f"Unable to get deployment logs due to: {ex}")
        raise typer.Exit(1) from ex


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(
    deployments_cli,
    name="deployments",
    help="Subcommands for managing the Deployments.",
)

if __name__ == "__main__":
    cli()
