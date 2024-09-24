"""Reflex CLI to create, run, and deploy apps."""

from __future__ import annotations

import atexit
import os
import webbrowser
from pathlib import Path
from typing import List, Optional

import typer
import typer.core
from reflex_cli.deployments import deployments_cli
from reflex_cli.utils import dependency

from reflex import constants
from reflex.config import get_config
from reflex.custom_components.custom_components import custom_components_cli
from reflex.state import reset_disk_state_manager
from reflex.utils import console, redir, telemetry

# Disable typer+rich integration for help panels
typer.core.rich = False  # type: ignore

# Create the app.
try:
    cli = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
except TypeError:
    # Fallback for older typer versions.
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
    template: str | None = None,
    loglevel: constants.LogLevel = config.loglevel,
    ai: bool = False,
):
    """Initialize a new Reflex app in the given directory."""
    from reflex.utils import exec, prerequisites

    # Set the log level.
    console.set_log_level(loglevel)

    # Show system info
    exec.output_system_info()

    # Validate the app name.
    app_name = prerequisites.validate_app_name(name)
    console.rule(f"[bold]Initializing {app_name}")

    # Check prerequisites.
    prerequisites.check_latest_package_version(constants.Reflex.MODULE_NAME)
    prerequisites.initialize_reflex_user_directory()
    prerequisites.ensure_reflex_installation_id()

    # Set up the web project.
    prerequisites.initialize_frontend_dependencies()

    # Integrate with reflex.build.
    generation_hash = None
    if ai:
        if template is None:
            # If AI is requested and no template specified, redirect the user to reflex.build.
            generation_hash = redir.reflex_build_redirect()
        elif prerequisites.is_generation_hash(template):
            # Otherwise treat the template as a generation hash.
            generation_hash = template
        else:
            console.error(
                "Cannot use `--template` option with `--ai` option. Please remove `--template` option."
            )
            raise typer.Exit(2)
        template = constants.Templates.DEFAULT

    # Initialize the app.
    prerequisites.initialize_app(app_name, template)

    # If a reflex.build generation hash is available, download the code and apply it to the main module.
    if generation_hash:
        prerequisites.initialize_main_module_index_from_generation(
            app_name, generation_hash=generation_hash
        )

    # Migrate Pynecone projects to Reflex.
    prerequisites.migrate_to_reflex()

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
    template: str = typer.Option(
        None,
        help="The template to initialize the app with.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
    ai: bool = typer.Option(
        False,
        help="Use AI to create the initial template. Cannot be used with existing app or `--template` option.",
    ),
):
    """Initialize a new Reflex app in the current directory."""
    _init(name, template, loglevel, ai)


def _run(
    env: constants.Env = constants.Env.DEV,
    frontend: bool = True,
    backend: bool = True,
    frontend_port: str = str(config.frontend_port),
    backend_port: str = str(config.backend_port),
    backend_host: str = config.backend_host,
    loglevel: constants.LogLevel = config.loglevel,
):
    """Run the app in the given directory."""
    from reflex.utils import build, exec, prerequisites, processes

    # Set the log level.
    console.set_log_level(loglevel)

    # Set env mode in the environment
    os.environ[constants.ENV_MODE_ENV_VAR] = env.value

    # Show system info
    exec.output_system_info()

    # If no --frontend-only and no --backend-only, then turn on frontend and backend both
    if not frontend and not backend:
        frontend = True
        backend = True

    if not frontend and backend:
        _skip_compile()

    # Check that the app is initialized.
    if prerequisites.needs_reinit(frontend=frontend):
        _init(name=config.app_name, loglevel=loglevel)

    # Delete the states folder if it exists.
    reset_disk_state_manager()

    # Find the next available open port if applicable.
    if frontend:
        frontend_port = processes.handle_port(
            "frontend", frontend_port, str(constants.DefaultPorts.FRONTEND_PORT)
        )

    if backend:
        backend_port = processes.handle_port(
            "backend", backend_port, str(constants.DefaultPorts.BACKEND_PORT)
        )

    # Apply the new ports to the config.
    if frontend_port != str(config.frontend_port):
        config._set_persistent(frontend_port=frontend_port)
    if backend_port != str(config.backend_port):
        config._set_persistent(backend_port=backend_port)

    # Reload the config to make sure the env vars are persistent.
    get_config(reload=True)

    console.rule("[bold]Starting Reflex App")

    prerequisites.check_latest_package_version(constants.Reflex.MODULE_NAME)

    if frontend:
        # Get the app module.
        prerequisites.get_compiled_app()

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
        commands.append((frontend_cmd, Path.cwd(), frontend_port, backend))

    # In prod mode, run the backend on a separate thread.
    if backend and env == constants.Env.PROD:
        commands.append((backend_cmd, backend_host, backend_port))

    # Start the frontend and backend.
    with processes.run_concurrently_context(*commands):
        # In dev mode, run the backend on the main thread.
        if backend and env == constants.Env.DEV:
            backend_cmd(backend_host, int(backend_port))
            # The windows uvicorn bug workaround
            # https://github.com/reflex-dev/reflex/issues/2335
            if constants.IS_WINDOWS and exec.frontend_process:
                # Sends SIGTERM in windows
                exec.kill(exec.frontend_process.pid)


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
        config.loglevel, help="The log level to use."
    ),
):
    """Export the app to a zip file."""
    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    if prerequisites.needs_reinit(frontend=True):
        _init(name=config.app_name, loglevel=loglevel)

    export_utils.export(
        zipping=zipping,
        frontend=frontend,
        backend=backend,
        zip_dest_dir=zip_dest_dir,
        upload_db_file=upload_db_file,
        loglevel=loglevel,
    )


def _login() -> str:
    """Helper function to authenticate with Reflex hosting service."""
    from reflex_cli.utils import hosting

    access_token, invitation_code = hosting.authenticated_token()
    if access_token:
        console.print("You already logged in.")
        return access_token

    # If not already logged in, open a browser window/tab to the login page.
    access_token = hosting.authenticate_on_browser(invitation_code)

    if not access_token:
        console.error(f"Unable to authenticate. Please try again or contact support.")
        raise typer.Exit(1)

    console.print("Successfully logged in.")
    return access_token


@cli.command()
def login(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Authenticate with Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    _login()


@cli.command()
def logout(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Log out of access to Reflex hosting service."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    hosting.log_out_on_browser()
    console.debug("Deleting access token from config locally")
    hosting.delete_token_from_config(include_invitation_code=True)


db_cli = typer.Typer()
script_cli = typer.Typer()


def _skip_compile():
    """Skip the compile step."""
    os.environ[constants.SKIP_COMPILE_ENV_VAR] = "yes"


@db_cli.command(name="init")
def db_init():
    """Create database schema and migration configuration."""
    from reflex import model
    from reflex.utils import prerequisites

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
    prerequisites.get_compiled_app()
    model.Model.alembic_init()
    model.Model.migrate(autogenerate=True)


@db_cli.command()
def migrate():
    """Create or update database schema from migration scripts."""
    from reflex import model
    from reflex.utils import prerequisites

    # TODO see if we can use `get_app()` instead (no compile).  Would _skip_compile still be needed then?
    _skip_compile()
    prerequisites.get_compiled_app()
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
    from alembic.util.exc import CommandError

    from reflex import model
    from reflex.utils import prerequisites

    # TODO see if we can use `get_app()` instead (no compile).  Would _skip_compile still be needed then?
    _skip_compile()
    prerequisites.get_compiled_app()
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
        None,
        "-k",
        "--deployment-key",
        help="The name of the deployment. Domain name safe characters only.",
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
    interactive: bool = typer.Option(
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
    from reflex_cli import cli as hosting_cli

    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    # Set the log level.
    console.set_log_level(loglevel)

    # Only check requirements if interactive. There is user interaction for requirements update.
    if interactive:
        dependency.check_requirements()

    # Check if we are set up.
    if prerequisites.needs_reinit(frontend=True):
        _init(name=config.app_name, loglevel=loglevel)
    prerequisites.check_latest_package_version(constants.ReflexHostingCLI.MODULE_NAME)

    hosting_cli.deploy(
        app_name=app_name,
        export_fn=lambda zip_dest_dir,
        api_url,
        deploy_url,
        frontend,
        backend,
        zipping: export_utils.export(
            zip_dest_dir=zip_dest_dir,
            api_url=api_url,
            deploy_url=deploy_url,
            frontend=frontend,
            backend=backend,
            zipping=zipping,
            loglevel=loglevel,
            upload_db_file=upload_db_file,
        ),
        key=key,
        regions=regions,
        envs=envs,
        cpus=cpus,
        memory_mb=memory_mb,
        auto_start=auto_start,
        auto_stop=auto_stop,
        frontend_hostname=frontend_hostname,
        interactive=interactive,
        with_metrics=with_metrics,
        with_tracing=with_tracing,
        loglevel=loglevel.value,
    )


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


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(script_cli, name="script", help="Subcommands running helper scripts.")
cli.add_typer(
    deployments_cli,
    name="deployments",
    help="Subcommands for managing the Deployments.",
)
cli.add_typer(
    custom_components_cli,
    name="component",
    help="Subcommands for creating and publishing Custom Components.",
)

if __name__ == "__main__":
    cli()
