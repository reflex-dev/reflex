"""Tests for the hosting CLI's logging pipeline, with and without reflex-base."""

from __future__ import annotations

import contextlib
import importlib
import logging
import sys
from collections.abc import Iterator
from types import ModuleType

import pytest
from reflex_cli.utils import console, log


class _ReflexBaseBlocker:
    """Meta path finder that makes reflex-base look uninstalled."""

    def find_spec(self, fullname: str, path=None, target=None):
        """Refuse to resolve reflex_base, as if it were not installed.

        Args:
            fullname: The module being imported.
            path: The parent package's search path.
            target: The module being reloaded, if any.

        Returns:
            None for every other module, deferring to the real finders.

        Raises:
            ImportError: If reflex_base (or a submodule) is being imported.
        """
        if fullname == "reflex_base" or fullname.startswith("reflex_base."):
            msg = f"No module named {fullname!r}"
            raise ImportError(msg)
        return


@contextlib.contextmanager
def _without_reflex_base() -> Iterator[tuple[ModuleType, ModuleType, ModuleType]]:
    """Import the CLI's logging modules as if reflex-base were not installed.

    Yields:
        The freshly imported (constants.base, utils.log, utils.console) modules.
    """
    cli_logger = logging.getLogger("reflex_cli")
    saved_state = (cli_logger.handlers[:], cli_logger.level, cli_logger.propagate)
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name.startswith(("reflex_cli", "reflex_base"))
    }
    for name in saved_modules:
        del sys.modules[name]
    blocker = _ReflexBaseBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield (
            importlib.import_module("reflex_cli.constants.base"),
            importlib.import_module("reflex_cli.utils.log"),
            importlib.import_module("reflex_cli.utils.console"),
        )
    finally:
        sys.meta_path.remove(blocker)
        for name in list(sys.modules):
            if name.startswith(("reflex_cli", "reflex_base")):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        cli_logger.handlers, cli_logger.level, cli_logger.propagate = saved_state


def test_reflex_base_is_used_when_installed():
    """The workspace has reflex-base, so the shared pipeline is what is used."""
    from reflex_base.utils import log as base_log

    assert log.HAS_REFLEX_BASE
    assert log.SUCCESS is base_log.SUCCESS
    assert log.set_log_level is base_log.set_log_level


def test_reflex_base_adopts_the_cli_logger_without_being_imported():
    """reflex-base parents reflex_cli itself, so the CLI never has to import it."""
    from reflex_base.utils import log as base_log

    assert "reflex_cli" in base_log.PACKAGE_LOGGER_NAMES


@pytest.mark.parametrize(
    "module",
    [
        "reflex_cli.utils.hosting",
        "reflex_cli.v2.apps",
        "reflex_cli.v2.cli",
        "reflex_cli.v2.deployments",
        "reflex_cli.v2.gcp",
        "reflex_cli.v2.project",
        "reflex_cli.v2.providers",
        "reflex_cli.v2.scan",
        "reflex_cli.v2.secrets",
        "reflex_cli.v2.vmtypes_regions",
    ],
)
def test_cli_imports_without_reflex_base(module: str):
    """Every CLI module imports on reflex versions that predate reflex-base."""
    with _without_reflex_base():
        importlib.import_module(module)


def test_fallback_success_level():
    """Without reflex-base the CLI defines the same SUCCESS level itself."""
    with _without_reflex_base() as (_, fallback_log, _console):
        assert not fallback_log.HAS_REFLEX_BASE
        assert fallback_log.SUCCESS == log.SUCCESS == 25
        assert logging.getLevelName(fallback_log.SUCCESS) == "SUCCESS"


def test_fallback_log_level_enum_matches_reflex_base():
    """The forked LogLevel is interchangeable with the reflex-base one."""
    from reflex_base.constants.base import LogLevel as BaseLogLevel

    with _without_reflex_base() as (constants_base, _, _console):
        forked = constants_base.LogLevel
        assert forked is not BaseLogLevel
        assert [level.value for level in forked] == [
            level.value for level in BaseLogLevel
        ]
        for level in forked:
            assert (
                level.to_logging_level() == BaseLogLevel(level.value).to_logging_level()
            )
        assert forked.from_string("warning") is forked.WARNING
        assert forked.from_string("nonsense") is None
        assert forked.from_string(None) is None
        assert forked.DEBUG < forked.INFO
        assert forked.DEBUG <= forked.DEBUG
        assert forked.ERROR > forked.INFO
        assert forked.ERROR >= forked.ERROR
        for level in forked:
            assert (
                level.subprocess_level().value
                == BaseLogLevel(level.value).subprocess_level().value
            )


def test_fallback_log_level_covers_the_whole_reflex_base_api():
    """The fork must expose everything the shared enum does.

    The fork is a drop-in for reflex-base's LogLevel, so CLI code written
    against the shared enum has to keep working when reflex-base is absent.
    A method added there and missed here would work on reflex 0.9 and break on
    older reflex -- the exact class of bug this package guards against.
    """
    from reflex_base.constants.base import LogLevel as BaseLogLevel

    with _without_reflex_base() as (constants_base, _, _console):
        forked = constants_base.LogLevel
        missing = {
            name
            for name in dir(BaseLogLevel)
            if not name.startswith("_") and not hasattr(forked, name)
        }
        assert not missing, (
            f"reflex_cli.constants.log_level.LogLevel is missing {sorted(missing)}, "
            "which reflex_base.constants.base.LogLevel defines."
        )


@pytest.mark.parametrize(
    ("level", "message", "expected"),
    [
        (logging.DEBUG, "a debug line", "Debug: a debug line"),
        (logging.INFO, "an info line", "Info: an info line"),
        (25, "a success line", "Success: a success line"),
        (logging.WARNING, "a warning line", "Warning: a warning line"),
    ],
)
def test_fallback_renders_records_to_stdout(capsys, level, message, expected):
    """The fallback sink renders records with the same prefixes as reflex-base."""
    with _without_reflex_base() as (constants_base, fallback_log, _console):
        fallback_log.set_log_level(constants_base.LogLevel.DEBUG)
        logging.getLogger("reflex_cli.test").log(level, message)

    assert expected in capsys.readouterr().out


def test_fallback_renders_errors_to_stderr(capsys):
    """Errors go to stderr, matching the reflex-base handler."""
    with _without_reflex_base() as (constants_base, fallback_log, _console):
        fallback_log.set_log_level(constants_base.LogLevel.INFO)
        logging.getLogger("reflex_cli.test").error("a failure")

    captured = capsys.readouterr()
    assert "a failure" in captured.err
    assert "a failure" not in captured.out


def test_fallback_gates_on_log_level(capsys):
    """Records below the configured level are not rendered."""
    with _without_reflex_base() as (constants_base, fallback_log, _console):
        fallback_log.set_log_level(constants_base.LogLevel.WARNING)
        cli_logger = logging.getLogger("reflex_cli.test")
        cli_logger.info("quiet info")
        cli_logger.warning("loud warning")

    captured = capsys.readouterr()
    assert "quiet info" not in captured.out
    assert "loud warning" in captured.out


def test_fallback_does_not_stack_handlers():
    """Repeated set_log_level calls reuse the one sink instead of stacking."""
    with _without_reflex_base() as (constants_base, fallback_log, _console):
        cli_logger = logging.getLogger("reflex_cli")
        fallback_log.set_log_level(constants_base.LogLevel.INFO)
        fallback_log.set_log_level(constants_base.LogLevel.DEBUG)

        assert cli_logger.handlers == [fallback_log._handler]
        # Propagation is cut so an application's own root config cannot
        # double-emit the CLI's records.
        assert not cli_logger.propagate
        assert cli_logger.level == logging.DEBUG


def test_fallback_rejects_non_log_level():
    """A non-LogLevel value is a programming error, not a silent no-op."""
    with _without_reflex_base() as (_, fallback_log, _console):
        with pytest.raises(TypeError):
            fallback_log.set_log_level("debug")
        # None means "leave it alone", matching reflex-base.
        fallback_log.set_log_level(None)


def test_set_log_level_accepts_strings(monkeypatch):
    """console.set_log_level keeps taking legacy string values."""
    with _without_reflex_base() as (_, _log, fallback_console):
        fallback_console.set_log_level("warning")
        assert logging.getLogger("reflex_cli").level == logging.WARNING
        # An unknown level falls back to INFO rather than raising.
        fallback_console.set_log_level("nonsense")
        assert logging.getLogger("reflex_cli").level == logging.INFO

    # The reflex-base path is process-wide: it sets REFLEX_LOGLEVEL so
    # subprocesses inherit the level, and moves a module global. Sandbox the
    # environment and put the level back, or the rest of the session (and any
    # subprocess it spawns) inherits whatever this test left behind.
    from reflex_base.constants.base import LogLevel as BaseLogLevel
    from reflex_base.utils import log as base_log

    previous = base_log.get_log_level()
    monkeypatch.setenv("REFLEX_LOGLEVEL", previous.value)
    try:
        console.set_log_level("warning")
        assert base_log.get_log_level() is BaseLogLevel.WARNING
        console.set_log_level("nonsense")
        assert base_log.get_log_level() is BaseLogLevel.INFO
    finally:
        base_log.set_log_level(previous)


def test_fallback_console_helpers(capsys):
    """The forked console renders the rich helpers the CLI actually uses."""
    with _without_reflex_base() as (_, _log, fallback_console):
        fallback_console.print("a plain line")
        fallback_console.print_table([["a@b.com", "1"]], headers=["email", "id"])
        fallback_console.rule("a rule")

    out = capsys.readouterr().out
    assert "a plain line" in out
    assert "a@b.com" in out
    assert "email" in out
    assert "a rule" in out
