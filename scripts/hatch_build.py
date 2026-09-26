"""Custom build hook for Hatch."""

import json
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

    def stubs_are_complete(self) -> bool:
        """Report whether every stub this package ships is already present.

        The generator logs and skips a module it cannot import, so a failed run
        can leave some stubs written and others missing. `pyi_hashes.json` names
        the full set.

        Returns:
            Whether every expected stub exists.
        """
        root = pathlib.Path(self.root)
        try:
            names = json.loads((root / "pyi_hashes.json").read_text())
        except (OSError, ValueError):
            # Absent, unreadable, or half-written by an interrupted generator
            # run, which writes it in place. Regenerate rather than fail here.
            return False
        expected = [root / name for name in names if name.startswith("reflex/")]
        return bool(expected) and all(stub.exists() for stub in expected)

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Initialize the build hook.

        Args:
            version: The version being built.
            build_data: Additional build data.
        """
        # An editable install builds against the working tree, so regenerating
        # would replace the developer's stubs with whatever the installing
        # environment resolves to. A fresh checkout has none — they are
        # gitignored — and there the install is what creates them.
        if version == "editable" and self.stubs_are_complete():
            return

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
