"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from platformdirs import PlatformDirs

if TYPE_CHECKING:
    # The two enums are interchangeable, so the shared one is what gets
    # type-checked; reflex_cli.constants.log_level is checked on its own.
    from reflex_base.constants.base import LogLevel as LogLevel
else:
    # reflex-base only exists from reflex 0.9 on, and the hosting CLI supports
    # older reflex too, so the fork is the baseline and the shared enum is
    # adopted when it is there. Older reflex-base releases predate part of the
    # enum's API, and adopting one of those leaves the CLI calling a method
    # that does not exist, so those keep the fork as well.
    from reflex_cli.constants.log_level import LogLevel as LogLevel

    try:
        from reflex_base.constants.base import LogLevel as _BaseLogLevel
    except ImportError:
        pass
    else:
        if hasattr(_BaseLogLevel, "to_logging_level"):
            LogLevel = _BaseLogLevel


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


class Dirs(SimpleNamespace):
    """Various directories/paths used by the CLI."""

    # The cloud.yaml file.
    CLOUD_YAML = "cloud.yml"
