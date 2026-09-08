"""Built-artifact inspection and pre-build dependency pinning."""

from __future__ import annotations

import fnmatch
import re
import sys
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .actions import ReleaseError, fail


def normalize_name(name: str) -> str:
    """Normalize a distribution name the PEP 503 way.

    Args:
        name: The distribution name as written.

    Returns:
        The lowercase name with every run of ``-``, ``_`` or ``.`` collapsed to
        a single ``-``.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def dist_metadata(path: Path) -> tuple[str, str]:
    """Read the ``Name`` and ``Version`` metadata fields of a built distribution.

    Args:
        path: A wheel (``*.whl``) or sdist (``*.tar.gz``).

    Returns:
        The Name and Version header values from the wheel's METADATA / sdist's
        PKG-INFO.

    Raises:
        ReleaseError: When the artifact declares no name or no version.
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
    fields: dict[str, str] = {}
    for line in content.splitlines():
        if not line.strip():
            break
        key, _, value = line.partition(":")
        if key in {"Name", "Version"}:
            fields[key] = value.strip()
    if not fields.get("Name") or not fields.get("Version"):
        message = f"no Name/Version field in the metadata of {path.name}"
        raise ReleaseError(message)
    return fields["Name"], fields["Version"]


def verify_dist(
    dist_dir: Path,
    distribution: str,
    target: Version,
    expect: Sequence[str] = (),
) -> int:
    """Verify every built artifact is the expected distribution at the target version.

    Catches a misconfigured dynamic-versioning tag prefix building e.g.
    ``0.0.0dev0`` instead of the version being released, and — since every
    package in a repository publishes through the same trusted-publishing
    identity — a build that produced some *other* distribution than the one the
    approval names. Lockstep siblings share a version, so the version alone does
    not distinguish them.

    Args:
        dist_dir: The directory holding the built artifacts.
        distribution: The distribution name every artifact must declare.
        target: The version every artifact must declare.
        expect: Filename glob patterns that must each match at least one
            artifact. A build spread over a matrix of platforms is only correct
            if every leg contributed, and a leg that produced nothing is
            otherwise indistinguishable from one that was never configured.

    Returns:
        The number of artifacts verified.
    """
    expected_name = normalize_name(distribution)
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
        name, raw = dist_metadata(path)
        if normalize_name(name) != expected_name:
            fail(
                f"artifact {path.name} is {name}, expected {distribution}; the "
                "build produced a different distribution than the one being "
                "published"
            )
        try:
            found = Version(raw)
        except InvalidVersion:
            fail(f"artifact {path.name} has unparsable version {raw!r}")
        if found != target:
            fail(f"artifact {path.name} has version {found}, expected {target}")
    for pattern in expect:
        if not any(fnmatch.fnmatchcase(path.name, pattern) for path in files):
            fail(
                f"no built artifact matches the expected pattern {pattern!r}; the "
                f"build produced: {', '.join(path.name for path in files)}. "
                "Publishing an incomplete set of artifacts is not recoverable — a "
                "version can only be uploaded once — so this stops the release."
            )
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
    text = pyproject.read_text(encoding="utf-8")
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
    pyproject.write_text(
        text.replace(matches[0].group(0), new_pin, 1), encoding="utf-8"
    )
    sys.stderr.write(f"Pinned {new_pin} in {pyproject}\n")
