"""The development-release dependency pin gate.

Development releases (``*.dev``) are not published to PyPI, so a package whose
published metadata pins one cannot be installed by downstream users. This gate
keeps such pins out of a release. Only each package's *own* published
dependencies are inspected — siblings are not followed — so the usual leaf-first
release flow (publish the depended-on package, then drop the dev pin in the
dependent) is never deadlocked by a pin in another package.
"""

from __future__ import annotations

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from .actions import echo, fail
from .config import Config, load_pyproject

# PEP 440 operators that establish a version floor the resolved version must meet
# or match. A development release under one of these is an unpublished
# *minimum*; the same release under an upper bound (``<``, ``<=``) or exclusion
# (``!=``) leaves the requirement resolvable from PyPI, so it is not a dev pin.
_LOWER_BOUND_OPERATORS = frozenset({"===", "==", "~=", ">=", ">"})


def parse_requirement(requirement: str) -> tuple[str, bool]:
    """Split a PEP 508 requirement into its canonical name and dev-pin status.

    Args:
        requirement: A dependency string such as ``"mypkg-base >= 1.0.dev1"``.

    Returns:
        A ``(canonical_name, is_dev_pinned)`` tuple. ``is_dev_pinned`` is True
        only when a development release appears as a lower bound. An unparsable
        requirement is reported as ``("", False)``.
    """
    try:
        parsed = Requirement(requirement)
    except InvalidRequirement:
        return "", False
    name = canonicalize_name(parsed.name)
    for specifier in parsed.specifier:
        if specifier.operator not in _LOWER_BOUND_OPERATORS:
            continue
        try:
            if Version(specifier.version).is_devrelease:
                return name, True
        except InvalidVersion:
            # A prefix match such as ``==1.2.*`` has no concrete version to inspect.
            continue
    return name, False


def published_dependencies(project: dict) -> list[str]:
    """Collect the requirements that become a package's published metadata.

    Args:
        project: The ``[project]`` table of a parsed ``pyproject.toml``.

    Returns:
        The core runtime dependencies plus every optional-dependency group —
        exactly the requirements emitted as ``Requires-Dist``. Dependency groups
        (PEP 735) are excluded: they are development-only and never published.
    """
    deps = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        deps.extend(group)
    return deps


def check_dev_pins(config: Config, packages: list[str]) -> None:
    """Fail if any selected package declares a development-release pin.

    Args:
        config: The repository configuration.
        packages: The packages to inspect; empty inspects every package.
    """
    for package in packages:
        config.require_known(package)
    targets = packages or config.all_packages()

    offenders: list[tuple[str, str]] = []
    for package in targets:
        project = load_pyproject(config.package_path(package) / "pyproject.toml").get(
            "project", {}
        )
        offenders += [
            (package, dependency)
            for dependency in published_dependencies(project)
            if parse_requirement(dependency)[1]
        ]

    if offenders:
        listing = "\n".join(f"  {name}: {dependency}" for name, dependency in offenders)
        fail(
            "development-release dependency pins must not be published:\n"
            f"{listing}\n\n{len(offenders)} development-release pin(s) found. Release "
            "the depended-on package(s) and re-pin to a published version before "
            "publishing."
        )
    echo(f"No development-release dependency pins found in {len(targets)} package(s).")
