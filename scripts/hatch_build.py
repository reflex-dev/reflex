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
        """
        if self.marker().exists():
            return

        if importlib.util.find_spec("pre_commit"):
            import pre_commit.yaml
            from diff_match_patch import diff_match_patch

            patch = """@@ -82,16 +82,28 @@
 ort yaml
+%0Aimport toml
 %0A%0ALoader
@@ -209,24 +209,28 @@
 der=Loader)%0A
+def 
 yaml_load = 
@@ -226,37 +226,145 @@
 aml_load
- = functools.partial(
+(stream):%0A    try:%0A        return toml.loads(stream).get(%22tool%22, %7B%7D).get(%22pre-commit%22, %7B%7D)%0A    except ValueError:%0A        return 
 yaml.loa
@@ -364,16 +364,23 @@
 aml.load
+(stream
 , Loader
"""  # noqa: W291

            dmp = diff_match_patch()
            patches = dmp.patch_fromText(patch)
            new_text, _ = dmp.patch_apply(
                patches, pathlib.Path(pre_commit.yaml.__file__).read_text()
            )
            pathlib.Path(pre_commit.yaml.__file__).write_text(new_text)

        if not (pathlib.Path(self.root) / "scripts").exists():
            return

        for file in (pathlib.Path(self.root) / "reflex").rglob("**/*.pyi"):
            file.unlink(missing_ok=True)

        subprocess.run(
            [sys.executable, "-m", "reflex.utils.pyi_generator"],
            check=True,
        )
        self.marker().touch()
