"""Custom build hook for Hatch."""

import importlib.util
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

        if importlib.util.find_spec("pre_commit") and importlib.util.find_spec("toml"):
            import json

            import toml
            import yaml

            reflex_dir = pathlib.Path(__file__).parent.parent
            pre_commit_config = json.loads(
                json.dumps(
                    toml.load(reflex_dir / "pyproject.toml")["tool"]["pre-commit"]
                )
            )
            (reflex_dir / ".pre-commit-config.yaml").write_text(
                yaml.dump(pre_commit_config), encoding="utf-8"
            )

        if not (pathlib.Path(self.root) / "scripts").exists():
            return

        for file in (pathlib.Path(self.root) / "reflex").rglob("**/*.pyi"):
            file.unlink(missing_ok=True)

        subprocess.run(
            [sys.executable, "-m", "reflex.utils.pyi_generator"],
            check=True,
        )
        self.marker().touch()
