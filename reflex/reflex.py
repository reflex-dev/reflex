"""Reflex CLI to create, run, and deploy apps."""

from __future__ import annotations

import logging
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn, cast, overload

import click
from reflex_base import constants
from reflex_base.config import get_config, reload_config
from reflex_base.environment import environment
from reflex_base.utils import console, log

from reflex.custom_components.custom_components import custom_components_cli
from reflex.utils.cli_options import log_options, loglevel_option

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from reflex_base.constants.base import LITERAL_ENV

    from reflex.minify import MinifyConfig


@click.group
@click.version_option(constants.Reflex.VERSION, message="%(version)s")
def cli():
    """Reflex CLI to create, run, and deploy apps."""
    # The CLI owns log rendering: attach the reflex sinks here and in every
    # worker subprocess (they inherit the marker through the environment).
    log.enable_managed_logging()


def raise_missing_package(name: str) -> NoReturn:
    """Report that the hosting CLI is not installed.

    Args:
        name: The `reflex` subcommand the user ran.

    Raises:
        Exit: Always, after reporting what to install.
    """
    package = constants.ReflexHostingCLI.MODULE_NAME
    logger.error(
        f"`reflex {name}` requires the {package} package, which is not "
        f"installed.\nInstall it with: pip install {package}"
    )
    raise click.exceptions.Exit(1)


def _missing_command(name: str) -> click.Command:
    """Build a stand-in for a cloud command whose package is unusable.

    The stand-in accepts any flags, so the user sees what to install rather than
    a usage error about an option the real command would have understood.

    Args:
        name: The command name to register.

    Returns:
        A command that reports how to install the hosting CLI.
    """
    package = constants.ReflexHostingCLI.MODULE_NAME

    @click.command(
        name=name,
        context_settings={"ignore_unknown_options": True},
        help=f"Requires the {package} package.",
    )
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def placeholder(args: tuple[str, ...]):
        raise_missing_package(name)

    return placeholder


def _init(
    name: str,
    template: str | None = None,
    ai: bool = False,
    agents: bool = False,
):
    """Initialize a new Reflex app in the given directory."""
    from reflex.utils import exec, frontend_skeleton, prerequisites, templates

    # Show system info
    exec.output_system_info()

    if ai:
        from reflex.utils.redir import reflex_build_redirect

        reflex_build_redirect()
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
    template = templates.initialize_app(app_name, template)

    # Initialize the .gitignore.
    frontend_skeleton.initialize_gitignore()

    # Write or refresh the AGENTS.md for AI coding agents.
    if agents:
        frontend_skeleton.initialize_agents_md()

    template_msg = f" using the {template} template" if template else ""
    if Path(constants.PyprojectToml.FILE).exists():
        needs_user_manual_update = False
        next_steps = " Run `uv run reflex run` to start the app."
    else:
        needs_user_manual_update = frontend_skeleton.initialize_requirements_txt()
        next_steps = " Install dependencies from `requirements.txt` with `uv pip install -r requirements.txt` (or your preferred installer) before running `uv run reflex run`."
    manual_update = (
        f" Make sure to add `{constants.RequirementsTxt.DEFAULTS_STUB + constants.Reflex.VERSION}` to your requirements.txt file."
        if needs_user_manual_update
        else ""
    )

    # Finish initializing the app.
    logger.log(
        log.SUCCESS,
        f"Initialized {app_name}{template_msg}.{manual_update}{next_steps}",
    )


@cli.command()
@log_options
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
@click.option(
    "--agents/--no-agents",
    default=True,
    help="Write an AGENTS.md to guide AI coding agents working in the app (enabled by default).",
)
def init(
    name: str,
    template: str | None,
    ai: bool,
    agents: bool,
):
    """Initialize a new Reflex app in the current directory."""
    _init(name, template, ai, agents)


def _compile_app(*, avoid_dirty_check: bool = True):
    from reflex.utils import exec, prerequisites

    app_task = prerequisites.compile_or_validate_app
    args = (True,)
    kwargs = {
        "check_if_schema_up_to_date": True,
        "prerender_routes": exec.should_prerender_routes(),
        "trigger": "initial",
    }

    # Granian fails if the app is already imported.
    if exec.should_use_granian() and avoid_dirty_check:
        import concurrent.futures

        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            compile_future = executor.submit(app_task, *args, **kwargs)
            return_result = compile_future.result()
    else:
        return_result = app_task(*args, **kwargs)

    if not return_result:
        raise SystemExit(1)


def _run_dev(
    running_mode: constants.RunningMode,
    frontend_port: int | None,
    backend_port: int | None,
    backend_host: str,
):
    """Run the app in development mode."""
    import atexit

    from reflex.utils import build, exec, processes, telemetry

    config = get_config()

    if frontend_port:
        config._set_persistent(frontend_port=frontend_port)
    if backend_port:
        config._set_persistent(backend_port=backend_port)

    if running_mode.has_frontend():
        _compile_app()

    # Post a telemetry event.
    telemetry.send("run-dev")

    # Display custom message when there is a keyboard interrupt.
    atexit.register(processes.atexit_handler)

    # Run the frontend and backend together.
    commands = []

    # Run the frontend on a separate thread.
    if running_mode.has_frontend():
        build.setup_frontend(Path.cwd())
        commands.append((
            exec.run_frontend,
            Path.cwd(),
            frontend_port,
            running_mode.has_backend(),
        ))

    # Start the frontend and backend.
    with processes.run_concurrently_context(*commands):
        # In dev mode, run the backend on the main thread.
        if running_mode.has_backend() and backend_port:
            exec.run_backend(
                backend_host,
                int(backend_port),
                config.loglevel.subprocess_level(),
                running_mode.has_frontend(),
            )
            # The windows uvicorn bug workaround
            # https://github.com/reflex-dev/reflex/issues/2335
            if constants.IS_WINDOWS and exec.frontend_process:
                # Sends SIGTERM in windows
                exec.kill(exec.frontend_process.pid)


def _run_preview(running_mode: constants.RunningMode, port: int, host: str):
    """Run the app in preview mode.

    Like dev mode, but instead of running the Vite dev server it serves a freshly
    built (un-minified) frontend bundle mounted into the backend on a single port.
    The backend still hot reloads, and each reload re-runs the frontend build
    against the newly compiled output, so a manual browser refresh shows changes.
    """
    import atexit

    from reflex.utils import build, exec, processes, telemetry

    config = get_config()

    config._set_persistent(frontend_port=port, backend_port=port)

    # Mount the compiled frontend into the dev backend so no Vite server is needed.
    environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.set(
        running_mode.has_frontend() and running_mode.has_backend()
    )

    if running_mode.has_frontend():
        # Compile the app and produce the initial frontend build.
        _compile_app()
        build.setup_frontend_prod(Path.cwd())

    # Post a telemetry event.
    telemetry.send("run-preview")

    # Display custom message when there is a keyboard interrupt.
    atexit.register(processes.atexit_handler)

    exec.notify_app_running()
    exec.notify_frontend(
        f"http://{host}:{port}",
        backend_present=running_mode.has_backend(),
    )

    if running_mode.has_backend():
        exec.run_backend(
            host, port, config.loglevel.subprocess_level(), running_mode.has_frontend()
        )
    else:
        exec.run_frontend_prod(host, port)


def _run_prod(running_mode: constants.RunningMode, port: int, host: str):
    import atexit

    from reflex.utils import build, exec, processes, telemetry

    config = get_config()

    config._set_persistent(frontend_port=port, backend_port=port)

    if running_mode.has_frontend():
        # Get the app module.
        _compile_app(avoid_dirty_check=False)
        build.setup_frontend_prod(Path.cwd())

    _skip_compile()

    # Post a telemetry event.
    telemetry.send("run-prod")

    # Display custom message when there is a keyboard interrupt.
    atexit.register(processes.atexit_handler)

    exec.notify_app_running()
    exec.notify_frontend(
        f"http://{host}:{port}",
        backend_present=running_mode.has_backend(),
    )
    if running_mode.has_backend():
        exec.run_backend_prod(
            host, port, config.loglevel.subprocess_level(), running_mode.has_frontend()
        )
    else:
        exec.run_frontend_prod(host, port)


def _run(
    *,
    env: constants.Env = constants.Env.DEV,
    running_mode: constants.RunningMode = constants.RunningMode.FULLSTACK,
    frontend_port: int | None = None,
    backend_port: int | None = None,
    backend_host: str | None = None,
):
    """Run the app in the given directory."""
    from reflex.istate.manager import reset_disk_state_manager
    from reflex.utils import exec, prerequisites, processes

    if frontend_port and not running_mode.has_frontend():
        logger.error("Cannot specify --frontend-port when not running frontend.")
        raise SystemExit(1)
    if backend_port and not running_mode.has_backend():
        logger.error("Cannot specify --backend-port when not running backend.")
        raise SystemExit(1)
    if (
        env in (constants.Env.PROD, constants.Env.PREVIEW)
        and frontend_port
        and backend_port
        and frontend_port != backend_port
    ):
        logger.error(
            f"In {env.value} mode, frontend and backend must run on the same port."
        )
        raise SystemExit(1)

    config = get_config()

    backend_host = backend_host or config.backend_host

    # Set env mode in the environment
    environment.REFLEX_ENV_MODE.set(env)

    # Preview serves a real (but readable) frontend bundle: disable JS/CSS
    # minification by default for readable output and to speed up rebuilds.
    # Sourcemaps are left off (the default) since un-minified output is already
    # debuggable, and autoprefixer is skipped (vendor prefixes are unnecessary for
    # local dev). All remain overridable via the corresponding env vars.
    if env == constants.Env.PREVIEW:
        if not environment.VITE_MINIFY.is_set():
            environment.VITE_MINIFY.set(False)
        if not environment.REFLEX_NO_AUTOPREFIXER.is_set():
            environment.REFLEX_NO_AUTOPREFIXER.set(True)

    # Show system info
    exec.output_system_info()

    if running_mode == constants.RunningMode.BACKEND_ONLY:
        _skip_compile()

    prerequisites.assert_in_reflex_dir()

    # Check that the app is initialized.
    if running_mode.has_frontend() and prerequisites.needs_reinit():
        _init(name=config.app_name)

    # Delete the states folder if it exists.
    reset_disk_state_manager()

    # Apply the new ports and host to the config.
    if frontend_port != config.frontend_port:
        config._set_persistent(frontend_port=frontend_port)
    if backend_port != config.backend_port:
        config._set_persistent(backend_port=backend_port)
    if backend_host != config.backend_host:
        config._set_persistent(backend_host=backend_host)

    # Reload the config to make sure the env vars are persistent.
    reload_config()

    console.rule("[bold]Starting Reflex App")

    prerequisites.check_latest_package_version(constants.Reflex.MODULE_NAME)

    if env == constants.Env.DEV:
        # Find the next available open port if applicable.
        if running_mode.has_frontend():
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

        if running_mode.has_backend():
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

        _run_dev(running_mode, frontend_port, backend_port, backend_host)
    else:
        if running_mode == constants.RunningMode.BACKEND_ONLY:
            requested_port = backend_port or config.backend_port
            fallback_port = constants.DefaultPorts.BACKEND_PORT
        elif running_mode == constants.RunningMode.FRONTEND_ONLY:
            requested_port = frontend_port or config.frontend_port
            fallback_port = constants.DefaultPorts.FRONTEND_PORT
        else:
            requested_port = (
                frontend_port
                or backend_port
                or config.frontend_port
                or config.backend_port
            )
            fallback_port = constants.DefaultPorts.FRONTEND_PORT

        port = processes.handle_port(
            service_name=running_mode.name.lower(),
            port=requested_port or fallback_port,
            auto_increment=requested_port is None,
        )

        if env == constants.Env.PREVIEW:
            _run_preview(running_mode, port, backend_host)
        else:
            _run_prod(running_mode, port, backend_host)


@cli.command()
@log_options
@click.option(
    "--env",
    type=click.Choice([e.value for e in constants.Env], case_sensitive=False),
    default=constants.Env.DEV.value,
    help=(
        "The environment to run the app in. 'preview' hot reloads like 'dev' but "
        "serves a freshly built, un-minified frontend bundle instead of the Vite dev server."
    ),
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
@click.option(
    "--single-port",
    is_flag=True,
    help="Run both frontend and backend on the same port.",
    default=False,
)
def run(
    env: LITERAL_ENV,
    frontend_only: bool,
    backend_only: bool,
    frontend_port: int | None,
    backend_port: int | None,
    backend_host: str | None,
    single_port: bool,
):
    """Run the app in the current directory."""
    from reflex.utils import prerequisites

    if frontend_only and backend_only:
        logger.error("Cannot use both --frontend-only and --backend-only options.")
        raise SystemExit(1)

    if single_port:
        if env != constants.Env.PROD:
            logger.error("--single-port can only be used with --env=PROD.")
            raise SystemExit(1)
        if frontend_only or backend_only:
            logger.error(
                "Cannot use --single-port with --frontend-only or --backend-only."
            )
            raise SystemExit(1)
        if frontend_port and backend_port and frontend_port != backend_port:
            logger.error(
                "Cannot specify different ports for frontend and backend when using --single-port."
            )
            raise SystemExit(1)

    config = get_config()

    frontend_port = frontend_port or config.frontend_port
    backend_port = backend_port or config.backend_port
    backend_host = backend_host or config.backend_host

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.RUN)
    environment.REFLEX_BACKEND_ONLY.set(backend_only)
    environment.REFLEX_FRONTEND_ONLY.set(frontend_only)

    running_mode = prerequisites.check_running_mode(frontend_only, backend_only)

    _run(
        env=constants.Env(env),
        running_mode=running_mode,
        frontend_port=frontend_port,
        backend_port=backend_port,
        backend_host=backend_host,
    )


@cli.command()
@log_options
@click.option(
    "--dry",
    is_flag=True,
    default=False,
    help="Run the command without making any changes.",
)
@click.option(
    "--rich/--no-rich",
    default=True,
    is_flag=True,
    help="Whether to use rich progress bars.",
)
def compile(dry: bool, rich: bool):
    """Compile the app in the current directory."""
    import time

    from reflex.utils import prerequisites

    # Check the app.
    if prerequisites.needs_reinit():
        _init(name=get_config().app_name)
    reload_config()
    starting_time = time.monotonic()
    prerequisites.get_compiled_app(dry_run=dry, use_rich=rich, trigger="cli_compile")
    elapsed_time = time.monotonic() - starting_time
    logger.log(log.SUCCESS, f"App compiled successfully in {elapsed_time:.3f} seconds.")


@cli.command()
@log_options
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
    type=click.Choice(
        [constants.Env.DEV.value, constants.Env.PROD.value], case_sensitive=False
    ),
    default=constants.Env.PROD.value,
    help="The environment to export the app in.",
)
@click.option(
    "--exclude-from-backend",
    "backend_excluded_dirs",
    multiple=True,
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
    help="Files or directories to exclude from the backend zip. Can be used multiple times.",
)
@click.option(
    "--server-side-rendering/--no-server-side-rendering",
    "--ssr/--no-ssr",
    "ssr",
    default=True,
    is_flag=True,
    help="Whether to enable server side rendering for the frontend.",
)
def export(
    zip: bool,
    frontend_only: bool,
    backend_only: bool,
    zip_dest_dir: str,
    upload_db_file: bool,
    env: Literal["dev", "prod"],
    backend_excluded_dirs: tuple[Path, ...] = (),
    ssr: bool = True,
):
    """Export the app to a zip file."""
    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites
    from reflex.utils.exec import arbitrate_ssr

    ssr = arbitrate_ssr(ssr)

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.EXPORT)

    running_mode = prerequisites.check_running_mode(frontend_only, backend_only)

    config = get_config()

    prerequisites.assert_in_reflex_dir()

    if running_mode.has_frontend() and prerequisites.needs_reinit():
        _init(name=config.app_name)

    export_utils.export(
        zipping=zip,
        frontend=running_mode.has_frontend(),
        backend=running_mode.has_backend(),
        zip_dest_dir=zip_dest_dir,
        upload_db_file=upload_db_file,
        env=constants.Env.DEV if env == constants.Env.DEV else constants.Env.PROD,
        loglevel=config.loglevel.subprocess_level(),
        backend_excluded_dirs=backend_excluded_dirs,
        prerender_routes=ssr,
    )


@cli.command()
@log_options
def login():
    """Authenticate with experimental Reflex hosting service."""
    try:
        from reflex_cli.v2 import cli as hosting_cli
        from reflex_cli.v2.deployments import check_version
    except ImportError:
        raise_missing_package("login")

    check_version()

    if (validated_info := hosting_cli.login()) and (
        user_uuid := validated_info.get("user_id")
    ):
        _skip_compile()  # Allow running outside of an app dir
        from reflex.utils import telemetry

        set_props = {}
        if user_email := validated_info.get("email"):
            set_props["email"] = user_email
        if user_tier := validated_info.get("tier"):
            set_props["tier"] = user_tier
        telemetry.send(
            "login",
            properties={
                "$set": set_props,
                "user_uuid": user_uuid,
            },
        )


@cli.command()
@log_options
def logout():
    """Log out of access to Reflex hosting service."""
    try:
        from reflex_cli.v2.cli import logout
        from reflex_cli.v2.deployments import check_version
    except ImportError:
        raise_missing_package("logout")

    check_version()

    logout(get_config().loglevel)


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
        logger.error("db_url is not configured, cannot initialize.")
        return

    # Check the alembic config.
    if environment.ALEMBIC_CONFIG.get().exists():
        logger.error(
            "Database is already initialized. Use "
            "[bold]reflex db makemigrations[/bold] to create schema change "
            "scripts and [bold]reflex db migrate[/bold] to apply migrations "
            "to a new or existing database.",
            extra={"rich": True},
        )
        return

    # Initialize the database.
    _skip_compile()
    prerequisites.get_compiled_app()
    model.alembic_init()
    model.migrate(autogenerate=True)


@db_cli.command()
def migrate():
    """Create or update database schema from migration scripts."""
    from reflex import model
    from reflex.utils import prerequisites

    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        return
    model.migrate()
    prerequisites.check_schema_up_to_date()


@db_cli.command()
def status():
    """Check the status of the database schema."""
    from reflex.model import format_revision, get_migration_history
    from reflex.utils import prerequisites

    prerequisites.get_app()
    if not prerequisites.check_db_initialized():
        logger.info(
            "Database is not initialized. Run [bold]reflex db init[/bold] to initialize.",
            extra={"rich": True},
        )
        return

    # Run alembic check command and display output
    import reflex_base.config

    config = reflex_base.config.get_config()
    console.print(f"[bold]\\[{config.db_url}][/bold]")

    # Get migration history using Model method
    current_rev, revisions = get_migration_history()
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
    with model.get_engine().connect() as connection:
        try:
            model.alembic_autogenerate(connection=connection, message=message)
        except CommandError as command_error:
            if "Target database is not up to date." not in str(command_error):
                raise
            logger.error(
                f"{command_error} Run [bold]reflex db migrate[/bold] to update database."
            )


@cli.command()
@log_options
@click.argument("new_name")
def rename(new_name: str):
    """Rename the app in the current directory."""
    from reflex.utils import prerequisites
    from reflex.utils.rename import rename_app

    prerequisites.validate_app_name(new_name)
    # Reload so we read rxconfig.py from the current directory, not a cached one.
    reload_config()
    rename_app(new_name, get_config().loglevel)


# Minify command group
@cli.group()
def minify():
    """Manage state and event name minification."""


def _load_app_for_minify() -> None:
    """Compile the user's app so dynamic states (e.g. ``ComponentState``) register."""
    from reflex.utils import prerequisites

    prerequisites.get_compiled_app(dry_run=True)


def _count_events(config: MinifyConfig) -> int:
    """Sum event handlers across every state in a minify config.

    Args:
        config: The minify configuration.

    Returns:
        Total handler count.
    """
    return sum(len(handlers) for handlers in config["events"].values())


@overload
def _open_minify_session(*, require_exists: Literal[True] = True) -> MinifyConfig: ...
@overload
def _open_minify_session(*, require_exists: Literal[False]) -> MinifyConfig | None: ...


def _open_minify_session(*, require_exists: bool = True) -> MinifyConfig | None:
    """Run the standard minify-CLI prelude.

    Compiles the user's app (so dynamic states register) and loads
    ``minify.json``. Exits the CLI with an error when the file is required
    but missing, or when it exists but is malformed.

    Args:
        require_exists: When ``True`` (default), missing ``minify.json`` is
            a fatal error. When ``False``, returns ``None`` instead.

    Returns:
        The parsed config, or ``None`` if ``require_exists`` is ``False`` and
        the file is absent.
    """
    from reflex.minify import (
        MINIFY_JSON,
        _get_minify_json_path,
        _load_minify_config_uncached,
    )

    exists = _get_minify_json_path().exists()
    if require_exists and not exists:
        logger.error(
            f"{MINIFY_JSON} does not exist. Use 'reflex minify init' to create it."
        )
        raise SystemExit(1)

    _load_app_for_minify()

    if not exists:
        return None

    try:
        config = _load_minify_config_uncached()
    except ValueError as e:
        logger.error(str(e))
        raise SystemExit(1) from e
    if config is None:
        logger.error(f"Failed to load {MINIFY_JSON}.")
        raise SystemExit(1)
    return config


@minify.command(name="init")
@loglevel_option
def minify_init():
    """Initialize minify.json with IDs for all states and events."""
    from reflex.minify import (
        MINIFY_JSON,
        _get_minify_json_path,
        generate_minify_config,
        save_minify_config,
    )

    if _get_minify_json_path().exists():
        logger.error(
            f"{MINIFY_JSON} already exists. Use 'reflex minify sync' to update "
            "or delete the file to reinitialize."
        )
        raise SystemExit(1)

    _load_app_for_minify()
    config = generate_minify_config()
    save_minify_config(config)

    logger.info(
        f"Created {MINIFY_JSON} with {len(config['states'])} states "
        f"and {_count_events(config)} events."
    )


@minify.command(name="sync")
@loglevel_option
@click.option(
    "--reassign-deleted",
    is_flag=True,
    help="Reassign IDs that are no longer in use (potentially breaking for existing clients).",
)
@click.option(
    "--prune",
    is_flag=True,
    help="Remove entries for states/events that no longer exist in code.",
)
def minify_sync(reassign_deleted: bool, prune: bool):
    """Synchronize minify.json with the current codebase.

    Adds new states and events, optionally removes orphaned entries.
    """
    from reflex.minify import MINIFY_JSON, save_minify_config, sync_minify_config

    existing_config = _open_minify_session()
    new_config = sync_minify_config(
        existing_config, reassign_deleted=reassign_deleted, prune=prune
    )
    save_minify_config(new_config)

    logger.info(f"Updated {MINIFY_JSON}:")
    logger.info(
        f"  States: {len(existing_config['states'])} -> {len(new_config['states'])}"
    )
    logger.info(
        f"  Events: {_count_events(existing_config)} -> {_count_events(new_config)}"
    )


@minify.command(name="validate")
@loglevel_option
def minify_validate():
    """Validate minify.json against the current codebase.

    Checks for duplicate IDs, missing entries, and orphaned entries.
    """
    from reflex.minify import MINIFY_JSON, validate_minify_config

    config = _open_minify_session()
    errors, warnings, missing = validate_minify_config(config)

    if errors:
        logger.error("Errors found:")
        for error in errors:
            logger.error(f"  - {error}")

    if warnings:
        logger.warning("Warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")

    if missing:
        logger.warning("Missing entries (in code but not in config):")
        for entry in missing:
            logger.warning(f"  - {entry}")

    if errors or missing:
        raise SystemExit(1)
    logger.info(f"{MINIFY_JSON} is valid and up-to-date.")


@minify.command(name="list")
@loglevel_option
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON.",
)
def minify_list(output_json: bool):
    """Print the state tree with IDs and minified names."""
    from typing import TypedDict

    from reflex.minify import get_state_full_path
    from reflex.state import BaseState, State

    class EventHandlerData(TypedDict):
        """Type for event handler data in state tree."""

        name: str
        event_id: str | None  # The minified name (e.g., "a", "ba") or None

    class StateTreeData(TypedDict):
        """Type for state tree data."""

        name: str
        full_path: str
        state_id: str | None  # The minified name (e.g., "a", "ba") or None
        event_handlers: list[EventHandlerData]
        substates: list[StateTreeData]

    # CLI inspection shows config contents regardless of env var settings.
    config = _open_minify_session(require_exists=False)
    states_map = config["states"] if config else {}
    events_map = config["events"] if config else {}

    def build_state_tree(state_cls: type[BaseState]) -> StateTreeData:
        """Recursively build state tree data.

        Args:
            state_cls: The state class to build the tree for.

        Returns:
            A dictionary containing the state tree data.
        """
        state_path = get_state_full_path(state_cls)
        state_entry = states_map.get(state_path)
        state_id = state_entry["id"] if state_entry is not None else None

        handler_ids = events_map.get(state_path, {})
        handlers: list[EventHandlerData] = [
            {"name": handler_name, "event_id": handler_ids.get(handler_name)}
            for handler_name in sorted(state_cls.event_handlers.keys())
        ]

        # Build substates recursively
        substates = [
            build_state_tree(substate)
            for substate in sorted(state_cls.get_substates(), key=lambda s: s.__name__)
        ]

        return {
            "name": state_cls.__name__,
            "full_path": state_path,
            "state_id": state_id,
            "event_handlers": handlers,
            "substates": substates,
        }

    def print_state_tree(
        state_data: StateTreeData, prefix: str = "", is_last: bool = True
    ):
        """Print a state and its children as a tree.

        Args:
            state_data: The state data dictionary.
            prefix: The prefix for indentation.
            is_last: Whether this is the last item in the current level.
        """
        # state_id is now the minified name directly (e.g., "a", "ba")
        state_id = state_data["state_id"]

        # Print the state node
        connector = "`-- " if is_last else "|-- "
        if state_id is not None:
            click.echo(f'{prefix}{connector}{state_data["name"]} -> "{state_id}"')
        else:
            click.echo(f"{prefix}{connector}{state_data['name']}")

        # Calculate new prefix for children
        child_prefix = prefix + ("    " if is_last else "|   ")

        # Print event handlers
        handlers = state_data["event_handlers"]
        substates = state_data["substates"]
        has_substates = len(substates) > 0

        if handlers:
            click.echo(
                f"{child_prefix}{'|' if has_substates else '`'}-- Event Handlers:"
            )
            handler_prefix = child_prefix + ("|   " if has_substates else "    ")
            for i, handler in enumerate(handlers):
                is_last_handler = i == len(handlers) - 1
                h_connector = "`-- " if is_last_handler else "|-- "
                # event_id is now the minified name directly
                event_id = handler["event_id"]
                if event_id is not None:
                    click.echo(
                        f'{handler_prefix}{h_connector}{handler["name"]} -> "{event_id}"'
                    )
                else:
                    click.echo(f"{handler_prefix}{h_connector}{handler['name']}")

        # Print substates recursively
        for i, substate in enumerate(substates):
            is_last_substate = i == len(substates) - 1
            print_state_tree(substate, child_prefix, is_last_substate)

    tree_data = build_state_tree(State)

    if output_json:
        import json

        click.echo(json.dumps(tree_data, indent=2))
    else:
        if config is not None:
            click.echo("State Tree (minify.json loaded)")
        else:
            click.echo("State Tree (no minify.json)")
        print_state_tree(tree_data)


@minify.command(name="lookup")
@loglevel_option
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output detailed info as JSON.",
)
@click.argument("minified_path")
def minify_lookup(output_json: bool, minified_path: str):
    """Lookup a state or event handler by its minified path (e.g., 'a.bU').

    Walks the state tree from the root to resolve each segment. The final
    segment may also be an event handler id of the state resolved so far, so
    an event name copied from the frontend resolves to its handler. The root
    state's own name is optional, so both 'a.bU' and the full name seen in
    the frontend ('reflex___state____state.a.bU') resolve the same way.
    """
    from reflex.minify import collect_all_states, get_state_full_path
    from reflex.state import State

    config = _open_minify_session()

    # Build lookup: full_path -> minified_id (None if no entry).
    path_to_id: dict[str, str | None] = {}
    for s in collect_all_states(State):
        path = get_state_full_path(s)
        entry = config["states"].get(path)
        path_to_id[path] = entry["id"] if entry is not None else None

    parts = minified_path.split(".")
    # The framework root state is never minified, so it never contributes a
    # minified segment. Accept a path copied verbatim from the frontend, which
    # still carries the root's default name as its first segment.
    if parts[0] == State.get_name():
        parts = parts[1:]

    result_parts: list[dict[str, str]] = []
    current = State
    last_index = len(parts) - 1

    for index, part in enumerate(parts):
        # Find the child of the previous match whose minified id is ``part``.
        found = next(
            (
                c
                for c in current.get_substates()
                if path_to_id.get(get_state_full_path(c)) == part
            ),
            None,
        )
        # An event name copied from the frontend ends in a handler id of the
        # state resolved so far, not in a substate id.
        handler = None
        current_path = get_state_full_path(current)
        if index == last_index:
            handler = next(
                (
                    name
                    for name, event_id in config["events"].get(current_path, {}).items()
                    if event_id == part
                ),
                None,
            )
        if found is None and handler is None:
            kind = "state or event handler" if index == last_index else "state"
            logger.error(
                f"No {kind} found for minified segment '{part}' in path '{minified_path}'"
            )
            raise SystemExit(1)

        if found is not None:
            result_parts.append({
                "kind": "state",
                "minified": part,
                "state_id": part,  # we just matched on it
                "module": found.__module__,
                "class": found.__name__,
                "full_path": get_state_full_path(found),
            })
        if handler is not None:
            # JSON readers see the ambiguity as two entries for one segment.
            if found is not None and not output_json:
                logger.warning(
                    f"Segment '{part}' is both a substate id and an event handler id "
                    f"of {current.__module__}.{current.__name__}; showing both."
                )
            result_parts.append({
                "kind": "event",
                "minified": part,
                "event_id": part,
                "module": current.__module__,
                "class": current.__name__,
                "handler": handler,
                "full_path": f"{current_path}.{handler}",
            })
        if found is not None:
            current = found

    if output_json:
        import json

        click.echo(json.dumps(result_parts, indent=2))
    else:
        # Simple output: module.ClassName, plus .handler for an event handler.
        for info in result_parts:
            line = f"{info['module']}.{info['class']}"
            if info["kind"] == "event":
                line += f".{info['handler']}"
            click.echo(line)


try:
    from reflex_cli.v2.deploy import deploy
    from reflex_cli.v2.deployments import hosting_cli
except ImportError:
    # The cloud commands still answer, so the failure names the package to
    # install instead of looking like a typo in the command name.
    cli.add_command(_missing_command("deploy"), name="deploy")
    cli.add_command(_missing_command("cloud"), name="cloud")
else:
    if find_spec("typer") and find_spec("typer.main"):
        import typer  # pyright: ignore[reportMissingImports]

        if isinstance(hosting_cli, typer.Typer):
            # typer >=0.27 vendors click, so its commands are structurally but
            # not nominally click commands.
            hosting_cli_command = cast(
                "click.Command", typer.main.get_command(hosting_cli)
            )
        else:
            hosting_cli_command = hosting_cli
    else:
        hosting_cli_command = hosting_cli

    cli.add_command(deploy, name="deploy")
    cli.add_command(hosting_cli_command, name="cloud")

cli.add_command(db_cli, name="db")
cli.add_command(script_cli, name="script")
cli.add_command(custom_components_cli, name="component")

if __name__ == "__main__":
    cli()
