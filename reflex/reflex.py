"""Reflex CLI to create, run, and deploy apps."""

import atexit
import json
import os
import webbrowser
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import requests
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

    # Check if feature is enabled:
    if not hosting.is_set_up():
        return

    # Check if the user is already logged in.
    token = hosting.get_existing_access_token()
    if not token:
        # If not already logged in, open a browser window/tab to the login page.
        console.print(f"Opening {config.cp_web_url} ...")
        if not webbrowser.open(config.cp_web_url or ""):
            console.warn(
                f'Unable to open the browser. Please open the "{config.cp_web_url}" manually.'
            )

        """
        with yaspin() as sp:
            sp.text = "Waiting for session"
            max_tries = 30
            for _ in range(max_tries):
                token = (
                    requests.get(config.cp_url)
                    .cookies.get_dict()
                    .get("__clerk_db_jwt", None)
                )
                console.info(f"Fetching token: {token}")
                if token:
                    break
                else:
                    time.sleep(2)
        """
        token = input("Enter the token: ")
        if not token:
            console.error("Entered token is empty.")
            return

    if not hosting.validate_token(token):
        console.error("Access denied.")
        return

    hosting_config = {}

    if os.path.exists(constants.HOSTING_JSON):
        try:
            with open(constants.HOSTING_JSON, "r") as config_file:
                hosting_config = json.load(config_file)
        except Exception as ex:
            console.debug(f"Unable to parse the hosting config file due to {ex}")
            console.warn("Config file is corrupted. Creating a new one.")

    hosting_config["access_token"] = token
    try:
        with open(constants.HOSTING_JSON, "w") as config_file:
            json.dump(hosting_config, config_file)
    except Exception as ex:
        console.error(f"Unable to write to the hosting config file due to {ex}")
        return
    # TODO: do not show this message if the user is already logged in.
    console.print("Successfully logged in.")


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


project_cli = typer.Typer()


@project_cli.command()
def create(
    project_name: str = typer.Option(
        None,
        "-p",
        "--project-name",
        help="The name of the project to create. Only alphanumeric characters and hyphens are allowed.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
):
    """Create a new Reflex project for hosting."""  # Set the log level.
    console.set_log_level(loglevel)

    # Check if the control plane url is set.
    if not hosting.is_set_up():
        return

    if not project_name:
        console.error("Please provide a name for the project.")
        return

    # Check if the user is authenticated
    if not (token := hosting.authenticated_token()):
        return

    project_params = hosting.ProjectPostParam(name=project_name)
    response = requests.post(
        hosting.POST_PROJECT_ENDPOINT,
        headers=hosting.authorization_header(token),
        json=project_params.dict(exclude_none=True),
        timeout=config.http_request_timeout,
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.debug(f"Reason: {response.content}")
            console.error("Internal server error. Please contact support.")
    except requests.exceptions.Timeout:
        console.error("Unable to create project due to request timeout.")
    else:
        console.print(f"New project created (not deployed yet): {project_name}")


@project_cli.command(name="list")
def list_projects(
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
):
    """List all the projects for the authenticated user."""
    console.set_log_level(loglevel)

    if not hosting.is_set_up():
        return

    # Check if the user is authenticated
    if not (token := hosting.authenticated_token()):
        return

    response = requests.get(
        hosting.GET_PROJECT_ENDPOINT,
        headers=hosting.authorization_header(token),
        timeout=config.http_request_timeout,
    )

    if response.status_code != 200:
        console.error(f"Unable to list projects due to {response.reason}.")
        return

    try:
        for project in response.json():
            print(project["name"])
    except Exception as ex:
        console.debug(f"Unable to parse the response due to {ex}.")
        console.error("Unable to list projects due to internal errors.")


instance_cli = typer.Typer()


@instance_cli.command(name="list")
def list_instances(
    project_name: str = typer.Option(
        "-p",
        "--project-name",
        help="The name of the project to list instances for.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
):
    """List all the hosted instances for the specified project."""
    console.set_log_level(loglevel)

    if not hosting.is_set_up():
        return

    if not (token := hosting.authenticated_token()):
        return

    params = hosting.HostedInstanceGetParam(project_name=project_name)
    response = requests.get(
        hosting.GET_HOSTED_INSTANCE_ENDPOINT,
        headers=hosting.authorization_header(token),
        json=params.dict(exclude_none=True),
    )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.debug(f"Reason: {response.content}")
            console.error("Internal server error. Please contact support.")
        else:
            console.error(f"Unable to list hosted instances due to {response.reason}.")
        return
    except requests.exceptions.Timeout:
        console.error("Unable to list hosted instances due to request timeout.")
        return

    try:
        # TODO: add project name to the column if project_name not specified
        # TODO: below are very susceptible to changes in the API response, make it robust
        fields_to_show = [
            "key",
            "regions",
            "vm_type",
            "cpus",
            "memory_mb",
            "auto_start",
            "auto_stop",
        ]
        field_to_header = [
            "name",  # key is the name of the deployment
            "regions",
            "vm_type",
            "cpus",
            "memory_mb",
            "auto_start",
            "auto_stop",
        ]
        table = [[instance[k] for k in fields_to_show] for instance in response.json()]
        print(tabulate(table, headers=field_to_header))

    except Exception as ex:
        console.debug(f"Unable to parse the response due to {ex}.")
        console.error("Unable to list hosted instances due to internal errors.")


# TODO: alternatively, we can combine all requests into one to CP and send the files in the body
# then CP uploads files to S3 without needing resigned urls
# question: 1) if we need multipart upload https://stackoverflow.com/questions/63048825/how-to-upload-file-using-fastapi
# 2) if CP machine has enough disk space to store the files
@instance_cli.command()
def deploy(
    instance_name: str = typer.Option(
        ..., "-n", "--instance-name", help="The name of the instance to deploy."
    ),
    project_name: str = typer.Option(
        config.app_name,
        "-p",
        "--project-name",
        help="The name of the project to deploy under.",
    ),
    # TODO: make this in a list of choices
    regions: list[str] = typer.Option(
        ...,
        "-r",
        "--region",
        help="The regions to deploy to. For multiple regions, repeat this option followed by the region name.",
    ),
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
        None, help="Whether to auto start the instance."
    ),
    auto_stop: Optional[bool] = typer.Option(
        None, help="Whether to auto stop the instance."
    ),
    dry_run: bool = typer.Option(False, help="Whether to run a dry run."),
    loglevel: constants.LogLevel = typer.Option(
        console.LOG_LEVEL, help="The log level to use."
    ),
):
    """Deploy the app to the Reflex hosting service."""
    # Set the log level.
    console.set_log_level(loglevel)

    # Check if the deploy url is set.
    if not hosting.is_set_up():
        return

    # Check if the user is authenticated
    token = hosting.get_existing_access_token()
    if not token:
        console.error("Please authenticate using `reflex login` first.")
        return
    if not hosting.validate_token(token):
        console.error("Access denied, exiting.")
        return

    url_response = requests.post(
        hosting.POST_APP_API_URL_ENDPOINT,
        headers=hosting.authorization_header(token),
        json=hosting.AppAPIUrlPostParam(key=instance_name).dict(exclude_none=True),
        timeout=config.http_request_timeout,
    )
    try:
        url_response.raise_for_status()
        assert (
            url_response
            and "url" in (url_json := url_response.json())
            and "prefix" in url_json
        )
    except requests.exceptions.HTTPError:
        console.error(
            f"Unable to get ready to deploy the app due to {url_response.reason}."
        )
        return

    save_api_url = config.api_url
    # Compile the app in production mode.
    config.api_url = url_json["url"]
    export(loglevel=loglevel)
    config.api_url = save_api_url

    # Exit early if this is a dry run.
    if dry_run:
        return

    frontend_file_name = constants.FRONTEND_ZIP
    backend_file_name = constants.BACKEND_ZIP
    params = hosting.HostedInstancePostParam(
        key=instance_name,
        project_name=project_name,
        regions_json=json.dumps(regions),
        app_prefix=url_json["prefix"],
        vm_type=vm_type,
        cpus=cpus,
        memory_mb=memory_mb,
        auto_start=auto_start,
        auto_stop=auto_stop,
    )
    console.debug(f"{params.dict(exclude_none=True)}")
    try:
        with open(frontend_file_name, "rb") as frontend_file, open(
            backend_file_name, "rb"
        ) as backend_file:
            # https://docs.python-requests.org/en/latest/user/advanced/#post-multiple-multipart-encoded-files
            files = [
                ("files", (frontend_file_name, frontend_file)),
                ("files", (backend_file_name, backend_file)),
            ]
            response = requests.post(
                hosting.POST_HOSTED_INSTANCE_ENDPOINT,
                headers=hosting.authorization_header(token),
                data=params.dict(exclude_none=True),
                files=files,
            )
            print(response.json())
        response.raise_for_status()

    except requests.exceptions.HTTPError as http_error:
        console.error(f"Unable to deploy due to {http_error}.")
        return
    except requests.exceptions.Timeout:
        console.error("Unable to deploy due to request timeout.")
        return

    console.print(f"Successfully deployed {instance_name} to {regions}.")


cli.add_typer(db_cli, name="db", help="Subcommands for managing the database schema.")
cli.add_typer(
    project_cli,
    name="projects",
    help="Subcommands for managing the projects for hosting.",
)
cli.add_typer(
    instance_cli,
    name="instances",
    help="Subcommands for managing the hosted instance.",
)

if __name__ == "__main__":
    cli()
