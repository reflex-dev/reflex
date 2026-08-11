"""Built-artifact inspection and pre-build dependency pinning."""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .actions import ReleaseError, fail


def dist_metadata_version(path: Path) -> str:
    """Read the ``Version`` metadata field of a built distribution.

    Args:
        path: A wheel (``*.whl``) or sdist (``*.tar.gz``).

    Returns:
        The Version header value from the wheel's METADATA / sdist's PKG-INFO.

    Raises:
        ReleaseError: When the artifact declares no version.
    """
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as wheel:
            names = [
                name
                for name in wheel.namelist()
                if name.endswith(".dist-info/METADATA") and name.count("/") == 1
            ]
            if len(names) != 1:
                fail(f"expected one .dist-info/METADATA in {path.name}, got {names}")
            content = wheel.read(names[0]).decode()
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as sdist:
            names = [
                member.name
                for member in sdist.getmembers()
                if member.name.endswith("/PKG-INFO") and member.name.count("/") == 1
            ]
            if len(names) != 1:
                fail(f"expected one top-level PKG-INFO in {path.name}, got {names}")
            member_file = sdist.extractfile(names[0])
            if member_file is None:
                fail(f"could not read {names[0]} from {path.name}")
            content = member_file.read().decode()
    else:
        fail(f"unexpected artifact type: {path.name}")
    for line in content.splitlines():
        if not line.strip():
            break
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    message = f"no Version field in the metadata of {path.name}"
    raise ReleaseError(message)


def verify_dist(dist_dir: Path, target: Version) -> int:
    """Verify every built artifact carries exactly the target version.

    Catches a misconfigured dynamic-versioning tag prefix building e.g.
    ``0.0.0dev0`` instead of the version being released.

    Args:
        dist_dir: The directory holding the built artifacts.
        target: The version every artifact must declare.

    Returns:
        The number of artifacts verified.
    """
    # Verify exactly what `uv publish dist/*` will upload: the shell glob skips
    # hidden files (uv build drops a .gitignore into dist/).
    files = sorted(
        path
        for path in dist_dir.glob("*")
        if path.is_file() and not path.name.startswith(".")
    )
    if not files:
        fail(f"no artifacts in {dist_dir}")
    for path in files:
        raw = dist_metadata_version(path)
        try:
            found = Version(raw)
        except InvalidVersion:
            fail(f"artifact {path.name} has unparsable version {raw!r}")
        if found != target:
            fail(f"artifact {path.name} has version {found}, expected {target}")
    return len(files)


def pin_exact(pyproject: Path, dependency: str, version: Version) -> None:
    """Rewrite a lower-bound requirement on a dependency to an exact pin.

    Lockstep packages release together at one version, so a package that
    publishes last must depend on exactly the sibling version published
    alongside it rather than on a floor that a future release would satisfy.

    Args:
        pyproject: The ``pyproject.toml`` of the package being built.
        dependency: The distribution name to pin.
        version: The version to pin it to.
    """
    text = pyproject.read_text()
    # Requirement strings are quoted TOML values, so the rewrite is anchored on
    # the quotes and on the distribution name, matched the PEP 503 way: any run
    # of ``-``, ``_`` or ``.`` is one separator. Extras carry over to the pin.
    name_pattern = r"[-_.]+".join(
        re.escape(part) for part in re.split(r"[-_.]+", dependency)
    )
    pattern = re.compile(
        rf'"\s*{name_pattern}\s*(?P<extras>\[[^"\]]*\])?\s*[<>=~!][^"]*"', re.IGNORECASE
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        fail(
            f'expected exactly one "{dependency} <specifier>" requirement in '
            f"{pyproject}, found {len(matches)}"
        )
    new_pin = f'"{dependency}{matches[0]["extras"] or ""} == {version}"'
    pyproject.write_text(text.replace(matches[0].group(0), new_pin, 1))
    sys.stderr.write(f"Pinned {new_pin} in {pyproject}\n")
