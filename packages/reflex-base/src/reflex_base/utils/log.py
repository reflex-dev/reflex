"""Standard-library logging pipeline with rich rendering and JSON output.

Reflex modules log through plain ``logging.getLogger(__name__)`` loggers.
When this module first loads (``reflex_base.utils.console`` imports it at
module scope, so that happens the moment reflex does anything) :func:`bootstrap`
parents every workspace package logger (``reflex_base``, ``reflex_cli``,
``reflex_components_*``) under the single ``reflex`` logger, so downstream
code tunes all reflex logging in one place
(``logging.getLogger("reflex")``) or per package, with standard stdlib APIs.

Handlers attach only in *managed* mode, i.e. when running under the reflex
CLI (or one of its worker subprocesses, which inherit the marker through the
environment). The sinks are: a rich-rendering console handler (colored, same
look as the legacy ``console`` helpers), a JSON-lines handler for machine
consumption (``REFLEX_LOG_JSON`` / ``--json``), and an optional file handler
(``REFLEX_ENABLE_FULL_LOGGING`` / ``REFLEX_LOG_FILE``). Outside the CLI no
handler is attached at all: records propagate to the root logger and the
application's own logging configuration (or ``logging.lastResort``) applies.
"""

from __future__ import annotations

import contextlib
import datetime
import functools
import json
import logging
import os
import shutil
import sys
import time
from collections.abc import Generator
from pathlib import Path
from types import FrameType, ModuleType
from typing import TYPE_CHECKING, cast

from rich.console import Console
from rich.errors import MarkupError
from rich.text import Text

from reflex_base.constants import LogLevel
from reflex_base.constants.base import Reflex
from reflex_base.utils.decorator import once

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterator
    from typing import TextIO

# Level between INFO and WARNING for user-facing success messages.
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

# Package-root loggers reparented under the top-level ``reflex`` logger.
# Every distribution that logs needs its root here: loggers do not propagate
# across the ``reflex_*`` top-level names, so an omitted root escapes the
# hierarchy entirely (no level gating, no reflex sinks, no file capture).
PACKAGE_LOGGER_NAMES = (
    "reflex_base",
    "reflex_cli",
    "reflex_components_core",
    "reflex_components_dataeditor",
    "reflex_components_lucide",
    "reflex_components_plotly",
    "reflex_components_react_player",
)

# The single logger the reflex sinks attach to; parent of every package logger.
_REFLEX_LOGGER = logging.getLogger("reflex")

# Marker inherited by worker subprocesses: handlers attach only when running
# under the reflex CLI. Read with os.environ so bootstrap stays import-light.
_MANAGED_ENV_VAR = "REFLEX_MANAGED_LOGGING"

# Consoles for pretty printing (shared with reflex_base.utils.console).
_console = Console(highlight=False)
_console_stderr = Console(stderr=True, highlight=False)

# Console that renders nowhere, backing interactive rich features in JSON mode.
_quiet_console = Console(quiet=True)

# The current log level.
_log_level = LogLevel.INFO

# Formatter kept only for its exception rendering, which is stateless.
_EXC_FORMATTER = logging.Formatter()

# (style, prefix) per level for the rich console sink.
_LEVEL_STYLES: dict[int, tuple[str, str]] = {
    logging.DEBUG: ("purple", "Debug: "),
    logging.INFO: ("cyan", "Info: "),
    SUCCESS: ("green", "Success: "),
    logging.WARNING: ("orange1", "Warning: "),
    logging.ERROR: ("red", ""),
    logging.CRITICAL: ("red", ""),
}

# Style and prefix for records carrying ``kind="deprecation"``.
DEPRECATION_STYLE = ("yellow", "DeprecationWarning: ")


def style_for_level(levelno: int) -> tuple[str, str]:
    """Resolve the rich style and message prefix for a log level.

    Args:
        levelno: The stdlib logging level number.

    Returns:
        A (style, prefix) tuple.
    """
    levelno = min(logging.CRITICAL, max(logging.DEBUG, levelno))
    # Round down to the nearest known level.
    while levelno not in _LEVEL_STYLES:
        levelno -= 1
    return _LEVEL_STYLES[levelno]


def _style_for(record: logging.LogRecord) -> tuple[str, str]:
    """Resolve the rich style and message prefix for a record.

    Args:
        record: The log record being rendered.

    Returns:
        A (style, prefix) tuple.
    """
    if getattr(record, "kind", None) == "deprecation":
        return DEPRECATION_STYLE
    return style_for_level(record.levelno)


def strip_markup(msg: str) -> str:
    """Remove rich markup tags from a message.

    Args:
        msg: The message, possibly containing rich markup.

    Returns:
        The plain-text message.
    """
    if "[" not in msg:
        return msg
    try:
        return Text.from_markup(msg).plain
    except MarkupError:
        return msg


class DedupeFilter(logging.Filter):
    """Drop repeat records that opted into deduplication."""

    def __init__(self):
        """Initialize the filter with an empty seen-set."""
        super().__init__()
        # Hashes only, so deduped messages are not retained for the process
        # lifetime.
        self.seen: set[int] = set()

    def register(self, key: Hashable) -> bool:
        """Record a dedupe key, reporting whether it is new.

        Args:
            key: A hashable dedupe key.

        Returns:
            True the first time the key is seen, False afterwards.
        """
        hashed = hash(key)
        if hashed in self.seen:
            return False
        self.seen.add(hashed)
        return True

    def filter(self, record: logging.LogRecord) -> bool:
        """Decide whether a record should be emitted.

        Args:
            record: The log record.

        Returns:
            False if an identical record was already emitted with dedupe set.
        """
        key = getattr(record, "dedupe_key", None)
        if key is None:
            if not getattr(record, "dedupe", False):
                return True
            key = (record.levelno, record.getMessage())
        return self.register(key)


class RichConsoleHandler(logging.Handler):
    """Render log records with rich, matching the legacy console look."""

    def emit(self, record: logging.LogRecord):
        """Print a record to the terminal.

        Args:
            record: The log record.
        """
        try:
            style, prefix = _style_for(record)
            console = _console_stderr if record.levelno >= logging.ERROR else _console
            # Records may carry a rich Progress to print through, so the
            # message lands above an active progress bar.
            progress = getattr(record, "progress", None)
            if progress is not None:
                console = progress.console
            end = getattr(record, "end", "\n")
            # Markup is opt-in per record (``extra={"rich": True}``); plain
            # messages keep their literal brackets.
            markup = bool(getattr(record, "rich", False))
            console.print(
                f"{prefix}{record.getMessage()}", style=style, end=end, markup=markup
            )
            if record.exc_info and record.exc_info[0] is not None:
                # Tracebacks may contain user data; never parse them as markup.
                # Never word-wrap them either: wrapping breaks file paths.
                console.print(
                    self.format_exception(record),
                    style=style,
                    markup=False,
                    soft_wrap=True,
                )
        except Exception:
            self.handleError(record)

    def format_exception(self, record: logging.LogRecord) -> str:
        """Format a record's exception info as text.

        Args:
            record: The log record with exc_info set.

        Returns:
            The formatted traceback.
        """
        return _EXC_FORMATTER.formatException(record.exc_info)  # pyright: ignore[reportArgumentType]


def _write_json(payload: dict, *, stderr: bool):
    """Write one JSON record to the output stream.

    Args:
        payload: The record fields.
        stderr: Whether the record targets stderr.
    """
    stream = sys.stderr if stderr else sys.stdout
    stream.write(json.dumps(payload, default=str) + "\n")
    stream.flush()


class JsonHandler(logging.Handler):
    """Emit one JSON object per record for machine consumption."""

    extra_fields = (
        "feature_name",
        "deprecation_version",
        "removal_version",
        "kind",
    )

    def emit(self, record: logging.LogRecord):
        """Write a record as a JSON line to stdout or stderr.

        Args:
            record: The log record.
        """
        try:
            message = record.getMessage()
            if getattr(record, "rich", False):
                message = strip_markup(message)
            payload = {
                "timestamp": datetime.datetime.fromtimestamp(
                    record.created, tz=datetime.timezone.utc
                ).isoformat(),
                "level": logging.getLevelName(record.levelno).lower(),
                "logger": record.name,
                "message": message,
                # Records may carry an explicit location (e.g. deprecations
                # point at the user call site, not the framework frame).
                "location": getattr(record, "location", None)
                or f"{record.pathname}:{record.lineno}",
                "pid": record.process,
            }
            for field in self.extra_fields:
                value = getattr(record, field, None)
                if value is not None:
                    payload[field] = value
            if record.exc_info and record.exc_info[0] is not None:
                payload["exception"] = _EXC_FORMATTER.formatException(
                    record.exc_info  # pyright: ignore[reportArgumentType]
                )
            _write_json(payload, stderr=record.levelno >= logging.ERROR)
        except Exception:
            self.handleError(record)


class _FileFormatter(logging.Formatter):
    """Formatter that removes rich markup from markup-enabled messages."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a record, stripping markup from records that opted into it.

        Args:
            record: The log record.

        Returns:
            The formatted line.
        """
        if not getattr(record, "rich", False):
            return super().format(record)
        msg, args = record.msg, record.args
        try:
            record.msg = strip_markup(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.msg, record.args = msg, args


def _log_file_path() -> Path:
    """Resolve the path of the full-logging file.

    Returns:
        The log file path (parent directory created).
    """
    from reflex_base.environment import environment

    if not (log_file := environment.REFLEX_LOG_FILE.get()):
        subseconds = int((time.time() % 1) * 1000)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S") + f"_{subseconds:03d}"
        log_file = Reflex.DIR / "logs" / (timestamp + ".log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    return log_file


@once
def _file_handler() -> logging.FileHandler:
    """Create the full-logging file handler.

    The file is truncated up front and the handler opened in append mode:
    appended writes land atomically at the end of the file, and a closed
    handler reopens on the next record — the stdlib refuses to reopen only
    ``mode="w"`` handlers. Both matter in granian workers, whose post-fork
    ``logging.config.dictConfig`` closes every fork-inherited handler.

    Returns:
        A file handler writing every record with markup stripped.
    """
    path = _log_file_path()
    path.write_bytes(b"")
    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setFormatter(
        _FileFormatter("[{asctime}] {levelname}: {message}", style="{")
    )
    return handler


@contextlib.contextmanager
def log_file_stream() -> Generator[TextIO]:
    """Return the live stream of the full-logging file, reopening if needed.

    An external ``logging.config.dictConfig`` (granian runs one in each
    worker process) closes every existing handler; reopen the file in append
    mode rather than handing writers a dead stream.

    Yields:
        The writable stream of the full-logging file.
    """
    handler = _file_handler()
    handler.acquire()
    try:
        stream = handler.stream
        if stream is None:
            # FileHandler._open is private stdlib API, but it is the only way
            # to reopen the file with the handler's own mode/encoding, and
            # FileHandler.emit itself reopens a closed handler the same way.
            stream = handler.stream = handler._open()
        yield cast("TextIO", stream)
    finally:
        handler.release()


class _LogFileStreamProxy:
    """Writable file-like object always targeting the live log-file stream.

    Long-lived writers (the legacy console file writer) hold this proxy
    instead of a raw stream, so they stay valid when an external logging
    re-config closes the file handler and the pipeline reopens it.
    """

    __slots__ = ()

    def write(self, text: str) -> int:
        """Write to the current log-file stream.

        Args:
            text: The text to write.

        Returns:
            The number of characters written.
        """
        with log_file_stream() as stream:
            return stream.write(text)

    def flush(self):
        """Flush the current log-file stream."""
        with log_file_stream() as stream:
            stream.flush()

    def isatty(self) -> bool:
        """Report that the log file is not a terminal.

        Returns:
            False.
        """
        return False


_LOG_FILE_PROXY = _LogFileStreamProxy()


def log_file_proxy() -> TextIO:
    """Return a stable writable proxy for the full-logging file.

    Returns:
        A file-like object resolving the live stream on every write.
    """
    return cast("TextIO", _LOG_FILE_PROXY)


@once
def _console_handler() -> RichConsoleHandler:
    """Create the rich console handler.

    Returns:
        The handler, with the dedupe filter attached.
    """
    handler = RichConsoleHandler()
    handler.addFilter(_dedupe_filter())
    return handler


@once
def _json_handler() -> JsonHandler:
    """Create the JSON-lines handler.

    Returns:
        The handler, with the dedupe filter attached.
    """
    handler = JsonHandler()
    handler.addFilter(_dedupe_filter())
    return handler


@once
def _dedupe_filter() -> DedupeFilter:
    """Create the shared dedupe filter.

    Returns:
        The dedupe filter used by the console and JSON handlers.
    """
    return DedupeFilter()


def is_json_mode() -> bool:
    """Check whether logs should be emitted as JSON records.

    Returns:
        True if REFLEX_LOG_JSON is enabled.
    """
    from reflex_base.environment import environment

    return environment.REFLEX_LOG_JSON.get()


def set_json_mode(enabled: bool):
    """Enable or disable machine-readable JSON log output.

    Sets the environment variable so subprocesses inherit the mode, then
    re-attaches the sinks (in managed mode; outside the CLI no sink exists).

    Args:
        enabled: Whether to emit JSON records.
    """
    from reflex_base.environment import environment

    environment.REFLEX_LOG_JSON.set(enabled)
    if is_managed_mode():
        configure()


def dedupe_once(key: Hashable) -> bool:
    """Register a dedupe key, reporting whether it is new.

    Args:
        key: A hashable dedupe key.

    Returns:
        True the first time the key is seen, False afterwards.
    """
    return _dedupe_filter().register(key)


def emit_json_print(
    msg: str,
    *,
    level: str = "info",
    dedupe: bool = False,
    stderr: bool = False,
    **fields,
):
    """Emit a plain console message as a JSON record.

    Used by ``console.print`` in JSON mode so the output stream stays
    machine-readable. Not routed through a logger: plain prints are not
    level-gated.

    Args:
        msg: The message.
        level: The severity to report, matching the calling console helper.
        dedupe: If True, suppress repeats of the same message.
        stderr: Whether the message targets stderr.
        fields: Extra fields to include in the record.
    """
    if dedupe and not dedupe_once(("print", msg)):
        return
    _write_json(
        {
            # Extras first: the canonical fields below always win.
            **fields,
            "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "level": level,
            "logger": "reflex.console",
            "message": strip_markup(msg),
            "pid": os.getpid(),
        },
        stderr=stderr,
    )


_configured = False
_active_file_handler: logging.FileHandler | None = None


def is_managed_mode() -> bool:
    """Check whether this process runs under the reflex CLI.

    Returns:
        True if the reflex CLI (or a worker it spawned) owns log rendering.
    """
    return os.environ.get(_MANAGED_ENV_VAR) == "true"


def enable_managed_logging():
    """Mark this process (and its subprocesses) as CLI-managed and attach sinks.

    Called from the reflex CLI entry point. Worker subprocesses inherit the
    marker through the environment and attach their sinks through
    ensure_configured() once configuration is loaded.
    """
    os.environ[_MANAGED_ENV_VAR] = "true"
    configure()


def bootstrap():
    """Parent the package loggers under the top-level ``reflex`` logger.

    Runs at the bottom of this module, so importing the pipeline is enough to
    fix up the hierarchy. The manual parent assignment is permanent: the
    logging manager only fixes up parents when it creates a logger, and
    loggers created later under a package root chain to the existing root.
    Sinks are never attached here: that needs :mod:`reflex_base.environment`
    (and with it the component tree), which is not safe to import from
    within this module's own import. Managed processes attach them through
    :func:`enable_managed_logging` (the CLI) or :func:`ensure_configured`
    (workers, from ``get_config``).
    """
    for name in PACKAGE_LOGGER_NAMES:
        child = logging.getLogger(name)
        child.parent = _REFLEX_LOGGER
        # Re-set the level a logger already has: that leaves an application's
        # own configuration untouched while clearing the isEnabledFor caches,
        # which reparenting alone does not do.
        child.setLevel(child.level)


def configure():
    """Attach the reflex sinks to the top-level ``reflex`` logger.

    Idempotent: handler instances are cached and re-attached, never stacked.
    Propagation to the root logger is cut while the sinks are attached, so an
    application-side ``basicConfig`` cannot double-emit reflex records or
    break the ``--json`` only-JSON output contract.
    """
    global _active_file_handler, _configured
    from reflex_base.environment import environment

    json_mode = environment.REFLEX_LOG_JSON.get()
    sink, other = (
        (_json_handler(), _console_handler())
        if json_mode
        else (_console_handler(), _json_handler())
    )
    sink.setLevel(_log_level.to_logging_level())
    full_logging = environment.REFLEX_ENABLE_FULL_LOGGING.get()
    file_handler = _active_file_handler
    if full_logging:
        file_handler = _active_file_handler = _file_handler()
    # addHandler/removeHandler are no-ops when the handler is already in the
    # desired state, so no membership checks are needed here.
    _REFLEX_LOGGER.propagate = False
    _REFLEX_LOGGER.setLevel(
        logging.DEBUG if full_logging else _log_level.to_logging_level()
    )
    _REFLEX_LOGGER.removeHandler(other)
    _REFLEX_LOGGER.addHandler(sink)
    if file_handler is not None:
        if full_logging:
            _REFLEX_LOGGER.addHandler(file_handler)
        else:
            _REFLEX_LOGGER.removeHandler(file_handler)
    _configured = True


def ensure_configured():
    """Attach the sinks in managed mode if that has not happened yet.

    Outside the CLI this is a no-op: no handler is attached and records
    propagate to the root logger for the application to handle.
    """
    if not _configured and is_managed_mode():
        configure()


def _reset():
    """Detach the sinks and restore propagation (test teardown helper)."""
    global _configured
    for handler in (_console_handler(), _json_handler(), _active_file_handler):
        if handler is not None:
            _REFLEX_LOGGER.removeHandler(handler)
    _REFLEX_LOGGER.propagate = True
    _REFLEX_LOGGER.setLevel(logging.NOTSET)
    _configured = False


def set_log_level(log_level: LogLevel | None):
    """Set the log level.

    Args:
        log_level: The log level to set.

    Raises:
        TypeError: If the log level is not a LogLevel enum value.
    """
    if log_level is None:
        return
    if not isinstance(log_level, LogLevel):
        msg = f"log_level must be a LogLevel enum value, got {log_level} of type {type(log_level)} instead."
        raise TypeError(msg)
    global _log_level
    if log_level != _log_level:
        # Set the loglevel persistently for subprocesses.
        os.environ["REFLEX_LOGLEVEL"] = log_level.value
    _log_level = log_level
    if is_managed_mode():
        configure()
    else:
        # Library mode: adjust the level like any stdlib API would, but never
        # attach handlers behind the application's back.
        _REFLEX_LOGGER.setLevel(log_level.to_logging_level())


def get_log_level() -> LogLevel:
    """Get the current log level.

    Returns:
        The current log level.
    """
    return _log_level


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _log_level <= LogLevel.DEBUG


@contextlib.contextmanager
def timing(logger: logging.Logger, msg: str) -> Iterator[None]:
    """Time a block of code and log the duration at debug level.

    Args:
        logger: The logger to emit the timing record on.
        msg: The message to display.

    Yields:
        None.
    """
    start = time.time()
    try:
        yield
    finally:
        logger.debug("[timing] %s: %.2fs", msg, time.time() - start)


@once
def _exclude_paths_from_frame_info() -> list[Path]:
    import importlib.util

    import click
    import granian
    import socketio
    import typing_extensions

    import reflex_base

    try:
        import reflex as rx
    except ImportError:
        rx = None

    # Exclude utility modules that should never be the source of deprecated reflex usage.
    exclude_modules: list[ModuleType | None] = [
        click,
        rx,
        typing_extensions,
        socketio,
        granian,
        reflex_base,
    ]

    modules_paths = [file for m in exclude_modules if m and (file := m.__file__)] + [
        spec.origin
        for m in [*sys.builtin_module_names, *sys.stdlib_module_names]
        if (spec := importlib.util.find_spec(m)) and spec.origin
    ]
    exclude_roots = [
        p.parent.resolve() if (p := Path(file)).name == "__init__.py" else p.resolve()
        for file in modules_paths
    ]
    # Specifically exclude the reflex cli module.
    if reflex_bin := shutil.which(b"reflex"):
        exclude_roots.append(Path(reflex_bin.decode()))

    return exclude_roots


@functools.cache
def _is_framework_filename(filename: str) -> bool:
    """Check if a code filename belongs to an excluded framework/stdlib root.

    Cached per filename: module file locations do not move within a process,
    but resolving a path and comparing it against every exclude root is far
    too expensive to repeat for each frame on every deprecation check.

    Args:
        filename: The ``co_filename`` of a frame's code object.

    Returns:
        Whether the file lives under one of the excluded framework roots.
    """
    frame_path = Path(filename).resolve()
    return any(
        frame_path.is_relative_to(root) for root in _exclude_paths_from_frame_info()
    )


def _get_first_non_framework_frame() -> FrameType | None:
    frame = sys._getframe()
    while frame := frame and frame.f_back:
        if not _is_framework_filename(frame.f_code.co_filename):
            break
    return frame


_deprecation_logger = logging.getLogger("reflex.deprecation")


def deprecate(
    *,
    feature_name: str,
    reason: str,
    deprecation_version: str,
    removal_version: str,
    dedupe: bool = True,
    **kwargs,
):
    """Log a deprecation warning.

    Args:
        feature_name: The feature to deprecate.
        reason: The reason for deprecation.
        deprecation_version: The version the feature was deprecated
        removal_version: The version the deprecated feature will be removed
        dedupe: If True, suppress multiple warnings of the same deprecation.
        kwargs: Ignored legacy print kwargs.
    """
    del kwargs
    dedupe_key = feature_name
    loc = ""
    user_location = None

    # See if we can find where the deprecation exists in "user code"
    origin_frame = _get_first_non_framework_frame()
    if origin_frame is not None:
        filename = Path(origin_frame.f_code.co_filename)
        cwd = Path.cwd()
        if filename.is_relative_to(cwd):
            filename = filename.relative_to(cwd)
        user_location = f"{filename}:{origin_frame.f_lineno}"
        loc = f" ({user_location})"
        dedupe_key = f"{dedupe_key} {loc}"

    # Claim the key up front so repeat warnings skip formatting and emission
    # entirely, rather than building a record for the filter to drop.
    if dedupe and not dedupe_once(f"deprecation:{dedupe_key}"):
        return

    msg = (
        f"{feature_name} has been deprecated in version {deprecation_version}. {reason.rstrip('.').lstrip('. ')}. It will be completely "
        f"removed in {removal_version}.{loc}"
    )
    _deprecation_logger.warning(
        msg,
        extra={
            "kind": "deprecation",
            "feature_name": feature_name,
            "deprecation_version": deprecation_version,
            "removal_version": removal_version,
            # Machine consumers need the user call site, not this frame.
            "location": user_location,
        },
    )


# Reparenting is permanent, so it happens the moment the pipeline loads —
# keeping ``import reflex`` itself free of this module (and rich).
bootstrap()
