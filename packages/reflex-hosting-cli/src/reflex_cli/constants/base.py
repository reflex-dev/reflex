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
    try:
        # reflex-base only exists from reflex 0.9 on, and the hosting CLI
        # supports older reflex too, so its LogLevel is shared when available
        # and forked otherwise.
        from reflex_base.constants.base import LogLevel as LogLevel
    except ImportError:
        from reflex_cli.constants.log_level import LogLevel as LogLevel


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
