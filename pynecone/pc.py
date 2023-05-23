"""Pynecone CLI to create, run, and deploy apps."""

import os
import platform
import threading
from pathlib import Path

import httpx
import typer

from pynecone import constants
from pynecone.config import get_config
from pynecone.utils import build, console, exec, prerequisites, processes, telemetry

# Create the app.
cli = typer.Typer()


@cli.command()
def version():
    """Get the Pynecone version."""
    console.print(constants.VERSION)


@cli.command()
def init(
    name: str = typer.Option(None, help="Name of the app to be initialized."),
    template: constants.Template = typer.Option(
        constants.Template.DEFAULT, help="Template to use for the app."
    ),
):
    """Initialize a new Pynecone app in the current directory."""
    app_name = prerequisites.get_default_app_name() if name is None else name

    # Make sure they don't name the app "pynecone".
    if app_name == constants.MODULE_NAME:
        console.print(
            f"[red]The app directory cannot be named [bold]{constants.MODULE_NAME}."
        )
        raise typer.Exit()

    console.rule(f"[bold]Initializing {app_name}")
    # Set up the web directory.
    prerequisites.validate_and_install_bun()
    prerequisites.initialize_web_directory()

    # Set up the app directory, only if the config doesn't exist.
    if not os.path.exists(constants.CONFIG_FILE):
        prerequisites.create_config(app_name)
        prerequisites.initialize_app_directory(app_name, template)
        build.set_pynecone_project_hash()
        telemetry.send("init", get_config().telemetry_enabled)
    else:
        build.set_pynecone_project_hash()
        telemetry.send("reinit", get_config().telemetry_enabled)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()
    # Finish initializing the app.
    console.log(f"[bold green]Finished Initializing: {app_name}")


@cli.command()
def run(
    env: constants.Env = typer.Option(
        constants.Env.DEV, help="The environment to run the app in."
    ),
    frontend: bool = typer.Option(
        False, "--frontend-only", help="Execute only frontend."
    ),
    backend: bool = typer.Option(False, "--backend-only", help="Execute only backend."),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.ERROR, help="The log level to use."
    ),
    port: str = typer.Option(None, help="Specify a different frontend port."),
    backend_port: str = typer.Option(None, help="Specify a different backend port."),
):
    """Run the app in the current directory."""
    if platform.system() == "Windows":
        console.print(
            "[yellow][WARNING] We strongly advise you to use Windows Subsystem for Linux (WSL) for optimal performance when using Pynecone. Due to compatibility issues with one of our dependencies, Bun, you may experience slower performance on Windows. By using WSL, you can expect to see a significant speed increase."
        )

    frontend_port = get_config().port if port is None else port
    backend_port = get_config().backend_port if backend_port is None else backend_port

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
            "[red]The app is not initialized. Run [bold]pc init[/bold] first."
        )
        raise typer.Exit()

    # Check that the template is up to date.
    if frontend and not prerequisites.is_latest_template():
        console.print(
            "[red]The base app template has updated. Run [bold]pc init[/bold] again."
        )
        raise typer.Exit()

    # Get the app module.
    console.rule("[bold]Starting Pynecone App")
    app = prerequisites.get_app()

    # Get the frontend and backend commands, based on the environment.
    frontend_cmd = backend_cmd = None
    if env == constants.Env.DEV:
        frontend_cmd, backend_cmd = exec.run_frontend, exec.run_backend
    if env == constants.Env.PROD:
        frontend_cmd, backend_cmd = exec.run_frontend_prod, exec.run_backend_prod
    assert frontend_cmd and backend_cmd, "Invalid env"

    # Post a telemetry event.
    telemetry.send(f"run-{env.value}", get_config().telemetry_enabled)

    # Run the frontend and backend.
    # try:
    if backend:
        threading.Thread(
            target=backend_cmd, args=(app.__name__, backend_port, loglevel)
        ).start()
    if frontend:
        threading.Thread(
            target=frontend_cmd, args=(app.app, Path.cwd(), frontend_port)
        ).start()


@cli.command()
def deploy(dry_run: bool = typer.Option(False, help="Whether to run a dry run.")):
    """Deploy the app to the Pynecone hosting service."""
    # Get the app config.
    config = get_config()
    config.api_url = prerequisites.get_production_backend_url()

    # Check if the deploy url is set.
    if config.pcdeploy_url is None:
        typer.echo("This feature is coming soon!")
        return

    # Compile the app in production mode.
    typer.echo("Compiling production app")
    app = prerequisites.get_app().app
    build.export_app(app, zip=True, deploy_url=config.deploy_url)

    # Exit early if this is a dry run.
    if dry_run:
        return

    # Deploy the app.
    data = {"userId": config.username, "projectId": config.app_name}
    original_response = httpx.get(config.pcdeploy_url, params=data)
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
    for_pc_deploy: bool = typer.Option(
        False,
        "--for-pc-deploy",
        help="Whether export the app for Pynecone Deploy Service.",
    ),
):
    """Export the app to a zip file."""
    config = get_config()

    if for_pc_deploy:
        # Get the app config and modify the api_url base on username and app_name.
        config.api_url = prerequisites.get_production_backend_url()

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")
    app = prerequisites.get_app().app
    build.export_app(
        app,
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


main = cli

if __name__ == "__main__":
    main()
