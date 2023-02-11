"""Pynecone CLI to create, run, and deploy apps."""

import os
from pathlib import Path

import httpx
import typer

from pynecone import constants, utils

# Create the app.
cli = typer.Typer()


@cli.command()
def version():
    """Get the Pynecone version."""
    utils.console.print(constants.VERSION)


@cli.command()
def init():
    """Initialize a new Pynecone app in the current directory."""
    app_name = utils.get_default_app_name()

    # Make sure they don't name the app "pynecone".
    if app_name == constants.MODULE_NAME:
        utils.console.print(
            f"[red]The app directory cannot be named [bold]{constants.MODULE_NAME}."
        )
        raise typer.Exit()

    with utils.console.status(f"[bold]Initializing {app_name}"):
        # Set up the web directory.
        utils.install_bun()
        utils.initialize_web_directory()

        # Set up the app directory, only if the config doesn't exist.
        if not os.path.exists(constants.CONFIG_FILE):
            utils.create_config(app_name)
            utils.initialize_app_directory(app_name)

        # Initialize the .gitignore.
        utils.initialize_gitignore()

        # Finish initializing the app.
        utils.console.log(f"[bold green]Finished Initializing: {app_name}")


@cli.command()
def run(
    env: constants.Env = typer.Option(
        constants.Env.DEV, help="The environment to run the app in."
    ),
    frontend: bool = typer.Option(
        True, "--no-frontend", help="Disable frontend execution."
    ),
    backend: bool = typer.Option(
        True, "--no-backend", help="Disable backend execution."
    ),
    loglevel: constants.LogLevel = typer.Option(
        constants.LogLevel.ERROR, help="The log level to use."
    ),
    port: str = typer.Option(None, help="Specify a different port."),
):
    """Run the app in the current directory."""
    frontend_port = utils.get_config().port if port is None else port
    backend_port = utils.get_api_port()

    # If something is running on the ports, ask the user if they want to kill or change it.
    if utils.is_process_on_port(frontend_port):
        frontend_port = utils.change_or_terminate_port(frontend_port, "frontend")

    if utils.is_process_on_port(backend_port):
        backend_port = utils.change_or_terminate_port(backend_port, "backend")

    # Check that the app is initialized.
    if frontend and not utils.is_initialized():
        utils.console.print(
            "[red]The app is not initialized. Run [bold]pc init[/bold] first."
        )
        raise typer.Exit()

    # Check that the template is up to date.
    if frontend and not utils.is_latest_template():
        utils.console.print(
            "[red]The base app template has updated. Run [bold]pc init[/bold] again."
        )
        raise typer.Exit()

    # Get the app module.
    utils.console.rule("[bold]Starting Pynecone App")
    app = utils.get_app()

    # Get the frontend and backend commands, based on the environment.
    frontend_cmd = backend_cmd = None
    if env == constants.Env.DEV:
        frontend_cmd, backend_cmd = utils.run_frontend, utils.run_backend
    if env == constants.Env.PROD:
        frontend_cmd, backend_cmd = utils.run_frontend_prod, utils.run_backend_prod
    assert frontend_cmd and backend_cmd, "Invalid env"

    # Run the frontend and backend.
    try:
        if frontend:
            frontend_cmd(app.app, Path.cwd(), frontend_port)
        if backend:
            backend_cmd(app.__name__, port=int(backend_port), loglevel=loglevel)
    finally:
        utils.kill_process_on_port(frontend_port)
        utils.kill_process_on_port(backend_port)


@cli.command()
def deploy(dry_run: bool = typer.Option(False, help="Whether to run a dry run.")):
    """Deploy the app to the Pynecone hosting service."""
    # Get the app config.
    config = utils.get_config()
    config.api_url = utils.get_production_backend_url()

    # Check if the deploy url is set.
    if config.deploy_url is None:
        typer.echo("This feature is coming soon!")
        return

    # Compile the app in production mode.
    typer.echo("Compiling production app")
    app = utils.get_app().app
    utils.export_app(app, zip=True)

    # Exit early if this is a dry run.
    if dry_run:
        return

    # Deploy the app.
    data = {"userId": config.username, "projectId": config.app_name}
    original_response = httpx.get(config.deploy_url, params=data)
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
    if for_pc_deploy:
        # Get the app config and modify the api_url base on username and app_name.
        config = utils.get_config()
        config.api_url = utils.get_production_backend_url()

    # Compile the app in production mode and export it.
    utils.console.rule("[bold]Compiling production app and preparing for export.")
    app = utils.get_app().app
    utils.export_app(app, backend=backend, frontend=frontend, zip=zipping)
    if zipping:
        utils.console.rule(
            """Backend & Frontend compiled. See [green bold]backend.zip[/green bold] 
            and [green bold]frontend.zip[/green bold]."""
        )
    else:
        utils.console.rule(
            """Backend & Frontend compiled. See [green bold]app[/green bold] 
            and [green bold].web/_static[/green bold] directories."""
        )


main = cli

if __name__ == "__main__":
    main()
