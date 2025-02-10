"""Reflex CLI to create, run, and deploy apps."""

from __future__ import annotations

import atexit
from pathlib import Path
from typing import List, Optional

import typer
import typer.core
from reflex_cli.v2.deployments import check_version, hosting_cli

from reflex import constants
from reflex.config import environment, get_config
from reflex.custom_components.custom_components import custom_components_cli
from reflex.state import reset_disk_state_manager
from reflex.utils import console, telemetry

# Disable typer+rich integration for help panels
typer.core.rich = None  # pyright: ignore [reportPrivateImportUsage]

# Create the app.
try:
    cli = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
except TypeError:
    # Fallback for older typer versions.
    cli = typer.Typer(add_completion=False)

SHOW_BUILT_WITH_REFLEX_INFO = "https://reflex.dev/docs/hosting/reflex-branding/"

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

    # Initialize the app.
    template = prerequisites.initialize_app(app_name, template, ai)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()

    # Initialize the requirements.txt.
    prerequisites.initialize_requirements_txt()

    template_msg = f" using the {template} template" if template else ""
    # Finish initializing the app.
    console.success(f"Initialized {app_name}{template_msg}")


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
    frontend_port: int = config.frontend_port,
    backend_port: int = config.backend_port,
    backend_host: str = config.backend_host,
    loglevel: constants.LogLevel = config.loglevel,
):
    """Run the app in the given directory."""
    from reflex.utils import build, exec, prerequisites, processes

    # Set the log level.
    console.set_log_level(loglevel)

    # Set env mode in the environment
    environment.REFLEX_ENV_MODE.set(env)

    # Show system info
    exec.output_system_info()

    # If no --frontend-only and no --backend-only, then turn on frontend and backend both
    frontend, backend = prerequisites.check_running_mode(frontend, backend)
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
            "frontend",
            frontend_port,
            constants.DefaultPorts.FRONTEND_PORT,
        )

    if backend:
        backend_port = processes.handle_port(
            "backend",
            backend_port,
            constants.DefaultPorts.BACKEND_PORT,
        )

    # Apply the new ports to the config.
    if frontend_port != config.frontend_port:
        config._set_persistent(frontend_port=frontend_port)
    if backend_port != config.backend_port:
        config._set_persistent(backend_port=backend_port)

    # Reload the config to make sure the env vars are persistent.
    get_config(reload=True)

    console.rule("[bold]Starting Reflex App")

    prerequisites.check_latest_package_version(constants.Reflex.MODULE_NAME)

    if frontend:
        if not config.show_built_with_reflex:
            # The sticky badge may be disabled at runtime for team/enterprise tiers.
            prerequisites.check_config_option_in_tier(
                option_name="show_built_with_reflex",
                allowed_tiers=["team", "enterprise"],
                fallback_value=True,
                help_link=SHOW_BUILT_WITH_REFLEX_INFO,
            )

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
    if not setup_frontend or not frontend_cmd or not backend_cmd:
        raise ValueError("Invalid env")

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
        commands.append(
            (
                backend_cmd,
                backend_host,
                backend_port,
                loglevel.subprocess_level(),
                frontend,
            )
        )

    # Start the frontend and backend.
    with processes.run_concurrently_context(*commands):
        # In dev mode, run the backend on the main thread.
        if backend and env == constants.Env.DEV:
            backend_cmd(
                backend_host, int(backend_port), loglevel.subprocess_level(), frontend
            )
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
        False,
        "--frontend-only",
        help="Execute only frontend.",
        envvar=environment.REFLEX_FRONTEND_ONLY.name,
    ),
    backend: bool = typer.Option(
        False,
        "--backend-only",
        help="Execute only backend.",
        envvar=environment.REFLEX_BACKEND_ONLY.name,
    ),
    frontend_port: int = typer.Option(
        config.frontend_port, help="Specify a different frontend port."
    ),
    backend_port: int = typer.Option(
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
    if frontend and backend:
        console.error("Cannot use both --frontend-only and --backend-only options.")
        raise typer.Exit(1)
    environment.REFLEX_BACKEND_ONLY.set(backend)
    environment.REFLEX_FRONTEND_ONLY.set(frontend)

    _run(env, frontend, backend, frontend_port, backend_port, backend_host, loglevel)


@cli.command()
def export(
    zipping: bool = typer.Option(
        True, "--no-zip", help="Disable zip for backend and frontend exports."
    ),
    frontend: bool = typer.Option(
        False,
        "--frontend-only",
        help="Export only frontend.",
        show_default=False,
        envvar=environment.REFLEX_FRONTEND_ONLY.name,
    ),
    backend: bool = typer.Option(
        False,
        "--backend-only",
        help="Export only backend.",
        show_default=False,
        envvar=environment.REFLEX_BACKEND_ONLY.name,
    ),
    zip_dest_dir: str = typer.Option(
        str(Path.cwd()),
        help="The directory to export the zip files to.",
        show_default=False,
    ),
    upload_db_file: bool = typer.Option(
        False,
        help="Whether to exclude sqlite db files when exporting backend.",
        hidden=True,
    ),
    env: constants.Env = typer.Option(
        constants.Env.PROD, help="The environment to export the app in."
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Export the app to a zip file."""
    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    frontend, backend = prerequisites.check_running_mode(frontend, backend)

    if prerequisites.needs_reinit(frontend=frontend or not backend):
        _init(name=config.app_name, loglevel=loglevel)

    if frontend and not config.show_built_with_reflex:
        # The sticky badge may be disabled on export for team/enterprise tiers.
        prerequisites.check_config_option_in_tier(
            option_name="show_built_with_reflex",
            allowed_tiers=["team", "enterprise"],
            fallback_value=False,
            help_link=SHOW_BUILT_WITH_REFLEX_INFO,
        )

    export_utils.export(
        zipping=zipping,
        frontend=frontend,
        backend=backend,
        zip_dest_dir=zip_dest_dir,
        upload_db_file=upload_db_file,
        env=env,
        loglevel=loglevel.subprocess_level(),
    )


@cli.command()
def login(loglevel: constants.LogLevel = typer.Option(config.loglevel)):
    """Authenticate with experimental Reflex hosting service."""
    from reflex_cli.v2 import cli as hosting_cli

    check_version()

    validated_info = hosting_cli.login()
    if validated_info is not None:
        _skip_compile()  # Allow running outside of an app dir
        telemetry.send("login", user_uuid=validated_info.get("user_id"))


@cli.command()
def logout(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Log out of access to Reflex hosting service."""
    from reflex_cli.v2.cli import logout

    check_version()

    logout(loglevel)  # pyright: ignore [reportArgumentType]


db_cli = typer.Typer()
script_cli = typer.Typer()


def _skip_compile():
    """Skip the compile step."""
    environment.REFLEX_SKIP_COMPILE.set(True)


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
    if environment.ALEMBIC_CONFIG.get().exists():
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
    app_name: str = typer.Option(
        config.app_name,
        "--app-name",
        help="The name of the App to deploy under.",
    ),
    app_id: str = typer.Option(
        None,
        "--app-id",
        help="The ID of the App to deploy over.",
    ),
    regions: List[str] = typer.Option(
        [],
        "-r",
        "--region",
        help="The regions to deploy to. `reflex cloud regions` For multiple envs, repeat this option, e.g. --region sjc --region iad",
    ),
    envs: List[str] = typer.Option(
        [],
        "--env",
        help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option, e.g. --env k1=v2 --env k2=v2.",
    ),
    vmtype: Optional[str] = typer.Option(
        None,
        "--vmtype",
        help="Vm type id. Run `reflex cloud vmtypes` to get options.",
    ),
    hostname: Optional[str] = typer.Option(
        None,
        "--hostname",
        help="The hostname of the frontend.",
    ),
    interactive: bool = typer.Option(
        True,
        help="Whether to list configuration options and ask for confirmation.",
    ),
    envfile: Optional[str] = typer.Option(
        None,
        "--envfile",
        help="The path to an env file to use. Will override any envs set manually.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="project id to deploy to",
    ),
    project_name: Optional[str] = typer.Option(
        None,
        "--project-name",
        help="The name of the project to deploy to.",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="token to use for auth",
    ),
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        help="path to the config file",
    ),
):
    """Deploy the app to the Reflex hosting service."""
    from reflex_cli.constants.base import LogLevel as HostingLogLevel
    from reflex_cli.utils import dependency
    from reflex_cli.v2 import cli as hosting_cli

    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    check_version()

    if not config.show_built_with_reflex:
        # The sticky badge may be disabled on deploy for pro/team/enterprise tiers.
        prerequisites.check_config_option_in_tier(
            option_name="show_built_with_reflex",
            allowed_tiers=["pro", "team", "enterprise"],
            fallback_value=True,
            help_link=SHOW_BUILT_WITH_REFLEX_INFO,
        )

    # Set the log level.
    console.set_log_level(loglevel)

    def convert_reflex_loglevel_to_reflex_cli_loglevel(
        loglevel: constants.LogLevel,
    ) -> HostingLogLevel:
        if loglevel == constants.LogLevel.DEBUG:
            return HostingLogLevel.DEBUG
        if loglevel == constants.LogLevel.INFO:
            return HostingLogLevel.INFO
        if loglevel == constants.LogLevel.WARNING:
            return HostingLogLevel.WARNING
        if loglevel == constants.LogLevel.ERROR:
            return HostingLogLevel.ERROR
        if loglevel == constants.LogLevel.CRITICAL:
            return HostingLogLevel.CRITICAL
        return HostingLogLevel.INFO

    # Only check requirements if interactive.
    # There is user interaction for requirements update.
    if interactive:
        dependency.check_requirements()

    # Check if we are set up.
    if prerequisites.needs_reinit(frontend=True):
        _init(name=config.app_name, loglevel=loglevel)
    prerequisites.check_latest_package_version(constants.ReflexHostingCLI.MODULE_NAME)

    hosting_cli.deploy(
        app_name=app_name,
        app_id=app_id,
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
            loglevel=loglevel.subprocess_level(),
        ),
        regions=regions,
        envs=envs,
        vmtype=vmtype,
        envfile=envfile,
        hostname=hostname,
        interactive=interactive,
        loglevel=convert_reflex_loglevel_to_reflex_cli_loglevel(loglevel),
        token=token,
        project=project,
        project_name=project_name,
        **({"config_path": config_path} if config_path is not None else {}),
    )


@cli.command()
def rename(
    new_name: str = typer.Argument(..., help="The new name for the app."),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Rename the app in the current directory."""
    from reflex.utils import prerequisites

    prerequisites.validate_app_name(new_name)
    prerequisites.rename_app(new_name, loglevel)


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(script_cli, name="script", help="Subcommands running helper scripts.")
cli.add_typer(
    hosting_cli,
    name="cloud",
    help="Subcommands for managing the reflex cloud.",
)
cli.add_typer(
    custom_components_cli,
    name="component",
    help="Subcommands for creating and publishing Custom Components.",
)

if __name__ == "__main__":
    cli()
