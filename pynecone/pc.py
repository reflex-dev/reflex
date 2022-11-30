"""Pynecone CLI to create, run, and deploy apps."""

import os

import requests
import typer

from pynecone import constants, utils
from pynecone.compiler import templates

# Create the app.
cli = typer.Typer()


@cli.command()
def version():
    """Get the Pynecone version."""
    utils.console.print(constants.VERSION)


@cli.command()
def init():
    """Initialize a new Pynecone app."""
    app_name = utils.get_default_app_name()
    with utils.console.status(f"[bold]Initializing {app_name}") as status:
        # Only create the app directory if it doesn't exist.
        if not os.path.exists(constants.CONFIG_FILE):
            # Create a configuration file.
            with open(constants.CONFIG_FILE, "w") as f:
                f.write(templates.PCCONFIG.format(app_name=app_name))
                utils.console.log(f"Initialize the app directory.")

            # Initialize the app directory.
            utils.cp(constants.APP_TEMPLATE_DIR, app_name)
            utils.mv(
                os.path.join(app_name, constants.APP_TEMPLATE_FILE),
                os.path.join(app_name, app_name + constants.PY_EXT),
            )
            utils.cp(constants.ASSETS_TEMPLATE_DIR, constants.APP_ASSETS_DIR)

        # Install bun if it isn't already installed.
        if not os.path.exists(utils.get_bun_path()):
            utils.console.log(f"Installing bun...")
            os.system(constants.INSTALL_BUN)

        # Initialize the web directory.
        utils.console.log(f"Initializing the web directory.")
        utils.rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.NODE_MODULES))
        utils.rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.PACKAGE_LOCK))
        utils.cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR)
        utils.console.log(f"[bold green]Finished Initializing: {app_name}")


@cli.command()
def run(
    env: constants.Env = constants.Env.DEV,
    frontend: bool = True,
    backend: bool = True,
):
    """Run the app.

    Args:
        env: The environment to run the app in.
        frontend: Whether to run the frontend.
        backend: Whether to run the backend.
    """
    utils.console.rule("[bold]Starting Pynecone App")
    app = utils.get_app()

    frontend_cmd = backend_cmd = None
    if env == constants.Env.DEV:
        frontend_cmd, backend_cmd = utils.run_frontend, utils.run_backend
    if env == constants.Env.PROD:
        frontend_cmd, backend_cmd = utils.run_frontend_prod, utils.run_backend_prod
    assert frontend_cmd and backend_cmd, "Invalid env"

    if frontend:
        frontend_cmd(app)
    if backend:
        backend_cmd(app)


@cli.command()
def deploy(dry_run: bool = False):
    """Deploy the app to the hosting service.

    Args:
        dry_run: Whether to run a dry run.
    """
    # Get the app config.
    config = utils.get_config()
    config.api_url = utils.get_production_backend_url()

    # Check if the deploy url is set.
    if config.deploy_url is None:
        typer.echo("This feature is coming soon!")
        typer.echo("Join our waitlist to be notified: https://pynecone.io/waitlist")
        return

    # Compile the app in production mode.
    typer.echo("Compiling production app")
    app = utils.get_app()
    utils.export_app(app)

    # Exit early if this is a dry run.
    if dry_run:
        return

    # Deploy the app.
    data = {"userId": config.username, "projectId": config.app_name}
    original_response = requests.get(config.deploy_url, params=data)
    response = original_response.json()
    print("response", response)
    frontend = response["frontend_resources_url"]
    backend = response["backend_resources_url"]

    # Upload the frontend and backend.
    with open(constants.FRONTEND_ZIP, "rb") as f:
        response = requests.put(frontend, data=f)

    with open(constants.BACKEND_ZIP, "rb") as f:
        response = requests.put(backend, data=f)


main = cli


if __name__ == "__main__":
    main()
