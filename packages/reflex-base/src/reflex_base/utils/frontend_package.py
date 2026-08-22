"""Locate and describe the bundled Reflex frontend npm package.

The frontend runtime ships with reflex-base in one of two forms: editable/dev
installs carry the live JS source directory (``reflex_base/frontend/``), while
wheels carry a packed npm tarball built by the reflex-base build hook. This
module is the single source of truth for which form is present and for the
package's manifest (name, version, dependency declarations) — it replaces the
frontend dependency lists that used to be maintained in Python constants.
"""

import dataclasses
import enum
import functools
import json
import tarfile
from pathlib import Path

from reflex_base.utils.exceptions import ReflexError


class FrontendPackageMissingError(ReflexError):
    """Raised when the bundled frontend package cannot be located."""


class FrontendPackageMode(enum.Enum):
    """How the frontend npm package is distributed in this install."""

    # Editable/dev install: the live source directory, symlinked into .web.
    SOURCE = "source"
    # Wheel install: a packed .tgz, copied into .web and installed from there.
    TARBALL = "tarball"


@dataclasses.dataclass(frozen=True)
class FrontendPackage:
    """The bundled frontend npm package and its manifest."""

    mode: FrontendPackageMode
    # The source directory (SOURCE) or the .tgz file (TARBALL).
    path: Path
    name: str
    # npm version from the manifest; a placeholder in SOURCE mode, the
    # stamped reflex-base-derived version in TARBALL mode.
    version: str
    dependencies: dict[str, str]
    # The app-level build toolchain contract: package managers never install
    # a dependency's devDependencies, so Reflex installs these into the app's
    # own devDependencies at setup time.
    dev_dependencies: dict[str, str]

    @property
    def tarball_basename(self) -> str:
        """The tarball filename for TARBALL mode.

        Returns:
            The basename of the packed tarball.

        Raises:
            FrontendPackageMissingError: If called in SOURCE mode.
        """
        if self.mode is not FrontendPackageMode.TARBALL:
            msg = "The frontend package is a source directory, not a tarball."
            raise FrontendPackageMissingError(msg)
        return self.path.name


def frontend_package_dir() -> Path:
    """Get the directory holding the bundled frontend package.

    Returns:
        The ``reflex_base/frontend`` directory of the active install.
    """
    import reflex_base

    return Path(reflex_base.__file__).parent / "frontend"


def _package_from_manifest(
    mode: FrontendPackageMode, path: Path, manifest: dict
) -> FrontendPackage:
    return FrontendPackage(
        mode=mode,
        path=path,
        name=manifest["name"],
        version=manifest["version"],
        dependencies=manifest.get("dependencies") or {},
        dev_dependencies=manifest.get("devDependencies") or {},
    )


@functools.lru_cache(maxsize=1)
def get_frontend_package() -> FrontendPackage:
    """Locate the bundled frontend package and read its manifest.

    Returns:
        The frontend package descriptor for the active reflex-base install.

    Raises:
        FrontendPackageMissingError: If neither the source directory nor a
            packed tarball is present (corrupt or incomplete install).
    """
    package_dir = frontend_package_dir()
    manifest_path = package_dir / "package.json"
    if manifest_path.is_file():
        return _package_from_manifest(
            FrontendPackageMode.SOURCE,
            package_dir,
            json.loads(manifest_path.read_text()),
        )
    tarballs = sorted(package_dir.glob("*.tgz")) if package_dir.is_dir() else []
    if len(tarballs) == 1:
        with tarfile.open(tarballs[0]) as tar:
            manifest_file = tar.extractfile("package/package.json")
            if manifest_file is None:  # pragma: no cover - malformed tarball
                msg = f"{tarballs[0]} does not contain package/package.json."
                raise FrontendPackageMissingError(msg)
            manifest = json.load(manifest_file)
        return _package_from_manifest(
            FrontendPackageMode.TARBALL, tarballs[0], manifest
        )
    msg = (
        f"The bundled frontend package was not found under {package_dir} "
        f"(expected a package.json or exactly one .tgz, found "
        f"{len(tarballs)} tarball(s)). Reinstall reflex-base to repair it."
    )
    raise FrontendPackageMissingError(msg)


def clear_frontend_package_cache():
    """Clear the cached frontend package descriptor (for tests)."""
    get_frontend_package.cache_clear()
