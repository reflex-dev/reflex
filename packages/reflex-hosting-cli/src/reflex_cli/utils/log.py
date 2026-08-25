"""Logging pipeline for the hosting CLI, shared with reflex-base when present.

The CLI logs through plain ``logging.getLogger(__name__)`` loggers either way.
Under reflex 0.9 and up, ``reflex_base.utils.log`` already parents ``reflex_cli``
under the ``reflex`` logger and owns the sinks, so this module only forwards to
it. Under older reflex there is no reflex-base to forward to, so the fallback
below renders the ``reflex_cli`` logger itself with the same styles.
"""

from __future__ import annotations

import logging

from reflex_cli.constants.base import LogLevel

try:
    from reflex_base.utils.log import SUCCESS as SUCCESS
    from reflex_base.utils.log import is_json_mode as is_json_mode
    from reflex_base.utils.log import set_log_level as set_log_level

    HAS_REFLEX_BASE = True

except ImportError:
    from rich.console import Console

    HAS_REFLEX_BASE = False

    # Level between INFO and WARNING for user-facing success messages.
    SUCCESS = 25
    logging.addLevelName(SUCCESS, "SUCCESS")

    # (style, prefix) per level, matching the reflex-base console handler.
    _LEVEL_STYLES: dict[int, tuple[str, str]] = {
        logging.DEBUG: ("purple", "Debug: "),
        logging.INFO: ("cyan", "Info: "),
        SUCCESS: ("green", "Success: "),
        logging.WARNING: ("orange1", "Warning: "),
        logging.ERROR: ("red", ""),
        logging.CRITICAL: ("red", ""),
    }

    _console = Console(highlight=False)
    _console_stderr = Console(stderr=True, highlight=False)

    # Formatter kept only for its exception rendering, which is stateless.
    _EXC_FORMATTER = logging.Formatter()

    _CLI_LOGGER = logging.getLogger("reflex_cli")

    def is_json_mode() -> bool:
        """Check whether logs should be emitted as JSON records.

        Returns:
            False: machine-readable output is a reflex-base feature, driven by
            REFLEX_LOG_JSON, and there is no pipeline here to emit it.
        """
        return False

    def _style_for_level(levelno: int) -> tuple[str, str]:
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

    class RichConsoleHandler(logging.Handler):
        """Render log records with rich, matching the reflex-base look."""

        def emit(self, record: logging.LogRecord):
            """Print a record to the terminal.

            Args:
                record: The log record.
            """
            try:
                style, prefix = _style_for_level(record.levelno)
                console = (
                    _console_stderr if record.levelno >= logging.ERROR else _console
                )
                # Markup is opt-in per record (``extra={"rich": True}``); plain
                # messages keep their literal brackets.
                markup = bool(getattr(record, "rich", False))
                console.print(
                    f"{prefix}{record.getMessage()}",
                    style=style,
                    end=getattr(record, "end", "\n"),
                    markup=markup,
                )
                if record.exc_info and record.exc_info[0] is not None:
                    # Tracebacks may contain user data; never parse them as
                    # markup. Never word-wrap them either: that breaks paths.
                    console.print(
                        _EXC_FORMATTER.formatException(record.exc_info),
                        style=style,
                        markup=False,
                        soft_wrap=True,
                    )
            except Exception:
                self.handleError(record)

    _handler = RichConsoleHandler()

    def set_log_level(log_level: LogLevel | None):
        """Set the log level and attach the CLI's console sink.

        Args:
            log_level: The log level to set, or None to leave it unchanged.

        Raises:
            TypeError: If the log level is not a LogLevel enum value.
        """
        if log_level is None:
            return
        if not isinstance(log_level, LogLevel):
            msg = f"log_level must be a LogLevel enum value, got {log_level} of type {type(log_level)} instead."
            raise TypeError(msg)
        _handler.setLevel(log_level.to_logging_level())
        _CLI_LOGGER.setLevel(log_level.to_logging_level())
        # Cut propagation while the sink is attached, so an application-side
        # basicConfig cannot double-emit the CLI's records. addHandler is a
        # no-op when the handler is already attached, so this stays idempotent.
        _CLI_LOGGER.propagate = False
        _CLI_LOGGER.addHandler(_handler)
