"""Verify that a built distribution ships the .pyi stubs its package generates.

Reflex generates its type stubs at build time — ``scripts/hatch_build.py`` for the
root ``reflex`` package, the ``hatch-reflex-pyi`` build hook for the component
packages — and ``*.pyi`` is gitignored, so nothing but the build itself puts a
stub into an artifact. A build that silently produced none ships a release with no
type information at all, and that is not recoverable: a version can only be
uploaded to PyPI once.

Run by ``.github/scripts/publish/post_build.sh``, the publish workflow's
repository-specific hook, with ``PACKAGE``, ``BUILD_DIR`` and ``DIST_DIR`` in the
environment — after the build and before the human approval gate.

Which packages must ship stubs is read out of the package's own pyproject rather
than listed here, so a package that starts or stops generating them is covered
without touching this script.
"""

# Inline dependencies, so `uv run --script` provisions the tomllib backport on the
# interpreters that lack it: the hook runs outside the project environment and can
# only rely on what this block declares.
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tomli; python_version < '3.11'",
# ]
# ///

from __future__ import annotations

import os
import sys
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyright: ignore[reportMissingImports]

#: The hatch build hook (packages/hatch-reflex-pyi) that a component package
#: declares to have its stubs generated during the build.
PYI_HOOK = "reflex-pyi"

#: Suffixes of the built artifacts that must carry a stub-shipping package's stubs.
ARTIFACT_SUFFIXES = (".whl", ".tar.gz")


def build_table(package_dir: Path) -> Mapping[str, Any]:
    """Read a package's ``[tool.hatch.build]`` table.

    Args:
        package_dir: The directory holding the package's pyproject.toml.

    Returns:
        The build table, empty when the package declares none.
    """
    with (package_dir / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    return pyproject.get("tool", {}).get("hatch", {}).get("build", {})


def generates_stubs(build: Mapping[str, Any]) -> bool:
    """Report whether a package is expected to ship generated .pyi stubs.

    Either signal is enough on its own. A package declaring the stub-generating
    build hook must ship stubs, and so must one declaring a ``*.pyi`` build
    artifact — the root ``reflex`` package generates its stubs from a custom
    hook and is only recognizable by the latter. Reading the hook independently
    of the artifact declaration is what catches a package that generates stubs
    but never declares them: ``*.pyi`` is gitignored, so hatchling leaves the
    generated files out of the artifact unless they are listed.

    Hatch accepts ``hooks`` and ``artifacts`` both at the top of the build table
    and under an individual target, and every scope is read.

    Args:
        build: The package's ``[tool.hatch.build]`` table.

    Returns:
        Whether the package's built artifacts must contain .pyi files.
    """
    return any(
        PYI_HOOK in scope.get("hooks", {})
        or any(pattern.endswith(".pyi") for pattern in scope.get("artifacts", ()))
        for scope in (build, *build.get("targets", {}).values())
    )


def stub_count(artifact: Path) -> int:
    """Count the .pyi files inside a built artifact.

    Args:
        artifact: A wheel (``*.whl``) or an sdist (``*.tar.gz``).

    Returns:
        The number of .pyi members the artifact contains.
    """
    if artifact.name.endswith(".whl"):
        with zipfile.ZipFile(artifact) as wheel:
            return sum(name.endswith(".pyi") for name in wheel.namelist())
    with tarfile.open(artifact, "r:gz") as sdist:
        return sum(name.endswith(".pyi") for name in sdist.getnames())


def main() -> int:
    """Check every artifact of a stub-generating package for its stubs.

    Returns:
        0 when the package generates no stubs or every artifact carries them,
        1 otherwise.
    """
    package = os.environ["PACKAGE"]
    build_dir = Path(os.environ["BUILD_DIR"])
    dist_dir = Path(os.environ["DIST_DIR"])

    if not generates_stubs(build_table(build_dir)):
        print(f"{package} does not generate .pyi stubs, nothing to verify")
        return 0

    # Every artifact, not just the first match: a build spread over a matrix
    # uploads several wheels and a leg that lost its stubs is as broken as a
    # single build that produced none.
    artifacts = sorted(
        path
        for path in dist_dir.glob("*")
        if path.is_file() and path.name.endswith(ARTIFACT_SUFFIXES)
    )
    if not artifacts:
        print(
            f"Error: {package} generates .pyi stubs but {dist_dir} holds no "
            "wheel or sdist to check"
        )
        return 1

    missing: list[str] = []
    for artifact in artifacts:
        count = stub_count(artifact)
        if count:
            print(f"✓ {artifact.name}: {count} .pyi files")
        else:
            missing.append(artifact.name)
            print(f"✗ {artifact.name}: no .pyi files")

    if missing:
        print(
            f"Error: {package} generates .pyi stubs but they are missing from "
            f"{', '.join(missing)}. A version can only be uploaded once, so a "
            "release with no type information is not recoverable — this stops "
            "the release."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
