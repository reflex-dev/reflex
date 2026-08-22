"""Custom build hook: pack reflex_base/frontend into an npm tarball bundled in the wheel.

The frontend npm package ships inside the reflex-base wheel as a packed
tarball whose version is stamped from the wheel's version, while the JS source
directory ships only in the sdist (and is used directly in editable installs).
The tarball is produced with the stdlib rather than ``npm pack`` because the
release build environment has no JS toolchain, and its bytes must be
deterministic: package managers record content hashes for ``file:`` tarballs
in lockfiles, so a wheel rebuilt from the sdist has to reproduce the tarball
byte for byte.
"""

from __future__ import annotations

import gzip
import io
import json
import re
import shutil
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from packaging.version import Version

if TYPE_CHECKING:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
else:
    try:
        from hatchling.builders.hooks.plugin.interface import BuildHookInterface
    except ImportError:  # loaded outside a build (release verification, tests)
        BuildHookInterface = object

FRONTEND_RELATIVE_PATH = "src/reflex_base/frontend"
WHEEL_DESTINATION_DIR = "reflex_base/frontend"

_EXCLUDED_DIR_NAMES = frozenset({"node_modules"})


def pep440_to_npm_semver(version: str) -> str:
    """Map a PEP 440 version to an equivalent npm semver string.

    The release segment maps directly (padded/truncated to three components),
    pre/post/dev segments become dot-joined prerelease identifiers, and local
    version segments become build metadata. Note npm prerelease *ordering*
    differs from PEP 440; irrelevant here since installs use exact refs.

    Args:
        version: The PEP 440 version string.

    Returns:
        The npm semver version string.
    """
    parsed = Version(version)
    release = ([*parsed.release, 0, 0])[:3]
    semver = ".".join(str(part) for part in release)
    prerelease_parts: list[str] = []
    if parsed.pre is not None:
        prerelease_parts += [parsed.pre[0], str(parsed.pre[1])]
    if parsed.post is not None:
        prerelease_parts += ["post", str(parsed.post)]
    if parsed.dev is not None:
        prerelease_parts += ["dev", str(parsed.dev)]
    if prerelease_parts:
        semver += "-" + ".".join(prerelease_parts)
    if parsed.local:
        semver += "+" + re.sub(r"[^0-9A-Za-z-]", "-", parsed.local)
    return semver


def npm_tarball_basename(name: str, version: str) -> str:
    """Compute the tarball filename npm pack would use for a package.

    Args:
        name: The npm package name (possibly scoped).
        version: The npm package version.

    Returns:
        The tarball basename, e.g. ``reflex-dev-reflex-base-0.9.10.tgz``.
    """
    return f"{name.removeprefix('@').replace('/', '-')}-{version}.tgz"


def _iter_package_files(source_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    """Select the files the tarball ships, honoring the manifest ``files`` list.

    Semantics are the minimal subset npm applies that this package needs:
    ``package.json`` is always included (stamped separately), ``README*`` and
    ``LICENSE*`` are always included, directories are included recursively,
    plain entries name files or simple globs, and ``node_modules``, hidden
    files, and tarballs are always excluded.

    Args:
        source_dir: The package source directory.
        manifest: The parsed package.json.

    Returns:
        Sorted file paths to include (package.json excluded).

    Raises:
        ValueError: If the ``files`` list uses unsupported negation patterns.
    """
    selected: set[Path] = set()
    entries = manifest.get("files")
    if entries is None:
        entries = ["."]
    for entry in entries:
        if entry.startswith("!"):
            msg = f"Unsupported negation pattern in package.json files: {entry!r}"
            raise ValueError(msg)
        target = source_dir / entry
        if target.is_dir():
            selected.update(p for p in target.rglob("*") if p.is_file())
        elif target.is_file():
            selected.add(target)
        else:
            selected.update(p for p in source_dir.glob(entry) if p.is_file())
    selected.update(source_dir.glob("README*"))
    selected.update(source_dir.glob("LICENSE*"))

    def _shippable(path: Path) -> bool:
        relative = path.relative_to(source_dir)
        return not (
            path.name == "package.json"
            or path.suffix == ".tgz"
            or any(
                part.startswith(".") or part in _EXCLUDED_DIR_NAMES
                for part in relative.parts
            )
        )

    return sorted(p for p in selected if _shippable(p))


def build_frontend_tarball(source_dir: Path, npm_version: str, out_path: Path) -> None:
    """Build a deterministic npm-compatible tarball from the package source.

    All members live under the ``package/`` prefix with zeroed uid/gid/mtime,
    normalized modes, sorted order, and a fixed gzip header, so identical
    source always produces identical bytes. The ``package.json`` member is the
    source manifest with the version replaced by ``npm_version``.

    Args:
        source_dir: The package source directory (contains package.json).
        npm_version: The npm version to stamp into the packed manifest.
        out_path: Where to write the .tgz file.
    """
    manifest = json.loads((source_dir / "package.json").read_text())
    manifest["version"] = npm_version
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()

    def _normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        info.mode = 0o755 if info.mode & 0o100 else 0o644
        return info

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        manifest_info = _normalize(tarfile.TarInfo("package/package.json"))
        manifest_info.size = len(manifest_bytes)
        tar.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for path in _iter_package_files(source_dir, manifest):
            arcname = f"package/{path.relative_to(source_dir).as_posix()}"
            tar.add(path, arcname=arcname, recursive=False, filter=_normalize)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # filename="" keeps the FNAME field out of the gzip header (it would
    # otherwise embed the build-machine-specific output path).
    with (
        out_path.open("wb") as out_file,
        gzip.GzipFile(
            filename="", fileobj=out_file, mode="wb", mtime=0, compresslevel=9
        ) as gz,
    ):
        gz.write(buffer.getvalue())


class BundleFrontendTarballHook(BuildHookInterface):
    """Pack the frontend npm package and force-include it into the wheel."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Build the tarball into the dist scratch dir and register it.

        Only wheel builds carry the tarball (the sdist keeps the JS source so
        wheels built from it regenerate identical bytes); editable installs
        skip the work entirely since dev mode uses the source directory.

        Args:
            version: The build version ("standard" or "editable").
            build_data: Build data dict, mutated to add the force-include.
        """
        if self.target_name != "wheel" or version == "editable":
            return
        frontend_dir = Path(self.root) / FRONTEND_RELATIVE_PATH
        manifest_path = frontend_dir / "package.json"
        if not manifest_path.is_file():
            # Building without the JS source (e.g. a stripped tree); the wheel
            # will simply lack the tarball and runtime raises a clear error.
            return
        npm_version = pep440_to_npm_semver(self.metadata.version)
        package_name = json.loads(manifest_path.read_text())["name"]
        basename = npm_tarball_basename(package_name, npm_version)
        scratch_dir = Path(self.directory) / ".reflex_frontend_tgz"
        shutil.rmtree(scratch_dir, ignore_errors=True)
        tgz_path = scratch_dir / basename
        build_frontend_tarball(frontend_dir, npm_version, tgz_path)
        force_include = build_data.setdefault("force_include", {})
        force_include[str(tgz_path)] = f"{WHEEL_DESTINATION_DIR}/{basename}"
