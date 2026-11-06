"""Thin wrappers over the alembic command line, used by `reflex db`.

The migration logic lives in alembic and in the env.py that `reflex db init`
writes from the template in `reflex/.templates/alembic`, so the `alembic`
command line works on a Reflex app exactly as `reflex db` does.
"""

from __future__ import annotations

import contextlib
import io
import logging
import shutil
from pathlib import Path

from reflex_base.environment import environment
from rich.markup import escape

from reflex.utils.prerequisites import get_app

logger = logging.getLogger(__name__)

# The env.py that replaces the stock one after `alembic init`.
TEMPLATE_ENV_PY = Path(__file__).parent.parent / ".templates" / "alembic" / "env.py"

LEGACY_ENV_HINT = (
    "The migration environment was created by an earlier Reflex release and "
    "cannot load the app. Run [bold]reflex db init[/bold] to update env.py; "
    "existing revisions are kept."
)

UPDATED_ENV_MESSAGE = (
    "Updated env.py to load the app; the previous one is kept as {backup}."
)

# True while env.py imports the app, when an import-time `migrate()` call would
# start a second alembic run inside the one already in progress.
_loading_app = False

# True while `run` executes an alembic command, so env.py can tell `reflex db`
# and `migrate()` apart from the `alembic` command line.
_in_run = False


def invoked_by_reflex() -> bool:
    """Whether the alembic command now running was started by `run`.

    Returns:
        True under `reflex db` and `migrate()`, False under the `alembic`
        command line.
    """
    return _in_run


def run(*args: str) -> None:
    """Run an alembic command line against the app's alembic.ini.

    Equivalent to ``alembic -c <ALEMBIC_CONFIG> <args>``, except that a failure
    raises ``alembic.util.exc.CommandError`` instead of exiting the process. A
    command issued while env.py imports the app, such as ``migrate()`` at module
    level, is skipped: alembic is already running and applies the scripts itself.

    Args:
        *args: The alembic command and its options, e.g. ``"upgrade", "head"``.
    """
    global _in_run

    if _loading_app:
        logger.debug(
            f"Skipping alembic {' '.join(args)}: an alembic run is loading the app."
        )
        return
    import alembic.config

    _in_run = True
    try:
        alembic.config.main(
            argv=[
                "--raiseerr",
                "--config",
                str(environment.ALEMBIC_CONFIG.get()),
                *args,
            ],
            prog="alembic",
        )
    finally:
        _in_run = False


def load_app() -> None:
    """Import the app for env.py, so that the models it declares are registered.

    The import may itself call ``migrate()`` at module level, before the app
    object exists; ``run`` skips the alembic command that would start then.
    """
    global _loading_app

    _loading_app = True
    try:
        get_app()
    finally:
        _loading_app = False


def init() -> None:
    """Run `alembic init` with its stock template, then install the reflex env.py.

    Without alembic's output: it names each template file even with --quiet, and
    its closing advice to edit the connection settings in alembic.ini does not
    apply, as env.py takes the database URL from rxconfig.py.
    """
    directory = environment.ALEMBIC_CONFIG.get().parent / "alembic"
    with contextlib.redirect_stdout(io.StringIO()):
        run("init", str(directory))
    install_env()


def install_env() -> Path:
    """Write the reflex env.py template into the script directory.

    Returns:
        The path of the written env.py.

    Raises:
        CommandError: If alembic.ini names no script directory or it is missing.
    """
    env_py = script_directory() / "env.py"
    shutil.copy(TEMPLATE_ENV_PY, env_py)
    return env_py


def script_directory() -> Path:
    """Locate the script directory named by alembic.ini.

    Returns:
        The directory holding env.py, script.py.mako and versions/.

    Raises:
        CommandError: If alembic.ini names no script directory or it is missing.
    """
    import alembic.config
    import alembic.script

    config = alembic.config.Config(environment.ALEMBIC_CONFIG.get())
    return Path(alembic.script.ScriptDirectory.from_config(config).dir)


def is_legacy_env() -> bool:
    """Whether env.py predates the reflex template and cannot load the app.

    Earlier Reflex releases ran `alembic init` with alembic's stock template and
    never executed the resulting env.py, which still reads
    ``target_metadata = None`` and connects to the placeholder URL in alembic.ini.

    Returns:
        True if env.py is the stock alembic template.
    """
    from alembic.util.exc import CommandError

    try:
        env_py = script_directory() / "env.py"
    except CommandError:
        # Let the command that needs the directory report what is wrong with it.
        return False
    return env_py.exists() and "target_metadata = None" in env_py.read_text()


def update_legacy_env() -> Path | None:
    """Replace a stock env.py with the reflex template, keeping it as env.old.

    Returns:
        Where the previous env.py went, or None when env.py already loads the app.
    """
    if not is_legacy_env():
        return None
    env_py = script_directory() / "env.py"
    backup = env_py.with_name("env.old")
    env_py.replace(backup)
    install_env()
    return backup


def describe_error(error: Exception) -> str:
    """Describe an alembic error with the reflex command that resolves it.

    Args:
        error: The ``CommandError`` alembic raised.

    Returns:
        The error message as rich markup, with a hint when the database is
        behind its scripts.
    """
    message = escape(str(error))
    if "Target database is not up to date." in message:
        message += " Run [bold]reflex db migrate[/bold] to update database."
    return message
