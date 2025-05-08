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

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        """Finalize the build process.

        Args:
            version: The version of the package.
            build_data: The build data.
            artifact_path: The path to the artifact.

        Raises:
            RuntimeError: If the pre-commit patches are not applied correctly.
        """
        if self.marker().exists():
            return

        if importlib.util.find_spec("pre_commit"):
            import pre_commit.constants
            import pre_commit.yaml

            patches = [
                (
                    pre_commit.constants.__file__,
                    """from __future__ import annotations

import importlib.metadata

CONFIG_FILE = '.pre-commit-config.yaml'
MANIFEST_FILE = '.pre-commit-hooks.yaml'

# Bump when modifying `empty_template`
LOCAL_REPO_VERSION = '1'

VERSION = importlib.metadata.version('pre_commit')

DEFAULT = 'default'""",
                    """from __future__ import annotations

import importlib.metadata

CONFIG_FILE = 'pyproject.toml'
MANIFEST_FILE = '.pre-commit-hooks.yaml'

# Bump when modifying `empty_template`
LOCAL_REPO_VERSION = '1'

VERSION = importlib.metadata.version('pre_commit')

DEFAULT = 'default'""",
                ),
                (
                    pre_commit.yaml.__file__,
                    """from __future__ import annotations

import functools
from typing import Any

import yaml

Loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
yaml_compose = functools.partial(yaml.compose, Loader=Loader)
yaml_load = functools.partial(yaml.load, Loader=Loader)
Dumper = getattr(yaml, 'CSafeDumper', yaml.SafeDumper)


def yaml_dump(o: Any, **kwargs: Any) -> str:
    # when python/mypy#1484 is solved, this can be `functools.partial`
    return yaml.dump(
        o, Dumper=Dumper, default_flow_style=False, indent=4, sort_keys=False,
        **kwargs,
    )""",
                    """from __future__ import annotations

import functools
from typing import Any

import yaml
import toml

Loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
yaml_compose = functools.partial(yaml.compose, Loader=Loader)
def yaml_load(stream):
    try:
        return toml.loads(stream).get("tool", {}).get("pre-commit", {})
    except ValueError:
        return yaml.load(stream, Loader=Loader)
Dumper = getattr(yaml, 'CSafeDumper', yaml.SafeDumper)


def yaml_dump(o: Any, **kwargs: Any) -> str:
    # when python/mypy#1484 is solved, this can be `functools.partial`
    return yaml.dump(
        o, Dumper=Dumper, default_flow_style=False, indent=4, sort_keys=False,
        **kwargs,
    )""",
                ),
            ]

            for file, old, new in patches:
                file_path = pathlib.Path(file)
                file_content = file_path.read_text()
                if file_content != new and file_content != old:
                    raise RuntimeError(
                        f"Unexpected content in {file_path}. Did you update pre-commit without updating the patches?"
                    )
                if file_content == old:
                    file_path.write_text(new)

        if not (pathlib.Path(self.root) / "scripts").exists():
            return

        for file in (pathlib.Path(self.root) / "reflex").rglob("**/*.pyi"):
            file.unlink(missing_ok=True)

        subprocess.run(
            [sys.executable, "-m", "reflex.utils.pyi_generator"],
            check=True,
        )
        self.marker().touch()
