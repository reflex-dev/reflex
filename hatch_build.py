"""Custom build hook for Hatch."""

import glob
import pathlib
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuilder(BuildHookInterface):
    """Custom build hook for Hatch."""

    PLUGIN_NAME = "custom"

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        print("Custom build hook")
        print(f"Version: {version}")
        print(f"Build data: {build_data}")
        print(f"Artifact path: {artifact_path}")
        print(f"Root path: {self.root}")

        if not (pathlib.Path(self.root) / "scripts").exists():
            return

        for file in pathlib.Path(self.root).rglob("**/*.pyi"):
            print(file)
            file.unlink(missing_ok=True)

        import subprocess

        p = subprocess.run(
            ["python", "-m", "scripts.make_pyi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
        )
        print(p.returncode)
        print(p.stderr)
        print(p.stdout)
        if p.returncode != 0:
            raise RuntimeError("Failed to generate .pyi files")

        for file in pathlib.Path(self.root).rglob("**/*.pyi"):
            print(file)
