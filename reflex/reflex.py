"""Reflex CLI to create, run, and deploy apps."""

from __future__ import annotations

import atexit
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

import click
from reflex_cli.v2.deployments import hosting_cli

from reflex import constants
from reflex.config import get_config
from reflex.constants.base import LITERAL_ENV
from reflex.custom_components.custom_components import custom_components_cli
from reflex.environment import environment
from reflex.state import reset_disk_state_manager
from reflex.utils import console, redir, telemetry
from reflex.utils.exec import should_use_granian


def set_loglevel(ctx: click.Context, self: click.Parameter, value: str | None):
    """Set the log level.

    Args:
        ctx: The click context.
        self: The click command.
        value: The log level to set.
    """
    if value is not None:
        loglevel = constants.LogLevel.from_string(value)
        console.set_log_level(loglevel)


@click.group
@click.version_option(constants.Reflex.VERSION, message="%(version)s")
def cli():
    """Reflex CLI to create, run, and deploy apps."""


loglevel_option = click.option(
    "--loglevel",
    type=click.Choice(
        [loglevel.value for loglevel in constants.LogLevel],
        case_sensitive=False,
    ),
    is_eager=True,
    callback=set_loglevel,
    expose_value=False,
    help="The log level to use.",
)


def _init(
    name: str,
    template: str | None = None,
    ai: bool = False,
):
    """Initialize a new Reflex app in the given directory."""
    from reflex.utils import exec, prerequisites

    # Show system info
    exec.output_system_info()

    if ai:
        redir.reflex_build_redirect()
        return

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
    template = prerequisites.initialize_app(app_name, template)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()

    # Initialize the requirements.txt.
    needs_user_manual_update = prerequisites.initialize_requirements_txt()

    template_msg = f" using the {template} template" if template else ""
    # Finish initializing the app.
    console.success(
        f"Initialized {app_name}{template_msg}."
        + (
            f" Make sure to add {constants.RequirementsTxt.DEFAULTS_STUB + constants.Reflex.VERSION} to your requirements.txt or pyproject.toml file."
            if needs_user_manual_update
            else ""
        )
    )


@cli.command()
@loglevel_option
@click.option(
    "--name",
    metavar="APP_NAME",
    help="The name of the app to initialize.",
)
@click.option(
    "--template",
    help="The template to initialize the app with.",
)
@click.option(
    "--ai",
    is_flag=True,
    help="Use AI to create the initial template. Cannot be used with existing app or `--template` option.",
)
def init(
    name: str,
    template: str | None,
    ai: bool,
):
    """Initialize a new Reflex app in the current directory."""
    _init(name, template, ai)


def _run(
    env: constants.Env = constants.Env.DEV,
    frontend: bool = True,
    backend: bool = True,
    frontend_port: int | None = None,
    backend_port: int | None = None,
    backend_host: str | None = None,
):
    """Run the app in the given directory."""
    from reflex.utils import build, exec, prerequisites, processes

    config = get_config()

    backend_host = backend_host or config.backend_host

    # Set env mode in the environment
    environment.REFLEX_ENV_MODE.set(env)

    # Show system info
    exec.output_system_info()

    # If no --frontend-only and no --backend-only, then turn on frontend and backend both
    frontend, backend = prerequisites.check_running_mode(frontend, backend)
    if not frontend and backend:
        _skip_compile()

    prerequisites.assert_in_reflex_dir()

    # Check that the app is initialized.
    if frontend and prerequisites.needs_reinit():
        _init(name=config.app_name)

    # Delete the states folder if it exists.
    reset_disk_state_manager()

    # Find the next available open port if applicable.
    if frontend:
        auto_increment_frontend = not bool(frontend_port or config.frontend_port)
        frontend_port = processes.handle_port(
            "frontend",
            (
                frontend_port
                or config.frontend_port
                or constants.DefaultPorts.FRONTEND_PORT
            ),
            auto_increment=auto_increment_frontend,
        )

    if backend:
        auto_increment_backend = not bool(backend_port or config.backend_port)

        backend_port = processes.handle_port(
            "backend",
            (
                backend_port
                or config.backend_port
                or constants.DefaultPorts.BACKEND_PORT
            ),
            auto_increment=auto_increment_backend,
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

    # Get the app module.
    app_task = prerequisites.compile_or_validate_app
    args = (frontend,)
    kwargs = {
        "check_if_schema_up_to_date": True,
        "prerender_routes": env == constants.Env.PROD,
    }

    # Granian fails if the app is already imported.
    if should_use_granian():
        import concurrent.futures

        compile_future = concurrent.futures.ProcessPoolExecutor(max_workers=1).submit(
            app_task,
            *args,
            **kwargs,
        )
        compile_future.result()
    else:
        app_task(*args, **kwargs)

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
        msg = f"Invalid env: {env}. Must be DEV or PROD."
        raise ValueError(msg)

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
                config.loglevel.subprocess_level(),
                frontend,
            )
        )

    # Start the frontend and backend.
    with processes.run_concurrently_context(*commands):
        # In dev mode, run the backend on the main thread.
        if backend and backend_port and env == constants.Env.DEV:
            backend_cmd(
                backend_host,
                int(backend_port),
                config.loglevel.subprocess_level(),
                frontend,
            )
            # The windows uvicorn bug workaround
            # https://github.com/reflex-dev/reflex/issues/2335
            if constants.IS_WINDOWS and exec.frontend_process:
                # Sends SIGTERM in windows
                exec.kill(exec.frontend_process.pid)


@cli.command()
@loglevel_option
@click.option(
    "--env",
    type=click.Choice([e.value for e in constants.Env], case_sensitive=False),
    default=constants.Env.DEV.value,
    help="The environment to run the app in.",
)
@click.option(
    "--frontend-only",
    is_flag=True,
    show_default=False,
    help="Execute only frontend.",
    envvar=environment.REFLEX_FRONTEND_ONLY.name,
)
@click.option(
    "--backend-only",
    is_flag=True,
    show_default=False,
    help="Execute only backend.",
    envvar=environment.REFLEX_BACKEND_ONLY.name,
)
@click.option(
    "--frontend-port",
    type=int,
    help="Specify a different frontend port.",
    envvar=environment.REFLEX_FRONTEND_PORT.name,
)
@click.option(
    "--backend-port",
    type=int,
    help="Specify a different backend port.",
    envvar=environment.REFLEX_BACKEND_PORT.name,
)
@click.option(
    "--backend-host",
    help="Specify the backend host.",
)
def run(
    env: LITERAL_ENV,
    frontend_only: bool,
    backend_only: bool,
    frontend_port: int | None,
    backend_port: int | None,
    backend_host: str | None,
):
    """Run the app in the current directory."""
    if frontend_only and backend_only:
        console.error("Cannot use both --frontend-only and --backend-only options.")
        raise click.exceptions.Exit(1)

    config = get_config()

    frontend_port = frontend_port or config.frontend_port
    backend_port = backend_port or config.backend_port
    backend_host = backend_host or config.backend_host

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.RUN)
    environment.REFLEX_BACKEND_ONLY.set(backend_only)
    environment.REFLEX_FRONTEND_ONLY.set(frontend_only)

    _run(
        constants.Env.DEV if env == constants.Env.DEV else constants.Env.PROD,
        frontend_only,
        backend_only,
        frontend_port,
        backend_port,
        backend_host,
    )


@cli.command()
@loglevel_option
@click.option(
    "--dry",
    is_flag=True,
    default=False,
    help="Run the command without making any changes.",
)
def compile(dry: bool):
    """Compile the app in the current directory."""
    import time

    from reflex.utils import prerequisites

    # Check the app.
    if prerequisites.needs_reinit():
        _init(name=get_config().app_name)
    get_config(reload=True)
    starting_time = time.monotonic()
    prerequisites.compile_app(dry_run=dry)
    elapsed_time = time.monotonic() - starting_time
    console.success(f"App compiled successfully in {elapsed_time:.3f} seconds.")


@cli.command()
@loglevel_option
@click.option(
    "--zip/--no-zip",
    default=True,
    is_flag=True,
    help="Whether to zip the backend and frontend exports.",
)
@click.option(
    "--frontend-only",
    is_flag=True,
    show_default=False,
    envvar=environment.REFLEX_FRONTEND_ONLY.name,
    help="Export only frontend.",
)
@click.option(
    "--backend-only",
    is_flag=True,
    show_default=False,
    envvar=environment.REFLEX_BACKEND_ONLY.name,
    help="Export only backend.",
)
@click.option(
    "--zip-dest-dir",
    default=str(Path.cwd()),
    help="The directory to export the zip files to.",
    show_default=False,
)
@click.option(
    "--upload-db-file",
    is_flag=True,
    help="Whether to exclude sqlite db files when exporting backend.",
    hidden=True,
)
@click.option(
    "--env",
    type=click.Choice([e.value for e in constants.Env], case_sensitive=False),
    default=constants.Env.PROD.value,
    help="The environment to export the app in.",
)
def export(
    zip: bool,
    frontend_only: bool,
    backend_only: bool,
    zip_dest_dir: str,
    upload_db_file: bool,
    env: LITERAL_ENV,
):
    """Export the app to a zip file."""
    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.EXPORT)

    should_frontend_run, should_backend_run = prerequisites.check_running_mode(
        frontend_only, backend_only
    )

    config = get_config()

    prerequisites.assert_in_reflex_dir()

    if should_frontend_run and prerequisites.needs_reinit():
        _init(name=config.app_name)

    export_utils.export(
        zipping=zip,
        frontend=should_frontend_run,
        backend=should_backend_run,
        zip_dest_dir=zip_dest_dir,
        upload_db_file=upload_db_file,
        env=constants.Env.DEV if env == constants.Env.DEV else constants.Env.PROD,
        loglevel=config.loglevel.subprocess_level(),
    )


@cli.command()
@loglevel_option
def login():
    """Authenticate with experimental Reflex hosting service."""
    from reflex_cli.v2 import cli as hosting_cli
    from reflex_cli.v2.deployments import check_version

    check_version()

    validated_info = hosting_cli.login()
    if validated_info is not None:
        _skip_compile()  # Allow running outside of an app dir
        telemetry.send("login", user_uuid=validated_info.get("user_id"))


@cli.command()
@loglevel_option
def logout():
    """Log out of access to Reflex hosting service."""
    from reflex_cli.v2.cli import logout
    from reflex_cli.v2.deployments import check_version

    check_version()

    logout(_convert_reflex_loglevel_to_reflex_cli_loglevel(get_config().loglevel))


@click.group
def db_cli():
    """Subcommands for managing the database schema."""


@click.group
def script_cli():
    """Subcommands for running helper scripts."""


def _skip_compile():
    """Skip the compile step."""
    environment.REFLEX_SKIP_COMPILE.set(True)


@db_cli.command(name="init")
def db_init():
    """Create database schema and migration configuration."""
    from reflex import model
    from reflex.utils import prerequisites

    config = get_config()

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

    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        return
    model.Model.migrate()
    prerequisites.check_schema_up_to_date()


@db_cli.command()
def status():
    """Check the status of the database schema."""
    from reflex.model import Model, format_revision
    from reflex.utils import prerequisites

    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        console.info(
            "Database is not initialized. Run [bold]reflex db init[/bold] to initialize."
        )
        return

    # Run alembic check command and display output
    import reflex.config

    config = reflex.config.get_config()
    console.print(f"[bold]\\[{config.db_url}][/bold]")

    # Get migration history using Model method
    current_rev, revisions = Model.get_migration_history()
    if current_rev is None and not revisions:
        return

    current_reached_ref = [current_rev is None]

    # Show migration history in chronological order
    console.print("<base>")
    for rev in revisions:
        # Format and print the revision
        console.print(format_revision(rev, current_rev, current_reached_ref))


@db_cli.command()
@click.option(
    "--message",
    help="Human readable identifier for the generated revision.",
)
def makemigrations(message: str | None):
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
@loglevel_option
@click.option(
    "--app-name",
    help="The name of the app to deploy.",
)
@click.option(
    "--app-id",
    help="The ID of the app to deploy.",
)
@click.option(
    "-r",
    "--region",
    multiple=True,
    help="The regions to deploy to. `reflex cloud regions` For multiple envs, repeat this option, e.g. --region sjc --region iad",
)
@click.option(
    "--env",
    multiple=True,
    help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option, e.g. --env k1=v2 --env k2=v2.",
)
@click.option(
    "--vmtype",
    help="Vm type id. Run `reflex cloud vmtypes` to get options.",
)
@click.option(
    "--hostname",
    help="The hostname of the frontend.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
@click.option(
    "--envfile",
    help="The path to an env file to use. Will override any envs set manually.",
)
@click.option(
    "--project",
    help="project id to deploy to",
)
@click.option(
    "--project-name",
    help="The name of the project to deploy to.",
)
@click.option(
    "--token",
    help="token to use for auth",
)
@click.option(
    "--config-path",
    "--config",
    help="path to the config file",
)
def deploy(
    app_name: str | None,
    app_id: str | None,
    region: tuple[str, ...],
    env: tuple[str],
    vmtype: str | None,
    hostname: str | None,
    interactive: bool,
    envfile: str | None,
    project: str | None,
    project_name: str | None,
    token: str | None,
    config_path: str | None,
):
    """Deploy the app to the Reflex hosting service."""
    from reflex_cli.utils import dependency
    from reflex_cli.v2 import cli as hosting_cli
    from reflex_cli.v2.deployments import check_version

    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites

    config = get_config()

    app_name = app_name or config.app_name

    check_version()

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.DEPLOY)

    # Only check requirements if interactive.
    # There is user interaction for requirements update.
    if interactive:
        dependency.check_requirements()

    prerequisites.assert_in_reflex_dir()

    # Check if we are set up.
    if prerequisites.needs_reinit():
        _init(name=config.app_name)
    prerequisites.check_latest_package_version(constants.ReflexHostingCLI.MODULE_NAME)

    hosting_cli.deploy(
        app_name=app_name,
        app_id=app_id,
        export_fn=(
            lambda zip_dest_dir,
            api_url,
            deploy_url,
            frontend,
            backend,
            upload_db,
            zipping: export_utils.export(
                zip_dest_dir=zip_dest_dir,
                api_url=api_url,
                deploy_url=deploy_url,
                frontend=frontend,
                backend=backend,
                zipping=zipping,
                loglevel=config.loglevel.subprocess_level(),
                upload_db_file=upload_db,
            )
        ),
        regions=list(region),
        envs=list(env),
        vmtype=vmtype,
        envfile=envfile,
        hostname=hostname,
        interactive=interactive,
        loglevel=_convert_reflex_loglevel_to_reflex_cli_loglevel(config.loglevel),
        token=token,
        project=project,
        project_name=project_name,
        **({"config_path": config_path} if config_path is not None else {}),
    )


@cli.command()
@loglevel_option
@click.argument("new_name")
def rename(new_name: str):
    """Rename the app in the current directory."""
    from reflex.utils import prerequisites

    prerequisites.validate_app_name(new_name)
    prerequisites.rename_app(new_name, get_config().loglevel)


if TYPE_CHECKING:
    from reflex_cli.constants.base import LogLevel as HostingLogLevel


def _convert_reflex_loglevel_to_reflex_cli_loglevel(
    loglevel: constants.LogLevel,
) -> HostingLogLevel:
    """Convert a Reflex log level to a Reflex CLI log level.

    Args:
        loglevel: The Reflex log level to convert.

    Returns:
        The converted Reflex CLI log level.
    """
    from reflex_cli.constants.base import LogLevel as HostingLogLevel

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


if find_spec("typer") and find_spec("typer.main"):
    import typer  # pyright: ignore[reportMissingImports]

    if isinstance(hosting_cli, typer.Typer):
        hosting_cli_command = typer.main.get_command(hosting_cli)
    else:
        hosting_cli_command = hosting_cli
else:
    hosting_cli_command = hosting_cli

cli.add_command(hosting_cli_command, name="cloud")
cli.add_command(db_cli, name="db")
cli.add_command(script_cli, name="script")
cli.add_command(custom_components_cli, name="component")

if __name__ == "__main__":
    cli()
