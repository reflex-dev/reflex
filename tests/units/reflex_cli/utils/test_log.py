"""Tests for the hosting CLI's logging pipeline, with and without reflex-base."""

from __future__ import annotations

import ast
import contextlib
import importlib
import logging
import sys
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from types import ModuleType

import pytest
import reflex_cli
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


def test_current_reflex_base_log_level_is_adopted():
    """With a current reflex-base installed, the shared enum is what the CLI uses.

    The CLI only adopts reflex-base's LogLevel when it carries the API the CLI
    calls. Were that probe ever to reject a current reflex-base, the CLI would
    fork the enum while still forwarding to reflex-base's ``set_log_level``,
    which type-checks against its own class -- so the mainline path is guarded
    here as well as the old-reflex one.
    """
    from reflex_base.constants.base import LogLevel as BaseLogLevel
    from reflex_cli.constants.base import LogLevel

    assert LogLevel is BaseLogLevel


def test_reflex_base_adopts_the_cli_logger_without_being_imported():
    """reflex-base parents reflex_cli itself, so the CLI never has to import it."""
    from reflex_base.utils import log as base_log

    assert "reflex_cli" in base_log.PACKAGE_LOGGER_NAMES


@pytest.mark.parametrize(
    "module",
    [
        "reflex_cli.utils.hosting",
        "reflex_cli.v2.apps",
        "reflex_cli.v2.auth",
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


def test_fallback_progress_bars(capsys):
    """Both progress bars build without reflex-base and render their tasks.

    transfer_progress drives the deploy upload, so it has to work on the reflex
    versions that predate reflex-base like everything else here.
    """
    with _without_reflex_base() as (_, fallback_log, fallback_console):
        # JSON output is a reflex-base pipeline feature; without it there is
        # nothing to stay quiet for, so the bars are never disabled.
        assert fallback_log.is_json_mode() is False

        with fallback_console.progress() as bar:
            bar.add_task("stepping", total=2)
        with fallback_console.transfer_progress() as transfer:
            task = transfer.add_task("uploading", total=1024)
            transfer.update(task, advance=512)

    out = capsys.readouterr().out
    assert "stepping" in out
    assert "uploading" in out


class _OldBaseLogLevel(str, Enum):
    """reflex-base's LogLevel as reflex 0.9.6 shipped it.

    Predates ``to_logging_level`` and the verbosity-ordered comparisons, so a
    CLI that adopts it as its own enum ends up calling methods it lacks.
    """

    DEBUG = "debug"
    DEFAULT = "default"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, level: str | None) -> _OldBaseLogLevel | None:
        """Convert a string to a log level.

        Args:
            level: The log level as a string.

        Returns:
            The log level.
        """
        if not level:
            return None
        try:
            return cls[level.upper()]
        except KeyError:
            return None

    def __le__(self, other: _OldBaseLogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less than or equal to the other log level.
        """
        levels = list(_OldBaseLogLevel)
        return levels.index(self) <= levels.index(other)

    def subprocess_level(self) -> _OldBaseLogLevel:
        """Return the log level for the subprocess.

        Returns:
            The log level for the subprocess.
        """
        return self if self != _OldBaseLogLevel.DEFAULT else _OldBaseLogLevel.WARNING


class _ReflexBaseLogBlocker:
    """Meta path finder that hides ``reflex_base.utils.log`` only."""

    def find_spec(self, fullname: str, path=None, target=None):
        """Refuse to resolve the reflex-base logging pipeline.

        Args:
            fullname: The module being imported.
            path: The parent package's search path.
            target: The module being reloaded, if any.

        Returns:
            None for every other module, deferring to the real finders.

        Raises:
            ImportError: If reflex_base.utils.log is being imported.
        """
        if fullname == "reflex_base.utils.log":
            msg = f"No module named {fullname!r}"
            raise ImportError(msg)
        return


@contextlib.contextmanager
def _with_old_reflex_base() -> Iterator[tuple[ModuleType, ModuleType, ModuleType]]:
    """Import the CLI's logging modules against a reflex 0.9.6 style reflex-base.

    That release ships ``reflex_base.constants.base`` -- so the CLI's optional
    import of the shared LogLevel succeeds -- but no ``reflex_base.utils.log``,
    and its LogLevel predates ``to_logging_level``.

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
    blocker = _ReflexBaseLogBlocker()
    sys.meta_path.insert(0, blocker)
    old_constants_base = ModuleType("reflex_base.constants.base")
    old_constants_base.LogLevel = _OldBaseLogLevel  # pyright: ignore[reportAttributeAccessIssue]
    sys.modules["reflex_base.constants.base"] = old_constants_base
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


def test_old_reflex_base_log_level_is_not_adopted():
    """An enum missing part of the API must not become the CLI's LogLevel.

    reflex 0.9.6 ships a reflex-base whose LogLevel has no
    ``to_logging_level``; adopting it left the CLI calling a method that does
    not exist the moment anything set the log level.
    """
    with _with_old_reflex_base() as (constants_base, fallback_log, _console):
        assert not fallback_log.HAS_REFLEX_BASE
        assert constants_base.LogLevel is not _OldBaseLogLevel
        assert hasattr(constants_base.LogLevel, "to_logging_level")


def test_set_log_level_accepts_an_old_reflex_log_level(capsys):
    """Old reflex hands its own LogLevel straight to the CLI's entrypoints.

    ``reflex deploy`` on 0.9.6 calls ``hosting_cli.deploy(loglevel=...)`` with a
    ``reflex.constants.LogLevel``, so the value never passes through click and
    arrives as a foreign enum rather than a string.
    """
    with _with_old_reflex_base() as (_, _fallback_log, fallback_console):
        fallback_console.set_log_level(_OldBaseLogLevel.WARNING)
        assert logging.getLogger("reflex_cli").level == logging.WARNING

        cli_logger = logging.getLogger("reflex_cli.test")
        cli_logger.info("quiet info")
        cli_logger.warning("loud warning")

    captured = capsys.readouterr().out
    assert "quiet info" not in captured
    assert "loud warning" in captured


@pytest.mark.parametrize("level", list(_OldBaseLogLevel))
def test_every_old_reflex_log_level_maps_across(level: _OldBaseLogLevel):
    """Each member of the old enum resolves to the CLI's own equivalent."""
    with _with_old_reflex_base() as (constants_base, _fallback_log, fallback_console):
        fallback_console.set_log_level(level)
        expected = constants_base.LogLevel(level.value).to_logging_level()
        assert logging.getLogger("reflex_cli").level == expected


def test_loglevel_option_still_offers_every_choice_on_old_reflex_base():
    """The click layer builds ``--loglevel`` from the same enum the CLI adopts.

    Falling back to the fork must not shrink or rename the choices a command
    accepts, or old reflex would start rejecting log levels it used to take.
    """
    with _with_old_reflex_base() as (_, _fallback_log, _console):
        cli_options = importlib.import_module("reflex_cli.utils.cli_options")
        (option,) = cli_options.loglevel_option(lambda: None).__click_params__

        assert list(option.type.choices) == [level.value for level in _OldBaseLogLevel]


@pytest.mark.parametrize(
    "module",
    [
        "reflex_cli.utils.hosting",
        "reflex_cli.v2.apps",
        "reflex_cli.v2.auth",
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
def test_cli_imports_with_old_reflex_base(module: str):
    """Every CLI module imports against a reflex-base that predates its log API."""
    with _with_old_reflex_base():
        importlib.import_module(module)


# A log level handed in from outside may be any reflex's LogLevel, so it is
# only ever safe to pass it to the normalizer. These two are the normalizer
# itself and the sink it forwards to, which is where the type finally holds.
_LOG_LEVEL_NORMALIZERS = {
    ("reflex_cli/utils/console.py", "set_log_level"),
    ("reflex_cli/utils/log.py", "set_log_level"),
}
_LOG_LEVEL_PARAMS = {"loglevel", "log_level"}


def _receives_a_log_level(call: ast.Call) -> bool:
    """Check whether a call is one of the log level normalizers.

    Args:
        call: The call node to inspect.

    Returns:
        True if the callee is a ``set_log_level``, however it is spelled.
    """
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return name == "set_log_level"


def _untrusted_log_level_uses(tree: ast.Module, path: str) -> list[str]:
    """Find reads of a log level parameter that do more than normalize it.

    Args:
        tree: The parsed module.
        path: The module's path, relative to the package source root.

    Returns:
        A ``path:line in function()`` description of every offending read.
    """
    offenders = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (path, func.name) in _LOG_LEVEL_NORMALIZERS:
            continue
        args = func.args
        params = {
            arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
        } & _LOG_LEVEL_PARAMS
        if not params:
            continue
        normalized = {
            id(arg)
            for node in ast.walk(func)
            if isinstance(node, ast.Call) and _receives_a_log_level(node)
            for arg in (*node.args, *(kw.value for kw in node.keywords))
        }
        offenders += [
            f"{path}:{node.lineno} in {func.name}()"
            for node in ast.walk(func)
            if isinstance(node, ast.Name)
            and node.id in params
            and isinstance(node.ctx, ast.Load)
            and id(node) not in normalized
        ]
    return offenders


def test_no_command_trusts_the_log_level_it_is_handed():
    """A log level from outside the package is normalized, never used directly.

    Old reflex calls ``deploy``, ``login``, ``logout`` and ``get_vm_types``
    itself rather than through click, so their ``loglevel`` is whatever enum
    that reflex has -- not necessarily this package's, and not necessarily one
    carrying the API the annotation promises. Passing it to
    ``console.set_log_level`` is safe because that resolves it by value;
    comparing it, calling a method on it or reading ``.value`` off it is not,
    and the type checker cannot tell the difference.
    """
    source_root = Path(reflex_cli.__file__).resolve().parents[1]
    offenders = sorted(
        offender
        for module in sorted(source_root.rglob("reflex_cli/**/*.py"))
        for offender in _untrusted_log_level_uses(
            ast.parse(module.read_text()),
            module.relative_to(source_root).as_posix(),
        )
    )
    assert not offenders, (
        "These read a log level parameter without normalizing it first: "
        f"{offenders}. Pass it to console.set_log_level, which resolves a "
        "foreign reflex's LogLevel by value, and use the result."
    )
