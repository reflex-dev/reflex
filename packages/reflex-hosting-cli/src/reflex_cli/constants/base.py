"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

from platformdirs import PlatformDirs


class Reflex(SimpleNamespace):
    """Base constants concerning Reflex. This is duplicate of the same class in reflex main."""

    # The name of the Reflex package.
    MODULE_NAME = "reflex"

    # Files and directories used to init a new project.
    # The directory to store reflex dependencies.
    DIR = (
        # on windows, we use C:/Users/<username>/AppData/Local/reflex.
        # on macOS, we use ~/Library/Application Support/reflex.
        # on linux, we use ~/.local/share/reflex.
        PlatformDirs(MODULE_NAME, False).user_data_dir
    )


# Log levels
class LogLevel(str, Enum):
    """The log levels."""

    DEBUG = "debug"
    DEFAULT = "default"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def __le__(self, other: LogLevel | str) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less than or equal to the other log level.

        """
        if isinstance(other, str):
            other = LogLevel(other.lower().strip())
        levels = list(LogLevel)
        return levels.index(self) <= levels.index(other)


class Dirs(SimpleNamespace):
    """Various directories/paths used by the CLI."""

    # The cloud.yaml file.
    CLOUD_YAML = "cloud.yml"
