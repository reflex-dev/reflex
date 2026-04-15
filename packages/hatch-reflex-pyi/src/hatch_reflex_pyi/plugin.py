"""Hatch build hook that generates .pyi stub files for Reflex component packages."""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class ReflexPyiBuildHook(BuildHookInterface):
    """Build hook that generates .pyi stubs for component packages."""

    PLUGIN_NAME = "reflex-pyi"

    def _src_dir(self) -> pathlib.Path | None:
        """Find the source directory under src/.

        Returns:
            The source directory path, or None if not found.
        """
        src = pathlib.Path(self.root) / "src"
        if not src.is_dir():
            return None
        children = [
            d for d in src.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
        return children[0] if len(children) == 1 else None

    def _marker(self) -> pathlib.Path:
        """Get the marker file path.

        Returns:
            The marker file path.
        """
        return (
            pathlib.Path(self.directory)
            / f".{self.metadata.name}-{self.metadata.version}.pyi_generated"
        )

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Generate .pyi stubs before the build.

        Args:
            version: The version being built.
            build_data: Additional build data.
        """
        if self._marker().exists():
            return

        src_dir = self._src_dir()
        if src_dir is None:
            return

        try:
            from reflex_base.utils.pyi_generator import PyiGenerator  # noqa: F401
        except ImportError:
            # reflex-base is not installed — skip pyi generation.
            # Pre-generated .pyi files in the sdist will be used.
            return

        for file in src_dir.rglob("*.pyi"):
            file.unlink(missing_ok=True)

        # Run from src/ so _path_to_module_name produces valid import names
        # (e.g. "reflex_components_core.core.banner" instead of
        # "packages.reflex-components-core.src.reflex_components_core.core.banner").
        subprocess.run(
            [sys.executable, "-m", "reflex_base.utils.pyi_generator", src_dir.name],
            cwd=src_dir.parent,
            check=True,
        )
        self._marker().touch()
