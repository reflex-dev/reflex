"""Custom build hook for Hatch."""

import pathlib
import subprocess
import sys
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuilder(BuildHookInterface):
    """Custom build hook for Hatch."""

    PLUGIN_NAME = "custom"

    def marker(self) -> pathlib.Path:
        """Get the marker file path.

        Returns:
            The marker file path.
        """
        return (
            pathlib.Path(self.directory)
            / f".reflex-{self.metadata.version}.pyi_generated"
        )

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Initialize the build hook.

        Args:
            version: The version being built.
            build_data: Additional build data.
        """
        if self.marker().exists():
            return

        if not (pathlib.Path(self.root) / "scripts").exists():
            return

        for file in (pathlib.Path(self.root) / "reflex").rglob("**/*.pyi"):
            file.unlink(missing_ok=True)

        subprocess.run(
            [sys.executable, "-m", "reflex_base.utils.pyi_generator"],
            check=True,
        )
        self.marker().touch()
