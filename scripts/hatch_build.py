"""Custom build hook for Hatch."""

import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

import tomlkit
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuilder(BuildHookInterface):
    """Custom build hook for Hatch."""

    PLUGIN_NAME = "custom"

    _sdist_directory: tempfile.TemporaryDirectory[str] | None = None

    def prepare_sdist(self, build_data: dict[str, Any]) -> None:
        """Exclude checkout-only workspace references from the source archive.

        Args:
            build_data: Additional build data.
        """
        pyproject = pathlib.Path(self.root) / "pyproject.toml"
        config = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
        uv_config = config.get("tool", {}).get("uv", {})
        uv_config.pop("sources", None)
        uv_config.pop("workspace", None)

        self._sdist_directory = tempfile.TemporaryDirectory(prefix="reflex-sdist-")
        packaged_pyproject = pathlib.Path(self._sdist_directory.name) / "pyproject.toml"
        packaged_pyproject.write_text(tomlkit.dumps(config), encoding="utf-8")
        build_data["force_include"].pop(str(pyproject))
        build_data["force_include"][str(packaged_pyproject)] = "pyproject.toml"

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
        if not isinstance(names, dict):
            return False
        expected = [root / name for name in names if name.startswith("reflex/")]
        return bool(expected) and all(stub.exists() for stub in expected)

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Initialize the build hook.

        Args:
            version: The version being built.
            build_data: Additional build data.
        """
        if self.target_name == "sdist":
            self.prepare_sdist(build_data)

        # An editable install builds against the working tree, so regenerating
        # would replace the developer's stubs with whatever the installing
        # environment resolves to. A fresh checkout has none — they are
        # gitignored — and there the install is what creates them. The marker
        # only records that some earlier build ran, so it cannot vouch for the
        # working tree's stubs.
        if version == "editable":
            if self.stubs_are_complete():
                return
        elif self.marker().exists():
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

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        """Remove the temporary source-archive configuration after building.

        Args:
            version: The version being built.
            build_data: Additional build data.
            artifact_path: The built distribution path.
        """
        if self._sdist_directory is not None:
            self._sdist_directory.cleanup()
            self._sdist_directory = None
