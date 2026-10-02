"""Custom build hook to bundle markdown docs from the parent docs/ tree into the wheel."""

import pathlib
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_BUNDLE_PREFIX = "reflex_docs_bundle/_docs"
_SKIP_TOP_LEVEL = {"app", "package", "__pycache__"}


class BundleDocsHook(BuildHookInterface):
    """Force-include markdown files from the parent docs/ tree into the build target as bundled package data."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Register every markdown file in the parent docs/ tree as a force-include into the build target.

        Args:
            version: The version being built.
            build_data: Build data dict, mutated to add force-includes.
        """
        if self.target_name not in ("wheel", "sdist"):
            return

        pkg_root = pathlib.Path(self.root).resolve()
        # When building from an unpacked sdist, the bundle already exists as part
        # of the source tree (and `..` no longer points at the original docs/
        # checkout) — fall through to the default include rules.
        if (pkg_root / _BUNDLE_PREFIX).is_dir():
            return

        docs_root = pkg_root.parent
        force_include = build_data.setdefault("force_include", {})
        for top in docs_root.iterdir():
            if top.name.startswith(".") or top.name in _SKIP_TOP_LEVEL:
                continue
            md_files = (
                [top] if top.is_file() and top.suffix == ".md" else top.rglob("*.md")
            )
            for md in md_files:
                rel = md.relative_to(docs_root).as_posix()
                force_include[str(md)] = f"{_BUNDLE_PREFIX}/{rel}"
