"""Reflex CLI to create, run, and deploy apps."""

import os
import platform
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
cli = typer.Typer()


@cli.command()
def version():
    """Get the Reflex version."""
    console.print(constants.VERSION)


@cli.command()
def init(
    name: str = typer.Option(None, help="Name of the app to be initialized."),
    template: constants.Template = typer.Option(
        constants.Template.DEFAULT, help="Template to use for the app."
    ),
):
    """Initialize a new Reflex app in the current directory."""
    app_name = prerequisites.get_default_app_name() if name is None else name

    # Make sure they don't name the app "reflex".
    if app_name == constants.MODULE_NAME:
        console.print(
            f"[red]The app directory cannot be named [bold]{constants.MODULE_NAME}."
        )
        raise typer.Exit()

    console.rule(f"[bold]Initializing {app_name}")
    # Set up the web directory.
    prerequisites.validate_and_install_bun()
    prerequisites.initialize_web_directory()

    # Migrate Pynecone projects to Reflex.
    prerequisites.migrate_to_reflex()

    # Set up the app directory, only if the config doesn't exist.
    if not os.path.exists(constants.CONFIG_FILE):
        prerequisites.create_config(app_name)
        prerequisites.initialize_app_directory(app_name, template)
        build.set_reflex_project_hash()
        telemetry.send("init", get_config().telemetry_enabled)
    else:
        build.set_reflex_project_hash()
        telemetry.send("reinit", get_config().telemetry_enabled)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()
    # Finish initializing the app.
    console.log(f"[bold green]Finished Initializing: {app_name}")


@cli.command()
def run(
    env: constants.Env = typer.Option(
        get_config().env, help="The environment to run the app in."
    ),
    frontend: bool = typer.Option(
        False, "--frontend-only", help="Execute only frontend."
    ),
    backend: bool = typer.Option(False, "--backend-only", help="Execute only backend."),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.ERROR, help="The log level to use."
    ),
    frontend_port: str = typer.Option(None, help="Specify a different frontend port."),
    backend_port: str = typer.Option(None, help="Specify a different backend port."),
    backend_host: str = typer.Option(None, help="Specify the backend host."),
):
    """Run the app in the current directory."""
    if platform.system() == "Windows":
        console.print(
            "[yellow][WARNING] We strongly advise you to use Windows Subsystem for Linux (WSL) for optimal performance when using Reflex. Due to compatibility issues with one of our dependencies, Bun, you may experience slower performance on Windows. By using WSL, you can expect to see a significant speed increase."
        )
    # Set ports as os env variables to take precedence over config and
    # .env variables(if override_os_envs flag in config is set to False).
    build.set_os_env(
        frontend_port=frontend_port,
        backend_port=backend_port,
        backend_host=backend_host,
    )

    frontend_port = (
        get_config().frontend_port if frontend_port is None else frontend_port
    )
    backend_port = get_config().backend_port if backend_port is None else backend_port
    backend_host = get_config().backend_host if backend_host is None else backend_host

    # If no --frontend-only and no --backend-only, then turn on frontend and backend both
    if not frontend and not backend:
        frontend = True
        backend = True

    # If something is running on the ports, ask the user if they want to kill or change it.
    if frontend and processes.is_process_on_port(frontend_port):
        frontend_port = processes.change_or_terminate_port(frontend_port, "frontend")

    if backend and processes.is_process_on_port(backend_port):
        backend_port = processes.change_or_terminate_port(backend_port, "backend")

    # Check that the app is initialized.
    if frontend and not prerequisites.is_initialized():
        console.print(
            "[red]The app is not initialized. Run [bold]reflex init[/bold] first."
        )
        raise typer.Exit()

    # Check that the template is up to date.
    if frontend and not prerequisites.is_latest_template():
        console.print(
            "[red]The base app template has updated. Run [bold]reflex init[/bold] again."
        )
        raise typer.Exit()

    # Get the app module.
    console.rule("[bold]Starting Reflex App")
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
    telemetry.send(f"run-{env.value}", get_config().telemetry_enabled)

    # Run the frontend and backend.
    if frontend:
        setup_frontend(Path.cwd(), loglevel)
        threading.Thread(
            target=frontend_cmd, args=(Path.cwd(), frontend_port, loglevel)
        ).start()
    if backend:
        threading.Thread(
            target=backend_cmd,
            args=(app.__name__, backend_host, backend_port, loglevel),
        ).start()

    # Display custom message when there is a keyboard interrupt.
    signal.signal(signal.SIGINT, processes.catch_keyboard_interrupt)


@cli.command()
def deploy(dry_run: bool = typer.Option(False, help="Whether to run a dry run.")):
    """Deploy the app to the Reflex hosting service."""
    # Get the app config.
    config = get_config()
    config.api_url = prerequisites.get_production_backend_url()

    # Check if the deploy url is set.
    if config.rxdeploy_url is None:
        typer.echo("This feature is coming soon!")
        return

    # Compile the app in production mode.
    typer.echo("Compiling production app")
    export(for_reflex_deploy=True)

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
    zipping: bool = typer.Option(
        True, "--no-zip", help="Disable zip for backend and frontend exports."
    ),
    frontend: bool = typer.Option(
        True, "--backend-only", help="Export only backend.", show_default=False
    ),
    backend: bool = typer.Option(
        True, "--frontend-only", help="Export only frontend.", show_default=False
    ),
    for_reflex_deploy: bool = typer.Option(
        False,
        "--for-reflex-deploy",
        help="Whether export the app for Reflex Deploy Service.",
    ),
):
    """Export the app to a zip file."""
    config = get_config()

    if for_reflex_deploy:
        # Get the app config and modify the api_url base on username and app_name.
        config.api_url = prerequisites.get_production_backend_url()

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")

    if frontend:
        # ensure module can be imported and app.compile() is called
        prerequisites.get_app()
        # set up .web directory and install frontend dependencies
        build.setup_frontend(Path.cwd())

    build.export_app(
        backend=backend,
        frontend=frontend,
        zip=zipping,
        deploy_url=config.deploy_url,
    )

    # Post a telemetry event.
    telemetry.send("export", get_config().telemetry_enabled)

    if zipping:
        console.rule(
            """Backend & Frontend compiled. See [green bold]backend.zip[/green bold]
            and [green bold]frontend.zip[/green bold]."""
        )
    else:
        console.rule(
            """Backend & Frontend compiled. See [green bold]app[/green bold]
            and [green bold].web/_static[/green bold] directories."""
        )


db_cli = typer.Typer()


@db_cli.command(name="init")
def db_init():
    """Create database schema and migration configuration."""
    if get_config().db_url is None:
        console.print("[red]db_url is not configured, cannot initialize.")
    if Path(constants.ALEMBIC_CONFIG).exists():
        console.print(
            "[red]Database is already initialized. Use "
            "[bold]reflex db makemigrations[/bold] to create schema change "
            "scripts and [bold]reflex db migrate[/bold] to apply migrations "
            "to a new or existing database.",
        )
        return
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
            console.print(
                f"[red]{command_error} Run [bold]reflex db migrate[/bold] to update database."
            )


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema")
main = cli

if __name__ == "__main__":
    main()
