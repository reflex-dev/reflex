# /// script
# requires-python = ">=3.11"
# dependencies = ["packaging"]
# ///
"""Pin reflex's internal workspace dependencies to exact versions before build.

When publishing the ``reflex`` metapackage we want it to strictly depend on the
exact versions of each internal sub-package that were the latest at the time of
the release. This script reads the internal workspace dependencies from
``pyproject.toml``, finds the latest matching git tag reachable from ``HEAD`` for
each one, and rewrites the dependency specifier to an ``== <version>`` pin.

An internal dependency is one that is both listed in ``[project.dependencies]``
*and* declared as a workspace source in ``[tool.uv.sources]``. Dependencies
without a version specifier (e.g. ``reflex-hosting-cli``) are intentionally left
untouched so they can continue to float.

Sub-package tags follow the ``<package>-v<version>`` convention (matching
``parse_tag.sh``). When the reflex version being published is a final release,
sub-package pre-releases are ignored; when it is itself a pre-release, they are
considered.

Usage:
    VERSION=<reflex version> uv run --script pin_internal_packages.py [pyproject.toml]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version


def internal_dependencies(pyproject: dict) -> list[tuple[str, Requirement]]:
    """Return the internal workspace dependencies that should be pinned.

    A dependency qualifies when it is declared as a workspace source and carries
    an existing version specifier (so specifier-less deps keep floating).

    Args:
        pyproject: Parsed contents of ``pyproject.toml``.

    Returns:
        The qualifying dependencies as ``(original string, parsed Requirement)``
        pairs. The original string is preserved verbatim so it can be located
        exactly in the raw file text.
    """
    sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    workspace_members = {
        name
        for name, source in sources.items()
        if isinstance(source, dict) and source.get("workspace")
    }
    qualifying: list[tuple[str, Requirement]] = []
    for dep in pyproject.get("project", {}).get("dependencies", []):
        requirement = Requirement(dep)
        if requirement.name in workspace_members and str(requirement.specifier):
            qualifying.append((dep, requirement))
    return qualifying


def reachable_tags(package: str) -> list[str]:
    """Return the git tags for a package that are reachable from HEAD.

    Args:
        package: The sub-package name (e.g. ``reflex-components-lucide``).

    Returns:
        The matching tag names, searching backward from the current commit.
    """
    result = subprocess.run(
        ["git", "tag", "--merged", "HEAD", "--list", f"{package}-v*"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def latest_version(
    package: str, tags: list[str], *, allow_prerelease: bool
) -> Version | None:
    """Select the highest version among a package's tags.

    Args:
        package: The sub-package name, used to strip the ``<package>-v`` prefix.
        tags: Candidate tag names for the package.
        allow_prerelease: Whether pre-release versions are eligible (``is_prerelease``
            already covers dev releases).

    Returns:
        The highest eligible version, or None if there are no candidates.
    """
    prefix = f"{package}-v"
    versions: list[Version] = []
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        try:
            version = Version(tag[len(prefix) :])
        except InvalidVersion:
            continue
        if not allow_prerelease and version.is_prerelease:
            continue
        versions.append(version)
    return max(versions) if versions else None


def pin_dependencies(text: str, pins: list[tuple[str, str, Version]]) -> str:
    """Rewrite dependency specifiers in raw ``pyproject.toml`` text to exact pins.

    Args:
        text: The original file contents.
        pins: ``(name, original dependency string, target version)`` tuples.

    Returns:
        The updated file contents.

    Raises:
        RuntimeError: If a dependency string cannot be located exactly once.
    """
    for name, original, version in pins:
        # Assumes double-quoted dependency strings, matching how this repo's
        # pyproject.toml is written; single-quoted TOML strings would not match.
        old = f'"{original}"'
        new = f'"{name} == {version}"'
        count = text.count(old)
        if count != 1:
            msg = f"Expected exactly one occurrence of {old} in pyproject.toml, found {count}"
            raise RuntimeError(msg)
        text = text.replace(old, new)
    return text


def main(argv: list[str]) -> int:
    """Pin internal dependencies in pyproject.toml and write the result back.

    Args:
        argv: Command line arguments; an optional path to ``pyproject.toml``.

    Returns:
        A process exit code.
    """
    import tomllib  # stdlib only on 3.11+; imported here so the pure helpers above remain importable on 3.10 for testing

    reflex_version_str = os.environ.get("VERSION")
    if not reflex_version_str:
        print("Error: VERSION environment variable is required", file=sys.stderr)  # noqa: T201
        return 1
    reflex_version = Version(reflex_version_str)
    allow_prerelease = reflex_version.is_prerelease

    path = Path(argv[1]) if len(argv) > 1 else Path("pyproject.toml")
    text = path.read_text()
    pyproject = tomllib.loads(text)

    dependencies = internal_dependencies(pyproject)
    if not dependencies:
        print("Error: no internal workspace dependencies found to pin", file=sys.stderr)  # noqa: T201
        return 1

    pins: list[tuple[str, str, Version]] = []
    for original, requirement in dependencies:
        tags = reachable_tags(requirement.name)
        version = latest_version(
            requirement.name, tags, allow_prerelease=allow_prerelease
        )
        if version is None:
            print(  # noqa: T201
                f"Error: no reachable git tag found for '{requirement.name}'"
                + ("" if allow_prerelease else " (excluding pre-releases)"),
                file=sys.stderr,
            )
            return 1
        pins.append((requirement.name, original, version))

    path.write_text(pin_dependencies(text, pins))

    for name, _, version in pins:
        print(f"Pinned {name} == {version}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
