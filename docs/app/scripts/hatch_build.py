"""Custom build hook to bundle the parent docs/ tree into the wheel."""

import pathlib
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_BUNDLE_PREFIX = "reflex_docs/_bundled_docs"
_SKIP_TOP_LEVEL = {"app", "scripts", "__pycache__"}


class BundleDocsHook(BuildHookInterface):
    """Force-include the parent docs/ tree into the wheel as bundled package data."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Register every file in the parent docs/ tree as a force-include into the build target.

        Args:
            version: The version being built.
            build_data: Build data dict, mutated to add force-includes.
        """
        if self.target_name not in ("wheel", "sdist"):
            return

        app_root = pathlib.Path(self.root).resolve()
        # When building from an unpacked sdist, the bundle already exists as part
        # of the source tree (and `..` no longer points at the original docs/
        # checkout) — fall through to the default include rules.
        if (app_root / _BUNDLE_PREFIX).is_dir():
            return

        docs_root = app_root.parent
        force_include = build_data.setdefault("force_include", {})
        for child in docs_root.iterdir():
            if child.name.startswith(".") or child.name in _SKIP_TOP_LEVEL:
                continue
            force_include[str(child)] = f"{_BUNDLE_PREFIX}/{child.name}"
