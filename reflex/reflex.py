"""Reflex CLI to create, run, and deploy apps."""

import atexit
import json
import os
import re
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from alembic.util.exc import CommandError
from tabulate import tabulate
from yaspin import yaspin

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
        constants.Templates.Kind.DEFAULT,
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
    """Authenticate with Reflex control plane."""
    # Set the log level.
    console.set_log_level(loglevel)

    # TODO: maybe do not need this
    # Check if feature is enabled:
    # if not hosting.is_set_up():
    #     return

    # Check if the user is already logged in.
    token = hosting.get_existing_access_token()
    using_existing_token = bool(token)
    if not token:
        # If not already logged in, open a browser window/tab to the login page.
        console.print(f"Opening {config.cp_web_url} ...")
        request_id = uuid.uuid4().hex
        if not webbrowser.open(f"{config.cp_web_url}?request={request_id}"):
            console.error(
                f"Unable to open the browser to authenticate. Please contact support."
            )
            raise typer.Exit(1)
        with yaspin(text="Waiting for authentication...", color="yellow"):
            for _ in range(constants.Hosting.WEB_AUTH_TIMEOUT):
                token = hosting.fetch_token(request_id)
                if token:
                    break
                time.sleep(1)
    if not token:
        console.error(f"Unable to authenticate. Please try again or contact support.")
        raise typer.Exit(1)
    if not hosting.validate_token(token):
        console.error("Access denied.")
        if using_existing_token and os.path.exists(constants.Hosting.HOSTING_JSON):
            hosting_config = {}
            try:
                with open(constants.Hosting.HOSTING_JSON, "r") as config_file:
                    hosting_config = json.load(config_file)
                    del hosting_config["access_token"]
            except Exception:
                # Best efforts removing invalid token is OK
                pass
        raise typer.Exit(1)

    hosting_config = {}

    if os.path.exists(constants.Hosting.HOSTING_JSON):
        try:
            with open(constants.Hosting.HOSTING_JSON, "r") as config_file:
                hosting_config = json.load(config_file)
        except Exception as ex:
            console.debug(f"Unable to parse the hosting config file due to: {ex}")
            console.warn("Config file is corrupted. Creating a new one.")

    hosting_config["access_token"] = token
    try:
        with open(constants.Hosting.HOSTING_JSON, "w") as config_file:
            json.dump(hosting_config, config_file)
    except Exception as ex:
        console.error(f"Unable to write to the hosting config file due to: {ex}")
        return
    if not using_existing_token:
        console.print("Successfully logged in.")
    else:
        console.print("You already logged in.")


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
    # TODO: make this in a list of choices
    regions: list[str] = typer.Option(
        list(),
        "-r",
        "--region",
        help="The regions to deploy to. For multiple regions, repeat this option followed by the region name.",
    ),
    envs: list[str] = typer.Option(
        list(),
        "--env",
        help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option followed by the env name.",
    ),
    # TODO: the VM types, cpus, mem should come from CP, since they are enums
    cpus: Optional[int] = typer.Option(
        None, help="The number of CPUs to allocate. List the available types here."
    ),
    memory_mb: Optional[int] = typer.Option(
        None, help="The amount of memory to allocate. List the available types here."
    ),
    auto_start: Optional[bool] = typer.Option(
        False, help="Whether to auto start the instance."
    ),
    auto_stop: Optional[bool] = typer.Option(
        False, help="Whether to auto stop the instance."
    ),
    non_interactive: Optional[bool] = typer.Option(
        False,
        "--non-interactive",
        help="Whether to list configuration options and ask for confirmation.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Deploy the app to the Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Check if the user is authenticated
    token = hosting.get_existing_access_token()
    if not token:
        console.error("Please authenticate using `reflex login` first.")
        raise typer.Exit(1)
    if not hosting.validate_token(token):
        console.error("Access denied, exiting.")
        raise typer.Exit(1)

    # Check if we are set up.
    # TODO: export will check again with frontend==True, refactor
    prerequisites.check_initialized(frontend=True)

    pre_launch_response = hosting.prepare_deploy(key, app_name)
    if not pre_launch_response:
        raise typer.Exit(1)

    # This should not change during the time of preparation
    app_prefix = pre_launch_response.app_prefix
    api_url = pre_launch_response.api_url
    if not non_interactive:
        key_candidate = api_url_candidate = None

        if pre_launch_response.existing_deployments_same_app_and_api_urls:
            # TODO: add another check to guard against CP returning a (None, None)
            key_candidate = (
                pre_launch_response.existing_deployments_same_app_and_api_urls[0][0]
            )
            api_url_candidate = (
                pre_launch_response.existing_deployments_same_app_and_api_urls[0][1]
            )
            # TODO: maybe keep it simple for now, since do not allow multiple deployments per app
            console.print(f"Overwrite deployment [ {key_candidate} ] ...")
        elif pre_launch_response.suggested_key_and_api_url:
            key_candidate = pre_launch_response.suggested_key_and_api_url[0]
            api_url_candidate = pre_launch_response.suggested_key_and_api_url[1]
            # This should not change during the time of preparation
            app_prefix = pre_launch_response.app_prefix
            # If user takes the suggestion, we will use the suggested key and proceed
            while key_input := console.ask(
                f"Name of deployment", default=key_candidate
            ):
                pre_launch_response = hosting.prepare_deploy(key_input, app_name)
                if pre_launch_response and pre_launch_response.api_url:
                    api_url_candidate = pre_launch_response.api_url
                    # This should not change during the time of preparation
                    app_prefix = pre_launch_response.app_prefix
                    break
                else:
                    console.error(
                        "Cannot deploy at this name, try picking a different name"
                    )
            key_candidate = key_input or key_candidate

        # We have pydantic validator to ensure key_candidate is provided
        if not key_candidate or not api_url_candidate:
            console.error("Unable to find a suitable deployment key.")
            raise typer.Exit(1)
        # Rename to make them more clear
        key = key_candidate
        api_url = api_url_candidate

        # TODO: let control plane suggest a region?
        # Then CP needs to know the user's location, might not be a good idea
        region_input = console.ask(
            "Region to deploy to", default=regions[0] if regions else "sjc"
        )
        regions = regions or [region_input]
        # process the envs
        envs_finished = False
        env_key_prompt = "Env name (enter to skip)"
        while not envs_finished:
            env_key = console.ask(env_key_prompt)
            env_key_prompt = "Env name (enter to finish)"
            if not env_key:
                envs_finished = True
                if envs:
                    console.print("Finished adding envs.")
                else:
                    console.print("No envs added. Continuing ...")
                break
            # If it possible to have empty values for env, so we do not check here
            env_value = console.ask("Env value")
            envs.append(f"{env_key}={env_value}")

    # Check the required params are valid
    console.debug(f"{key=}, {regions=}, {app_name=}, {app_prefix=}, {api_url=}")
    if not key or not regions or not app_name or not app_prefix or not api_url:
        console.error("Please provide all the required parameters.")
        raise typer.Exit(1)

    processed_envs = None
    if envs:
        # check format
        processed_envs = {}
        for env in envs:
            kv = env.split("=", maxsplit=1)
            if len(kv) != 2:
                console.error("Invalid env format: should be <key>=<value>.")
                raise typer.Exit(1)
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", kv[0]):
                console.error(
                    "Invalid env name: should start with a letter or underscore, followed by letters, digits, or underscores."
                )
                raise typer.Exit(1)
            processed_envs[kv[0]] = kv[1]

    # Compile the app in production mode.
    config.api_url = api_url
    try:
        export(frontend=True, backend=True, zipping=True, loglevel=loglevel)
    except ImportError as ie:
        # TODO: maybe show the missing dependency as well?
        console.error(f"Encountered ImportError, did you install all the dependencies?")
        raise typer.Exit(1) from ie
    # config.api_url = save_api_url

    frontend_file_name = constants.ComponentName.FRONTEND.zip()
    backend_file_name = constants.ComponentName.BACKEND.zip()

    console.print("Uploading code ...")
    deploy_response = hosting.deploy(
        frontend_file_name,
        backend_file_name,
        key,
        app_name,
        regions,
        app_prefix,
        cpus=cpus,
        memory_mb=memory_mb,
        auto_start=auto_start,
        auto_stop=auto_stop,
        envs=processed_envs,
    )
    if not deploy_response:
        hosting.clean_up()
        raise typer.Exit(1)
    console.print("Deployment will start shortly.")
    site_url = deploy_response.url
    if not site_url.startswith("https://"):
        site_url = f"https://{site_url}"

    backend_up = frontend_up = False
    # TODO: poll backend for status
    with yaspin(text="Checking backend ...") as sp:
        for _ in range(constants.Hosting.BACKEND_POLL_TIMEOUT):
            if backend_up := hosting.poll_backend(config.api_url):
                # TODO: what is a universal tick mark?
                sp.ok("✅ ")
                break
            time.sleep(1)
        if not backend_up:
            sp.fail("❌ ")

    # TODO: poll frontend for status
    with yaspin(text="Checking frontend ...") as sp:
        for _ in range(constants.Hosting.FRONTEND_POLL_TIMEOUT):
            if frontend_up := hosting.poll_frontend(site_url):
                # TODO: what is a universal tick mark?
                sp.ok("✅ ")
                break
            time.sleep(1)
        if not frontend_up:
            sp.fail("❌ ")

    # TODO: below is a bit hacky, refactor
    if not frontend_up or not backend_up:
        console.warn(
            "Your deployment is taking unusually long. Check back later using this command: reflex deployments status <deployment-name>"
        )
        hosting.clean_up()
    console.print(f"Your site <{key}> {regions} is up: {site_url}")


deployments_cli = typer.Typer()


@deployments_cli.command(name="list")
def list_deployments(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
    as_json: bool = typer.Option(
        False, help="Whether to output the result in json format."
    ),
):
    """List all the hosted instances for the specified app."""
    console.set_log_level(loglevel)

    if (deployments := hosting.list_deployments()) is None:
        raise typer.Exit(1)
    if as_json:
        console.print(json.dumps(deployments))
        return
    try:
        headers = list(deployments[0].dict().keys())
        table = [list(deployment.dict().values()) for deployment in deployments]
        console.print(tabulate(table, headers=headers))
    except Exception as ex:
        console.debug(f"Unable to tabulate the deployments due to: {ex}")
        console.print(str(deployments))


@deployments_cli.command(name="delete")
def delete_deployment(
    key: str,  # = typer.Argument(..., help="The name of the deployment."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Delete a hosted instance."""
    console.set_log_level(loglevel)

    if not hosting.delete_deployment(key):
        raise typer.Exit(1)
    console.print(f"Successfully deleted [ {key} ].")


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(
    deployments_cli,
    name="deployments",
    help="Subcommands for managing the Deployments.",
)

if __name__ == "__main__":
    cli()
