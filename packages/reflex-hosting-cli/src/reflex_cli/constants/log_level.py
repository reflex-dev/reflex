"""The hosting CLI's own LogLevel, used when reflex-base is not installed.

reflex-base only exists from reflex 0.9 on, but the hosting CLI supports older
reflex too. :mod:`reflex_cli.constants.base` prefers the reflex-base enum when
it is importable and falls back to this one otherwise; the two are
interchangeable, with the same members and the same string values.
"""

from __future__ import annotations

import logging
from enum import Enum


class LogLevel(str, Enum):
    """The log levels."""

    DEBUG = "debug"
    DEFAULT = "default"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, level: str | None) -> LogLevel | None:
        """Convert a string to a log level.

        Args:
            level: The log level as a string.

        Returns:
            The log level, or None if the string names no level.
        """
        if not level:
            return None
        try:
            return cls[level.upper()]
        except KeyError:
            return None

    def to_logging_level(self) -> int:
        """Map this level to a stdlib logging level number.

        DEFAULT acts as a threshold equivalent to INFO.

        Returns:
            The stdlib logging level.
        """
        return _LOGGING_LEVELS[self]

    def subprocess_level(self) -> LogLevel:
        """Return the log level to hand to a subprocess.

        Returns:
            This level, or WARNING when it is DEFAULT.
        """
        return self if self != LogLevel.DEFAULT else LogLevel.WARNING

    # The str mixin supplies alphabetical comparisons, so all four operators
    # must be overridden to compare by verbosity rank instead.
    def __lt__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less verbose than the other log level.
        """
        return _LOG_LEVEL_RANK[self] < _LOG_LEVEL_RANK[other]

    def __le__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less than or equal to the other log level.
        """
        return _LOG_LEVEL_RANK[self] <= _LOG_LEVEL_RANK[other]

    def __gt__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is more verbose-restrictive than the other.
        """
        return _LOG_LEVEL_RANK[self] > _LOG_LEVEL_RANK[other]

    def __ge__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is greater than or equal to the other.
        """
        return _LOG_LEVEL_RANK[self] >= _LOG_LEVEL_RANK[other]


_LOG_LEVEL_RANK = {level: rank for rank, level in enumerate(LogLevel)}
_LOGGING_LEVELS = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.DEFAULT: logging.INFO,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}
