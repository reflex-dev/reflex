"""Reflex CLI to create, run, and deploy apps."""

import os
import signal
import threading
from pathlib import Path

import httpx
import typer
from alembic.util.exc import CommandError

from reflex import constants, model
from reflex.config import get_config
from reflex.utils import build, console, exec, prerequisites, processes, telemetry

# Create the app.
cli = typer.Typer(add_completion=False)

# Get the config
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
        None, metavar="APP_NAME", help="The name of the app to be initialized."
    ),
    template: constants.Template = typer.Option(
        constants.Template.DEFAULT, help="The template to initialize the app with."
    ),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.INFO, help="The log level to use."
    ),
):
    """Initialize a new Reflex app in the current directory."""
    # Set the log level.
    console.set_log_level(loglevel)

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
        build.set_reflex_project_hash()
        telemetry.send("init", config.telemetry_enabled)
    else:
        telemetry.send("reinit", config.telemetry_enabled)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()

    # Finish initializing the app.
    console.success(f"Initialized {app_name}")


@cli.command()
def run(
    env: constants.Env = typer.Option(
        constants.Env.DEV, help="The environment to run the app in."
    ),
    frontend_only: bool = typer.Option(
        False, "frontend-only", help="Execute only frontend."
    ),
    backend_only: bool = typer.Option(
        False, "backend-only", help="Execute only backend."
    ),
    frontend_port: str = typer.Option(
        constants.FRONTEND_PORT,
        help="Specify a different frontend port.",
        metavar="PORT",
    ),
    backend_port: str = typer.Option(
        constants.BACKEND_PORT, help="Specify a different backend port.", metavar="PORT"
    ),
    backend_host: str = typer.Option(
        constants.BACKEND_HOST, help="Specify the backend host url.", metavar="URL"
    ),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.INFO, help="The log level to use."
    ),
):
    """Run the app in the current directory."""
    # Set the log level.
    console.set_log_level(loglevel)
    console.rule("[bold]Starting Reflex App")

    # Check which parts of the app to run.
    run_frontend = not backend_only
    run_backend = not frontend_only

    # Check that the app is initialized.
    prerequisites.check_initialized(frontend=run_frontend)

    # Get the app module.
    app = prerequisites.get_app()

    # Check the admin dashboard settings.
    prerequisites.check_admin_settings()

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
    telemetry.send(f"run-{env.value}", config.telemetry_enabled)

    # Run the frontend and backend.
    if run_frontend:
        setup_frontend(Path.cwd())
        frontend_port = processes.change_or_terminate_port(frontend_port, "frontend")
        threading.Thread(target=frontend_cmd, args=(Path.cwd(), frontend_port)).start()
    if run_backend:
        backend_port = processes.change_or_terminate_port(backend_port, "backend")
        threading.Thread(
            target=backend_cmd,
            args=(app.__name__, backend_host, backend_port),
        ).start()

    # Display custom message when there is a keyboard interrupt.
    signal.signal(signal.SIGINT, processes.catch_keyboard_interrupt)


@cli.command()
def deploy(dry_run: bool = typer.Option(False, help="Whether to run a dry run.")):
    """Deploy the app to the Reflex hosting service."""
    # Check if the deploy url is set.
    if config.rxdeploy_url is None:
        typer.echo("This feature is coming soon!")
        return

    # Compile the app in production mode.
    typer.echo("Compiling production app")
    export()

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
    with open(constants.FRONTEND_ZIP, "rb") as f:
        httpx.put(frontend, data=f)  # type: ignore

    with open(constants.BACKEND_ZIP, "rb") as f:
        httpx.put(backend, data=f)  # type: ignore


@cli.command()
def export(
    backend_only: bool = typer.Option(False, help="Export only backend."),
    frontend_only: bool = typer.Option(False, help="Export only frontend."),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.INFO, help="The log level to use."
    ),
):
    """Export the app to a zip file."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Check which parts of the app to run.
    export_frontend = not backend_only
    export_backend = not frontend_only

    # Check that the app is initialized.
    prerequisites.check_initialized(frontend=export_frontend)

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")

    if export_frontend:
        # Ensure module can be imported and app.compile() is called.
        prerequisites.get_app()
        # Set up .web directory and install frontend dependencies.
        build.setup_frontend(Path.cwd())

    # Export the app.
    build.export(
        backend=export_backend,
        frontend=export_frontend,
        deploy_url=config.deploy_url,
    )

    # Post a telemetry event.
    telemetry.send("export", config.telemetry_enabled)
    console.success(
        """App exported to[bold]backend.zip[/bold] and [bold]frontend.zip[bold]."""
    )


db_cli = typer.Typer()


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
    prerequisites.get_app()
    model.Model.alembic_init()
    model.Model.migrate(autogenerate=True)


@db_cli.command()
def migrate():
    """Create or update database schema from migration scripts."""
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


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")

if __name__ == "__main__":
    cli()
