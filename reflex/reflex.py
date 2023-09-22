"""Reflex CLI to create, run, and deploy apps."""

import atexit
import json
import os
import webbrowser
from pathlib import Path
from typing import Optional

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
        console.print(constants.VERSION)
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
    template: constants.Template = typer.Option(
        constants.Template.DEFAULT, help="The template to initialize the app with."
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
    if not os.path.exists(constants.CONFIG_FILE):
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
        console.LOG_LEVEL, help="The log level to use."
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
        console.LOG_LEVEL, help="The log level to use."
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
        if not webbrowser.open(config.cp_web_url or ""):  # TODO: mypy complaints
            console.warn(
                f'Unable to open the browser. Please open the "{config.cp_web_url}" manually.'
            )
        token = input("Enter the token: ")
        if not token:
            console.error("Entered token is empty.")
            return

    if not hosting.validate_token(token):
        console.error("Access denied.")
        if using_existing_token and os.path.exists(constants.HOSTING_JSON):
            hosting_config = {}
            try:
                with open(constants.HOSTING_JSON, "r") as config_file:
                    hosting_config = json.load(config_file)
                    del hosting_config["access_token"]
            except Exception:
                # Best efforts removing invalid token is OK
                pass
        raise typer.Exit(1)

    hosting_config = {}

    if os.path.exists(constants.HOSTING_JSON):
        try:
            with open(constants.HOSTING_JSON, "r") as config_file:
                hosting_config = json.load(config_file)
        except Exception as ex:
            console.debug(f"Unable to parse the hosting config file due to: {ex}")
            console.warn("Config file is corrupted. Creating a new one.")

    hosting_config["access_token"] = token
    try:
        with open(constants.HOSTING_JSON, "w") as config_file:
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


apps_cli = typer.Typer()


@apps_cli.command()
def create(
    app_name: str,
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
):
    """Create a new Reflex App for hosting."""  # Set the log level.
    console.set_log_level(loglevel)

    # TODO: we might not need this below
    # # Check if the control plane url is set.
    # if not hosting.is_set_up():
    #     return

    # TODO: detect the app name from the current directory
    if not app_name:
        console.error("Please provide a name for the App.")
        return

    hosting.create_app(app_name)


@apps_cli.command(name="list")
def list_apps(
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Whether to output the result in json format."
    ),
):
    """List all the projects for the authenticated user."""
    console.set_log_level(loglevel)

    apps = hosting.list_apps()
    if apps is None:
        raise typer.Exit(1)
    if as_json:
        console.print(json.dumps(apps))
        return

    try:
        headers = list(apps[0].dict().keys())
        table = [list(app.dict().values()) for app in apps]
        console.print(tabulate(table, headers=headers))
    except Exception as ex:
        console.debug(f"Unable to tabulate the apps due to: {ex}")
        console.print(str(apps))


deployments_cli = typer.Typer()


@deployments_cli.command(name="list")
def list_deployments(
    app_name: Optional[str] = typer.Option(
        None,
        "--app-name",
        help="The name of the App to list instances for.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
    as_json: bool = typer.Option(
        False, help="Whether to output the result in json format."
    ),
):
    """List all the hosted instances for the specified app."""
    console.set_log_level(loglevel)

    deployments = hosting.list_deployments(app_name)
    if deployments is None:
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


# TODO: if CP machine has enough disk space or even relevant
# when the CP backend handler uses file-like object (not
# waiting for the whole file to be written to disk)
@deployments_cli.command()
def launch(
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
    # TODO: the VM types, cpus, mem should come from CP, since they are enums
    cpus: Optional[int] = typer.Option(
        None, help="The number of CPUs to allocate. List the available types here."
    ),
    memory_mb: Optional[int] = typer.Option(
        None, help="The amount of memory to allocate. List the available types here."
    ),
    vm_type: Optional[str] = typer.Option(
        None, help="The type of VM to use. List the available types here."
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
        console.LOG_LEVEL, help="The log level to use."
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
    # Do not compile yet
    _skip_compile()
    # No need to check frontend yet
    # TODO: export will check again with frontend==True, refactor
    prerequisites.check_initialized(frontend=True)

    pre_launch_response = hosting.prepare_launch(key, app_name)
    if not pre_launch_response:
        raise typer.Exit(1)

    if not non_interactive:
        # If a key is provided and is available, control plane returns it as the suggested deployment key
        key = pre_launch_response.suggested_deployment_key
        # User input takes precedence
        key = console.ask(f"Name of deployment", default=key) or key
        app_name = console.ask(f"Associated App", default=app_name) or app_name
        # TODO: let control plane suggest a region?
        # Then CP needs to know the user's location, might not be a good idea
        region_input = console.ask(
            "Regions to deploy to", default=regions[0] if regions else "sjc"
        )
        regions = regions or [region_input]

    # Check the required params are valid
    if (
        not key
        or not regions
        or not app_name
        or not (app_prefix := pre_launch_response.app_prefix)
    ):
        console.error("Please provide all the required parameters.")
        raise typer.Exit(1)

    save_api_url = config.api_url
    # Compile the app in production mode.
    config.api_url = pre_launch_response.api_url
    export(loglevel=loglevel)
    config.api_url = save_api_url

    frontend_file_name = constants.FRONTEND_ZIP
    backend_file_name = constants.BACKEND_ZIP

    launch_response = hosting.launch(
        frontend_file_name,
        backend_file_name,
        key,
        app_name,
        regions,
        app_prefix,
        vm_type=vm_type,
        cpus=cpus,
        memory_mb=memory_mb,
        auto_start=auto_start,
        auto_stop=auto_stop,
    )
    if not launch_response:
        raise typer.Exit(1)

    # TODO: below is a bit hacky, refactor
    site_url = launch_response.url
    if not site_url.startswith("https://"):
        site_url = f"https://{site_url}"
    console.print(f"Deploying <{key}> {regions} shortly to: {site_url}.")


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(
    apps_cli,
    name="apps",
    help="Subcommands for managing Apps for hosting.",
)
cli.add_typer(
    deployments_cli,
    name="deployments",
    help="Subcommands for managing the Deployments.",
)

if __name__ == "__main__":
    cli()
