"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

from types import SimpleNamespace

from platformdirs import PlatformDirs
from reflex_base.constants.base import LogLevel as LogLevel


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
