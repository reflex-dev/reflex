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
        the full set; without it, treat the stubs as incomplete and regenerate.

        Returns:
            Whether every expected stub exists.
        """
        root = pathlib.Path(self.root)
        hashes = root / "pyi_hashes.json"
        if not hashes.exists():
            return False
        expected = [
            root / name
            for name in json.loads(hashes.read_text())
            if name.startswith("reflex/")
        ]
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
