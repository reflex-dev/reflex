"""Reflex CLI to create, run, and deploy apps."""

import asyncio
import atexit
import json
import os
import shutil
import tempfile
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from alembic.util.exc import CommandError
from tabulate import tabulate

from reflex import constants, model
from reflex.config import get_config
from reflex.utils import (
    build,
    console,
    dependency,
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


def _init(
    name: str,
    template: constants.Templates.Kind,
    loglevel: constants.LogLevel,
):
    """Initialize a new Reflex app in the given directory."""
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
def init(
    name: str = typer.Option(
        None, metavar="APP_NAME", help="The name of the app to initialize."
    ),
    template: constants.Templates.Kind = typer.Option(
        constants.Templates.Kind.BASE.value,
        help="The template to initialize the app with.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Initialize a new Reflex app in the current directory."""
    _init(name, template, loglevel)


def _run(
    env: constants.Env = constants.Env.DEV,
    frontend: bool = True,
    backend: bool = True,
    frontend_port: str = str(get_config().frontend_port),
    backend_port: str = str(get_config().backend_port),
    backend_host: str = config.backend_host,
    loglevel: constants.LogLevel = config.loglevel,
):
    """Run the app in the given directory."""
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

    # Reload the config to make sure the env vars are persistent.
    get_config(reload=True)

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
    _run(env, frontend, backend, frontend_port, backend_port, backend_host, loglevel)


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
    zip_dest_dir: str = typer.Option(
        os.getcwd(),
        help="The directory to export the zip files to.",
        show_default=False,
    ),
    upload_db_file: bool = typer.Option(
        False,
        help="Whether to exclude sqlite db files when exporting backend.",
        hidden=True,
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
        zip_dest_dir=zip_dest_dir,
        deploy_url=config.deploy_url,
        upload_db_file=upload_db_file,
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

    access_token, invitation_code = hosting.authenticated_token()
    if access_token:
        console.print("You already logged in.")
        return

    # If not already logged in, open a browser window/tab to the login page.
    access_token = hosting.authenticate_on_browser(invitation_code)

    if not access_token:
        console.error(f"Unable to authenticate. Please try again or contact support.")
        raise typer.Exit(1)

    console.print("Successfully logged in.")


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
    hosting.delete_token_from_config(include_invitation_code=True)


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
        hidden=True,
    ),
    regions: List[str] = typer.Option(
        list(),
        "-r",
        "--region",
        help="The regions to deploy to.",
    ),
    envs: List[str] = typer.Option(
        list(),
        "--env",
        help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option, e.g. --env k1=v2 --env k2=v2.",
    ),
    cpus: Optional[int] = typer.Option(
        None, help="The number of CPUs to allocate.", hidden=True
    ),
    memory_mb: Optional[int] = typer.Option(
        None, help="The amount of memory to allocate.", hidden=True
    ),
    auto_start: Optional[bool] = typer.Option(
        None,
        help="Whether to auto start the instance.",
        hidden=True,
    ),
    auto_stop: Optional[bool] = typer.Option(
        None,
        help="Whether to auto stop the instance.",
        hidden=True,
    ),
    frontend_hostname: Optional[str] = typer.Option(
        None,
        "--frontend-hostname",
        help="The hostname of the frontend.",
        hidden=True,
    ),
    interactive: Optional[bool] = typer.Option(
        True,
        help="Whether to list configuration options and ask for confirmation.",
    ),
    with_metrics: Optional[str] = typer.Option(
        None,
        help="Setting for metrics scraping for the deployment. Setup required in user code.",
        hidden=True,
    ),
    with_tracing: Optional[str] = typer.Option(
        None,
        help="Setting to export tracing for the deployment. Setup required in user code.",
        hidden=True,
    ),
    upload_db_file: bool = typer.Option(
        False,
        help="Whether to include local sqlite db files when uploading to hosting service.",
        hidden=True,
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Deploy the app to the Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    if not interactive and not key:
        console.error(
            "Please provide a name for the deployed instance when not in interactive mode."
        )
        raise typer.Exit(1)

    dependency.check_requirements()

    # Check if we are set up.
    prerequisites.check_initialized(frontend=True)
    enabled_regions = None
    try:
        # Send a request to server to obtain necessary information
        # in preparation of a deployment. For example,
        # server can return confirmation of a particular deployment key,
        # is available, or suggest a new key, or return an existing deployment.
        # Some of these are used in the interactive mode.
        pre_deploy_response = hosting.prepare_deploy(
            app_name, key=key, frontend_hostname=frontend_hostname
        )
        # Note: we likely won't need to fetch this twice
        if pre_deploy_response.enabled_regions is not None:
            enabled_regions = pre_deploy_response.enabled_regions

    except Exception as ex:
        console.error(f"Unable to prepare deployment")
        raise typer.Exit(1) from ex

    # The app prefix should not change during the time of preparation
    app_prefix = pre_deploy_response.app_prefix
    if not interactive:
        # in this case, the key was supplied for the pre_deploy call, at this point the reply is expected
        if (reply := pre_deploy_response.reply) is None:
            console.error(f"Unable to deploy at this name {key}.")
            raise typer.Exit(1)
        api_url = reply.api_url
        deploy_url = reply.deploy_url
    else:
        (
            key_candidate,
            api_url,
            deploy_url,
        ) = hosting.interactive_get_deployment_key_from_user_input(
            pre_deploy_response, app_name, frontend_hostname=frontend_hostname
        )
        if not key_candidate or not api_url or not deploy_url:
            console.error("Unable to find a suitable deployment key.")
            raise typer.Exit(1)

        # Now copy over the candidate to the key
        key = key_candidate

        # Then CP needs to know the user's location, which requires user permission
        while True:
            region_input = console.ask(
                "Region to deploy to. Enter to use default.",
                default=regions[0] if regions else "sjc",
            )

            if enabled_regions is None or region_input in enabled_regions:
                break
            else:
                console.warn(
                    f"{region_input} is not a valid region. Must be one of {enabled_regions}"
                )
                console.warn("Run `reflex deploymemts regions` to see details.")
        regions = regions or [region_input]

        # process the envs
        envs = hosting.interactive_prompt_for_envs()

    # Check the required params are valid
    console.debug(f"{key=}, {regions=}, {app_name=}, {app_prefix=}, {api_url}")
    if not key or not regions or not app_name or not app_prefix or not api_url:
        console.error("Please provide all the required parameters.")
        raise typer.Exit(1)
    # Note: if the user uses --no-interactive mode, there was no prepare_deploy call
    # so we do not check the regions until the call to hosting server

    processed_envs = hosting.process_envs(envs) if envs else None

    # Compile the app in production mode.
    config.api_url = api_url
    config.deploy_url = deploy_url
    tmp_dir = tempfile.mkdtemp()
    try:
        export(
            frontend=True,
            backend=True,
            zipping=True,
            zip_dest_dir=tmp_dir,
            loglevel=loglevel,
            upload_db_file=upload_db_file,
        )
    except ImportError as ie:
        console.error(
            f"Encountered ImportError, did you install all the dependencies? {ie}"
        )
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        raise typer.Exit(1) from ie
    except Exception as ex:
        console.error(f"Unable to export due to: {ex}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        raise typer.Exit(1) from ex

    frontend_file_name = constants.ComponentName.FRONTEND.zip()
    backend_file_name = constants.ComponentName.BACKEND.zip()

    console.print("Uploading code and sending request ...")
    deploy_requested_at = datetime.now().astimezone()
    try:
        deploy_response = hosting.deploy(
            frontend_file_name=frontend_file_name,
            backend_file_name=backend_file_name,
            export_dir=tmp_dir,
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
        raise typer.Exit(1) from ex
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

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
    server_report_deploy_success = asyncio.get_event_loop().run_until_complete(
        hosting.display_deploy_milestones(key, from_iso_timestamp=deploy_requested_at)
    )
    if not server_report_deploy_success:
        console.error("Hosting server reports failure.")
        console.error(
            f"Check the server logs using `reflex deployments build-logs {key}`"
        )
        raise typer.Exit(1)
    console.print("Waiting for the new deployment to come up")
    backend_up = frontend_up = False

    with console.status("Checking backend ..."):
        for _ in range(constants.Hosting.BACKEND_POLL_RETRIES):
            if backend_up := hosting.poll_backend(deploy_response.backend_url):
                break
            time.sleep(1)
    if not backend_up:
        console.print("Backend unreachable")

    with console.status("Checking frontend ..."):
        for _ in range(constants.Hosting.FRONTEND_POLL_RETRIES):
            if frontend_up := hosting.poll_frontend(deploy_response.frontend_url):
                break
            time.sleep(1)
    if not frontend_up:
        console.print("frontend is unreachable")

    if frontend_up and backend_up:
        console.print(
            f"Your site [ {key} ] at {regions} is up: {deploy_response.frontend_url}"
        )
        return
    console.warn(f"Your deployment is taking time.")
    console.warn(f"Check back later on its status: `reflex deployments status {key}`")
    console.warn(f"For logs: `reflex deployments logs {key}`")


@cli.command()
def demo(
    frontend_port: str = typer.Option(
        "3001", help="Specify a different frontend port."
    ),
    backend_port: str = typer.Option("8001", help="Specify a different backend port."),
):
    """Run the demo app."""
    # Open the demo app in a terminal.
    webbrowser.open("https://demo.reflex.run")

    # Later: open the demo app locally.
    # with tempfile.TemporaryDirectory() as tmp_dir:
    #     os.chdir(tmp_dir)
    #     _init(
    #         name="reflex_demo",
    #         template=constants.Templates.Kind.DEMO,
    #         loglevel=constants.LogLevel.DEBUG,
    #     )
    #     _run(
    #         frontend_port=frontend_port,
    #         backend_port=backend_port,
    #         loglevel=constants.LogLevel.DEBUG,
    #     )


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
        console.error(f"Unable to list deployments")
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
        console.error(f"Unable to delete deployment")
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
        console.error(f"Unable to get deployment status")
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
        console.error(f"Unable to get deployment logs")
        raise typer.Exit(1) from ex


@deployments_cli.command(name="build-logs")
def get_deployment_build_logs(
    key: str = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Get the logs for a deployment."""
    console.set_log_level(loglevel)

    console.print("Note: there is a few seconds delay for logs to be available.")
    try:
        # TODO: we need to find a way not to fetch logs
        # that match the deployed app name but not previously of a different owner
        # This should not happen often
        asyncio.run(hosting.get_logs(key, log_type=hosting.LogType.BUILD_LOG))
    except Exception as ex:
        console.error(f"Unable to get deployment logs")
        raise typer.Exit(1) from ex


@deployments_cli.command(name="regions")
def get_deployment_regions(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
    as_json: bool = typer.Option(
        False, "-j", "--json", help="Whether to output the result in json format."
    ),
):
    """List all the regions of the hosting service."""
    console.set_log_level(loglevel)
    list_regions_info = hosting.get_regions()
    if as_json:
        console.print(json.dumps(list_regions_info))
        return
    if list_regions_info:
        headers = list(list_regions_info[0].keys())
        table = [list(deployment.values()) for deployment in list_regions_info]
        console.print(tabulate(table, headers=headers))


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(
    deployments_cli,
    name="deployments",
    help="Subcommands for managing the Deployments.",
)

if __name__ == "__main__":
    cli()
