"""Validate that each workspace package's declared minimum dependency versions are workable.

For every checkable package (the root ``reflex`` package plus the sub-packages under
``packages/*``), this installs the package editable into two isolated virtualenvs (deps
from PyPI, never the local workspace, via ``--no-sources``): one with dependencies resolved
to their *declared minimums* (``--resolution lowest-direct``) and one with the latest
compatible versions. Pyright runs against the package's own source in each, and the check
fails only on errors that are *new* at the minimum versions.

The delta is what matters, not the absolute error count: a package's source legitimately
references undeclared optional/circular imports under ``TYPE_CHECKING`` (e.g. ``sqlalchemy``,
``pandas``, sibling ``reflex.*`` modules) that are missing in any isolated env. Those errors
appear identically at both resolutions and cancel out. An error that appears *only* at the
minimum versions means the code depends on a newer dependency than its declared lower bound
allows — exactly the bug this catches (e.g. calling a pydantic 2.x API while declaring
``pydantic >=1.10``).

Both resolutions install every optional-dependency group, of the package itself and of each
workspace sibling it depends on directly (e.g. ``reflex[db,pydantic,testing]`` when checking
``reflex-docgen``). A floor that is only too low for code behind an extra is then caught too,
rather than hidden because that extra's dependencies were never installed at either end.

Workspace siblings are the exception to ``--no-sources``. Every sibling the package
declares is built from its local checkout into a temporary directory that is offered to the
resolver as an extra ``--find-links`` index, so ``latest`` means "this workspace" for a
sibling and "PyPI" for everything else. Third-party dependencies still resolve from PyPI at
both ends.

That matters because a delta cannot see an error present at *both* ends. Cross-package APIs
are written and consumed in the same release train, so a package routinely imports a sibling
symbol that no published version of that sibling has yet. Resolving both ends from PyPI put
the identical error in both sets, it cancelled out, and the too-low floor sailed through —
until the sibling was published, at which point the check went red on already-merged code.
Against the workspace the symbol is present at ``latest`` and missing at the floor, which is
what the delta is meant to report. The fix it asks for is the ``*.dev`` pin below, which the
release pipeline rewrites to the real version.

A development-release pin (e.g. ``reflex-base >= 0.9.5.dev1``) is unresolvable from PyPI by
construction, so the same index is what makes it installable at all. Each sibling is built at
the version its own checkout derives, which keeps the wheelhouse a consistent snapshot of the
workspace; only a build that lands *below* such a floor — a checkout whose tags predate the
pin — is redone at the floor itself. An index is used rather than an extra editable install
target because build environments (a package whose build backend sets
``require-runtime-dependencies`` resolves its own runtime dependencies to build) are resolved
separately from the install targets and would otherwise not see the sibling at all.

An index alone is not enough at ``latest``. A workspace build carries a development version
(``0.9.12.post1.dev0+<sha>``), and a resolver only considers pre-releases for a requirement
that names one — so a plain floor such as ``reflex-base >= 0.9.12`` would quietly prefer the
published release. The baseline therefore pins each sibling to the exact version built from
the workspace, which is that opt-in. The minimum resolution is otherwise left unpinned, where
``lowest-direct`` selects the published release each declared floor asks for.

A ``*.dev`` floor is the exception, and it is pinned at the minimum too. Such a floor names a
version that was never published, so nothing on PyPI is the release it asks for; what the
index does hold below it are the pre-releases of the same version, and naming a development
version is exactly what makes a resolver consider those. Which one it then picks for
``lowest-direct`` has varied across uv versions, so leaving it unpinned made the result turn
on the resolver rather than on the code. The workspace build is the only honest answer, and
pinning it says so outright.

Run with ``uv run python scripts/check_min_deps.py [package ...]``. With no package
arguments, every checkable package is validated. The sibling wheels have to come from
somewhere: ``--wheelhouse DIR`` takes them from a directory, which is how CI reuses the
artifacts its build jobs already produced, and a run without it builds them locally instead.
Building is deliberately not a fallback for a wheelhouse that comes up short — a gap there
means this check and the build workflow have drifted, and silently building over it would
both hide that and waste the minutes those jobs already spent. A wheel that falls below a
declared development floor is rebuilt at that floor either way, since the build jobs number
every wheel from the tags and no tag reaches a version that has not been released.
``--check-dev-pins [package ...]`` instead scans the declared dependencies for
development-release pins and fails if any are found (used by the publish pipeline to keep
``*.dev`` pins out of released package metadata).
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "packaging",
#     "tomli; python_version < '3.11'",
# ]
# ///

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default isolated interpreter: match the interpreter running this script so the Python
# version is held constant across both resolutions and only dependency versions vary.
DEFAULT_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"

# Packages that are intentionally not validated:
#   hatch-reflex-pyi   - build-backend plugin, only depends on hatchling
#   integrations-docs  - has no declared dependencies
#   reflex-site-shared - excluded from the root pyright config
SKIP_PACKAGES = frozenset({
    "hatch-reflex-pyi",
    "integrations-docs",
    "reflex-site-shared",
})

# PEP 440 operators that establish a version floor the resolved version must meet or match.
# A development release under one of these is an unpublished *minimum*; the same release under
# an upper-bound (``<``, ``<=``) or exclusion (``!=``) operator (e.g. ``!=2.0.dev1``) leaves
# the requirement resolvable from PyPI, so it must not count as a dev pin.
_LOWER_BOUND_OPERATORS = frozenset({"===", "==", "~=", ">=", ">"})


def _parse_requirement(requirement: str) -> tuple[str, bool]:
    """Split a PEP 508 requirement into its canonical name and whether it dev-pins its floor.

    Uses ``packaging`` to parse the requirement and its version specifiers rather than ad hoc
    string handling, so name normalization, extras, markers and PEP 440 version semantics are
    all handled by the standard implementation.

    Args:
        requirement: A dependency string such as ``"reflex-base >= 0.9.5.dev1"``.

    Returns:
        A ``(canonical_name, is_dev_pinned)`` tuple. ``is_dev_pinned`` is ``True`` only when a
        development release (unpublished by convention) appears as a lower bound — under a
        ``>=``, ``>``, ``==``, ``===`` or ``~=`` operator. A dev release in an upper-bound or
        ``!=`` clause (e.g. ``reflex-base >=1.0,!=2.0.dev1``) stays resolvable from PyPI and
        does not count. An unparsable requirement is reported as ``("", False)``.
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


def _with_extras(target: str, extras: Sequence[str]) -> str:
    """Append a ``[extra,...]`` suffix to an install target.

    Args:
        target: A distribution name or project path.
        extras: The extras to request, possibly none.

    Returns:
        The target with its extras appended, or unchanged when there are none.
    """
    return f"{target}[{','.join(extras)}]" if extras else target


@dataclass(frozen=True)
class Package:
    """A workspace package that can be checked against its minimum dependencies."""

    name: str
    """The package directory name (e.g. ``reflex-base``), used as the CLI identifier."""

    project_dir: Path
    """Directory containing the package's ``pyproject.toml`` (the editable install target)."""

    source_dir: Path
    """Directory of importable source that pyright should type-check."""

    extras: tuple[str, ...]
    """Names of optional-dependency groups to install alongside the package."""

    local_sources: tuple[Path, ...] = ()
    """Project dirs of the sibling workspace packages this package depends on.

    These are built into a local wheelhouse offered to the resolver alongside PyPI in both
    resolutions, so ``latest`` resolves a sibling to this workspace. Without it a sibling API
    added in the current release train is missing at both ends and its error cancels out.
    """

    def install_target(self) -> str:
        """Build the editable install target, including any extras.

        Returns:
            The path passed to ``uv pip install -e``, with ``[extra,...]`` appended.
        """
        return _with_extras(str(self.project_dir), self.extras)


def _load_pyproject(path: Path) -> dict:
    """Parse a ``pyproject.toml`` file.

    Args:
        path: Path to the ``pyproject.toml`` file.

    Returns:
        The parsed TOML document.
    """
    with path.open("rb") as f:
        return tomllib.load(f)


def _single_source_dir(src: Path) -> Path:
    """Return the lone module directory under a ``src/`` layout directory.

    Args:
        src: The ``src`` directory of a package.

    Returns:
        The single child directory (the importable package).

    Raises:
        ValueError: If ``src`` does not contain exactly one child directory.
    """
    children = [child for child in src.iterdir() if child.is_dir()]
    if len(children) != 1:
        msg = f"expected exactly one module directory under {src}, found {children}"
        raise ValueError(msg)
    return children[0]


def _workspace_pyprojects() -> Iterator[tuple[str, Path]]:
    """Yield every workspace package's directory name paired with its ``pyproject.toml``.

    Yields:
        ``(directory_name, pyproject_path)`` for the root package (named ``"reflex"``) and
        each ``packages/*`` member. The directory name is the publish/CLI identifier.
    """
    yield "reflex", REPO_ROOT / "pyproject.toml"
    for project_file in sorted((REPO_ROOT / "packages").glob("*/pyproject.toml")):
        yield project_file.parent.name, project_file


def _workspace_package_dirs() -> dict[str, Path]:
    """Map each workspace package's normalized distribution name to its project directory.

    Returns:
        A mapping from canonical distribution name to the directory containing its
        ``pyproject.toml``, used to resolve a ``*.dev`` dependency pin to a local checkout.
    """
    dirs: dict[str, Path] = {}
    for _, project_file in _workspace_pyprojects():
        name = _load_pyproject(project_file).get("project", {}).get("name")
        if name:
            dirs[canonicalize_name(name)] = project_file.parent
    return dirs


def _published_dependencies(project: dict) -> list[str]:
    """Collect the requirements that become a package's published metadata.

    Args:
        project: The ``[project]`` table of a parsed ``pyproject.toml``.

    Returns:
        The core runtime dependencies plus every optional-dependency group — exactly the
        requirements emitted as ``Requires-Dist``. Dependency groups (PEP 735) are excluded
        because they are development-only and never published.
    """
    deps = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        deps.extend(group)
    return deps


def _local_sources(project: dict, workspace_dirs: dict[str, Path]) -> tuple[Path, ...]:
    """Resolve a package's workspace-sibling dependencies to local project directories.

    The whole transitive closure is returned, not just the direct dependencies: building a
    sibling resolves *its* runtime requirements too when its build backend sets
    ``require-runtime-dependencies``, so an unpublished floor deeper in the graph has to be
    in the wheelhouse already. Checking ``reflex-docgen`` builds the root ``reflex``, whose
    build environment resolves the root's own ``reflex-base`` floor.

    Args:
        project: The ``[project]`` table of the package being checked.
        workspace_dirs: Mapping from distribution name to project dir (see
            :func:`_workspace_package_dirs`).

    Returns:
        The project directories of the workspace packages this package depends on, directly
        or transitively, deduplicated and ordered dependencies-first so each sibling's own
        requirements are already built when it is.
    """
    sources: list[Path] = []
    seen: set[str] = set()

    def visit(project: dict) -> None:
        for dependency in _published_dependencies(project):
            name, _ = _parse_requirement(dependency)
            directory = workspace_dirs.get(name)
            if directory is None or name in seen:
                continue
            # Marked before recursing, so a cycle in the workspace graph terminates.
            seen.add(name)
            visit(_load_pyproject(directory / "pyproject.toml")["project"])
            sources.append(directory)

    visit(project)
    return tuple(sources)


def discover_packages() -> list[Package]:
    """Discover every checkable workspace package.

    Returns:
        The checkable packages, sorted by name, with the root ``reflex`` package first.
    """
    workspace_dirs = _workspace_package_dirs()
    packages: list[Package] = []

    root_project = _load_pyproject(REPO_ROOT / "pyproject.toml")["project"]
    packages.append(
        Package(
            name="reflex",
            project_dir=REPO_ROOT,
            source_dir=REPO_ROOT / "reflex",
            extras=tuple(root_project.get("optional-dependencies", {})),
            local_sources=_local_sources(root_project, workspace_dirs),
        )
    )

    for project_file in sorted((REPO_ROOT / "packages").glob("*/pyproject.toml")):
        name = project_file.parent.name
        if name in SKIP_PACKAGES:
            continue
        project = _load_pyproject(project_file)["project"]
        extras = tuple(project.get("optional-dependencies", {}))
        if not project.get("dependencies") and not extras:
            continue
        packages.append(
            Package(
                name=name,
                project_dir=project_file.parent,
                source_dir=_single_source_dir(project_file.parent / "src"),
                extras=extras,
                local_sources=_local_sources(project, workspace_dirs),
            )
        )

    return packages


@dataclass
class Result:
    """The outcome of checking a single package."""

    package: str
    ok: bool
    stage: str
    """Where the result was decided: ``"resolution"``, ``"min-version"`` or ``"ok"``."""
    detail: str
    """Human-readable diagnostics to print on failure."""


def _venv_python(venv: Path) -> Path:
    """Return the path to the interpreter inside a virtualenv.

    Args:
        venv: The virtualenv directory.

    Returns:
        The interpreter path, accounting for the platform's layout.
    """
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run a subprocess capturing combined output as text.

    Args:
        cmd: The command and arguments to run.
        kwargs: Extra keyword arguments forwarded to ``subprocess.run``.

    Returns:
        The completed process.
    """
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        **kwargs,
    )


def _pyright_errors(report: dict) -> dict[tuple[str, int, int, str], str]:
    """Extract error diagnostics from a pyright JSON report.

    Args:
        report: The parsed ``--outputjson`` document.

    Returns:
        A mapping from a stable diagnostic key (file, line, character, message) to a
        formatted, human-readable display line.
    """
    errors: dict[tuple[str, int, int, str], str] = {}
    for diagnostic in report.get("generalDiagnostics", []):
        if diagnostic.get("severity") != "error":
            continue
        start = diagnostic.get("range", {}).get("start", {})
        if "line" not in start or "character" not in start:
            continue
        key = (
            diagnostic["file"],
            start["line"],
            start["character"],
            diagnostic["message"],
        )
        errors[key] = (
            f"{diagnostic['file']}:{start['line'] + 1}:{start['character'] + 1}"
            f" - error: {diagnostic['message']}"
        )
    return errors


def _declared_requirements(projects: Iterable[dict]) -> dict[str, list[Requirement]]:
    """Group published requirements by canonical distribution name, across several projects.

    The package under test and every workspace sibling in its closure are passed together: a
    sibling's wheel has to satisfy whoever else in the closure depends on it, not just the
    package that pulled it in.

    Args:
        projects: The ``[project]`` tables to collect requirements from.

    Returns:
        A mapping from canonical distribution name to every requirement declared against it,
        across the core dependencies and the optional groups of each project.
    """
    requirements: dict[str, list[Requirement]] = {}
    for project in projects:
        for dependency in _published_dependencies(project):
            name, _ = _parse_requirement(dependency)
            if name:
                requirements.setdefault(name, []).append(Requirement(dependency))
    return requirements


def _satisfies(requirements: list[Requirement], version: Version) -> bool:
    """Return whether a version meets every requirement declared against its distribution.

    Pre-releases count as satisfying: a workspace build always carries a development version,
    and whether a resolver would *consider* one is settled by naming it in a pin, not here.

    Args:
        requirements: The requirements declared against one distribution.
        version: The version to test.

    Returns:
        True when every requirement's specifier admits the version.
    """
    return all(
        requirement.specifier.contains(version, prereleases=True)
        for requirement in requirements
    )


def _dev_build_version(requirements: list[Requirement]) -> str | None:
    """Choose a declared development floor that satisfies a sibling's requirements.

    Args:
        requirements: The requirements declared against the sibling.

    Returns:
        The lowest usable declared development version, or None when none is declared.
    """
    candidates: set[Version] = set()
    for requirement in requirements:
        for specifier in requirement.specifier:
            if specifier.operator not in _LOWER_BOUND_OPERATORS:
                continue
            try:
                version = Version(specifier.version)
            except InvalidVersion:
                continue
            if version.is_devrelease:
                candidates.add(version)
    return next(
        (
            str(version)
            for version in sorted(candidates)
            if _satisfies(requirements, version)
        ),
        None,
    )


def _wheel_versions(wheelhouse: Path) -> dict[str, Version]:
    """Map each distribution built into a wheelhouse to its highest version there.

    Args:
        wheelhouse: Directory holding the built wheels.

    Returns:
        A mapping from canonical distribution name to the highest version built for it.
    """
    versions: dict[str, Version] = {}
    for wheel in wheelhouse.glob("*.whl"):
        name, version, *_ = parse_wheel_filename(wheel.name)
        if name not in versions or version > versions[name]:
            versions[name] = version
    return versions


def _build_sibling(source: Path, wheelhouse: Path, version: str | None) -> str | None:
    """Build one sibling's wheel into the wheelhouse.

    Args:
        source: The sibling's project directory.
        wheelhouse: Directory to write the wheel into. It doubles as an index so an earlier
            sibling's wheel can satisfy this one's build environment.
        version: A version to build at in place of the one the checkout derives, or ``None``
            to use that.

    Returns:
        ``None`` on success, otherwise the captured output of the failing build.
    """
    build = _run(
        [
            "uv",
            "build",
            "--no-sources",
            "--wheel",
            "--find-links",
            str(wheelhouse),
            "--out-dir",
            str(wheelhouse),
            str(source),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "UV_DYNAMIC_VERSIONING_BYPASS": version}
        if version is not None
        else None,
    )
    return None if build.returncode == 0 else build.stdout


def _distribution_name(project_dir: Path) -> str:
    """Return a workspace package's canonical distribution name.

    Args:
        project_dir: The directory holding the package's ``pyproject.toml``.

    Returns:
        The canonical name its wheels are published under.
    """
    return canonicalize_name(
        _load_pyproject(project_dir / "pyproject.toml")["project"]["name"]
    )


def build_wheelhouse(
    packages: list[Package], wheelhouse: Path, build: bool
) -> tuple[dict[str, Version], str | None]:
    """Build every workspace sibling the selected packages need, once, into one index.

    This runs to completion before any package is checked, and never alongside one. The pyi
    build hook deletes the stubs in a sibling's *own* source tree and regenerates them, so a
    build overlapping a pyright run over that same tree is read mid-rewrite: an import
    resolves into a stub that has just been removed, or is not yet written, and the delta
    reports errors that belong to neither resolution. Building everything up front also
    builds each sibling once per run rather than once per package that declares it.

    Each sibling is built at the version its own checkout derives, so the wheelhouse is one
    consistent snapshot of the workspace. Only a build that lands *below* a declared
    development floor — a checkout whose tags predate the pin — is redone at that floor,
    which is what keeps an unpublished ``*.dev`` requirement resolvable at all. The floors
    considered are those declared anywhere in the selection, because one wheel has to serve
    every package in it.

    A sibling already present in the index is taken as built, which is how CI reuses the
    wheels its build jobs produced. Building the rest is opt-in: without it a sibling the
    index does not hold is an error naming it, rather than a wheel quietly produced here to
    a different recipe than the one the build workflow follows. That keeps the two from
    drifting apart unnoticed, and a wheel this check cannot use is one those jobs spent
    their minutes on for nothing. A wheel below a declared development floor is redone at
    that floor either way: the build jobs number every wheel from the tags, and such a floor
    names the unreleased version above them, so the sibling is not missing from their
    output — no wheel they could have produced meets it.

    A wheel that is present but unable to satisfy what is declared against it fails too, for
    a different reason: a package is numbered from the newest tag its checkout reaches, so a
    floor raised to a release whose tag never landed on this branch cannot be met by any
    revision of it. Resolving that sibling from PyPI at both ends instead would cancel its
    errors out and quietly restore the blind spot this check exists to close, so a pin this
    branch cannot satisfy is refused rather than worked around.

    Args:
        packages: The packages about to be checked.
        wheelhouse: Directory to write the wheels into, holding any already built for it.
        build: Whether to build a sibling the index does not hold at all.

    Returns:
        A ``(versions, detail)`` tuple mapping each distribution in the index to its version.
        ``detail`` is ``None`` on success, otherwise the failure — a build's captured output,
        or a report of the siblings the index cannot serve.
    """
    wheelhouse.mkdir(parents=True, exist_ok=True)
    # Each package's closure already lists a sibling after everything it depends on, and two
    # closures cannot disagree on the order of a pair, so keeping first occurrences merges
    # them without disturbing that.
    sources = list(
        dict.fromkeys(
            source for package in packages for source in package.local_sources
        )
    )
    requirements = _declared_requirements(
        _load_pyproject(path / "pyproject.toml")["project"]
        for path in dict.fromkeys([
            *(package.project_dir for package in packages),
            *sources,
        ])
    )
    unusable: list[str] = []
    for source in sources:
        name = _distribution_name(source)
        declared = requirements.get(name, [])
        built = _wheel_versions(wheelhouse).get(name)
        if built is None and build:
            detail = _build_sibling(source, wheelhouse, None)
            if detail is not None:
                return {}, detail
            built = _wheel_versions(wheelhouse).get(name)
        if built is None:
            unusable.append(f"  {name}: absent from the wheelhouse")
            continue
        if _satisfies(declared, built):
            continue
        floor = _dev_build_version(declared)
        if floor is not None:
            detail = _build_sibling(source, wheelhouse, floor)
            if detail is not None:
                return {}, detail
            continue
        unusable.append(
            f"  {name}: builds as {built} here, which does not satisfy "
            f"{', '.join(str(requirement) for requirement in declared)}"
        )
    if unusable:
        return {}, (
            "the wheelhouse cannot serve every workspace sibling:\n"
            + "\n".join(unusable)
            + "\n\nA sibling that is absent means this check and the build jobs that "
            "produce these wheels have drifted; drop --wheelhouse to build it here "
            "instead.\nA sibling this checkout cannot number high enough means a floor was "
            "raised to a release whose tag is not on this branch, so no revision of it can "
            "satisfy that floor. Tag the commit here whose source matches that release:\n"
            "  git tag <package>-v<version>.post1 <commit> && git push origin "
            "<package>-v<version>.post1"
        )
    return _wheel_versions(wheelhouse), None


def _workspace_pins(
    package: Package, versions: dict[str, Version]
) -> tuple[list[str], list[str]]:
    """Pin a package's own siblings to the wheels built from their local checkouts.

    A workspace build carries a development version (``0.9.12.post1.dev0+<sha>``), and a
    resolver only considers pre-releases for a requirement that names one, so a plain floor
    such as ``reflex-base >= 0.9.12`` would skip the wheel and take the published release.
    Naming the exact version is that opt-in, and it makes the baseline independent of how
    the workspace version sorts against PyPI.

    The minimum resolution is the opposite case — a declared floor is what it is there to
    test, so the published release it names is what should be installed. A ``*.dev`` floor
    names no published release at all, and naming a development version is itself the opt-in
    that puts every pre-release of that version in reach; which of those ``lowest-direct``
    then chose has differed between uv releases. So that floor is pinned to the workspace
    build, the one thing that can satisfy it on purpose rather than by accident.

    Each sibling the package depends on directly is also requested with all of its extras
    in both lists, so a floor too low for code behind a sibling's optional dependencies is
    caught too, not only one on its default set.

    Args:
        package: The package being checked.
        versions: Every distribution in the wheelhouse, from :func:`build_wheelhouse`.

    Returns:
        A ``(latest, minimum)`` pair of requirement lists. ``latest`` pins this package's own
        siblings whose build satisfies what its closure declares for them as
        ``name[extras]==version``. One that does not — a checkout whose tags predate the
        floor — is left unpinned in both, so that sibling resolves from PyPI as it did
        before. ``minimum`` pins only those the package itself floors at a development
        release, and names every other direct sibling with extras unpinned. Siblings another
        package in the selection needed are not pinned here.
    """
    project = _load_pyproject(package.project_dir / "pyproject.toml")["project"]
    siblings = [
        _load_pyproject(source / "pyproject.toml")["project"]
        for source in package.local_sources
    ]
    requirements = _declared_requirements([project, *siblings])
    # Only what the package declares itself decides the minimum: ``lowest-direct`` pins its
    # direct dependencies, and a floor a sibling declares is that sibling's own to test.
    own = _declared_requirements([project])
    latest: list[str] = []
    minimum: list[str] = []
    for sibling in siblings:
        name = canonicalize_name(sibling["name"])
        version = versions[name]
        # A direct sibling is requested with every extra it declares, so code the package
        # reaches through a sibling's optional dependencies is type-checked at both ends. A
        # transitive one is not: naming it here would make it a direct dependency, which
        # ``lowest-direct`` would then drop to a floor the package never declared.
        target = (
            _with_extras(name, tuple(sibling.get("optional-dependencies", {})))
            if name in own
            else name
        )
        pinned = _satisfies(requirements.get(name, []), version)
        if pinned:
            latest.append(f"{target}=={version}")
        elif target != name:
            latest.append(target)
        if pinned and _dev_build_version(own.get(name, [])) is not None:
            minimum.append(f"{target}=={version}")
        elif target != name:
            minimum.append(target)
    return latest, minimum


def _resolve_and_check(
    package: Package,
    python_version: str,
    venv: Path,
    config: Path,
    wheelhouse: Path | None,
    pins: Sequence[str],
    lowest: bool,
) -> tuple[dict[tuple[str, int, int, str], str] | None, str]:
    """Install a package into an isolated venv and run pyright against its source.

    Args:
        package: The package to install and check.
        python_version: The interpreter version for the venv.
        venv: Directory in which to create the virtualenv.
        config: Path to the pyright options config.
        wheelhouse: Local index holding wheels built from the package's workspace siblings,
            or ``None`` when the package declares none.
        pins: Extra ``name==version`` requirements to install alongside the package (see
            :func:`_workspace_pins`). The minimum resolution pins only the siblings it
            floors at a development release; every other declared floor is what is under
            test there, so it is left for ``lowest-direct`` to resolve.
        lowest: Whether to pin direct dependencies to their declared minimums.

    Returns:
        A ``(errors, detail)`` tuple. ``errors`` is the pyright error map, or ``None`` if
        the environment could not be built or pyright produced no parseable output, in
        which case ``detail`` carries the captured output.
    """
    venv_proc = _run(["uv", "venv", "--python", python_version, str(venv)])
    if venv_proc.returncode != 0:
        return None, venv_proc.stdout
    venv_python = str(_venv_python(venv))

    install_cmd = [
        "uv",
        "pip",
        "install",
        "--python",
        venv_python,
        "--no-sources",
    ]
    # ``--no-sources`` forces every dependency to resolve from PyPI; workspace siblings are the
    # exception, offered as an extra index of locally built wheels. At ``latest`` the ``pins``
    # select them, so an API added in the current release train is present on one side of the
    # delta. The minimum resolution pins only siblings floored at a ``*.dev`` version, which no
    # published release satisfies, and leaves ``lowest-direct`` to take the lowest version
    # satisfying every other declared floor — the published release under test. Unlike
    # an editable install target, an index is also consulted while resolving build
    # environments, which a ``require-runtime-dependencies`` build hook makes subject to the
    # same requirements.
    if wheelhouse is not None:
        install_cmd += ["--find-links", str(wheelhouse)]
    if lowest:
        install_cmd += ["--resolution", "lowest-direct"]
    install_cmd += ["-e", package.install_target(), *pins]
    install = _run(install_cmd, cwd=REPO_ROOT)
    if install.returncode != 0:
        return None, install.stdout

    # The package's modules are named individually rather than by directory, so only real
    # source is checked. ``.pyi`` stubs under ``src/`` are build artifacts: absent from a
    # fresh checkout, regenerated into the tree whenever the pyi build hook runs — including
    # when another package's check builds this one as a sibling — and written against the
    # workspace rather than this isolated environment, so checking them reports imports that
    # were never this package's to resolve. Naming the ``.py`` files leaves the diagnostics
    # byte-identical whether or not stubs happen to be present.
    pyright = _run(
        [
            "pyright",
            "--outputjson",
            "--pythonpath",
            venv_python,
            "--project",
            str(config),
            *sorted(str(module) for module in package.source_dir.rglob("*.py")),
        ],
        cwd=REPO_ROOT,
    )
    try:
        report = json.loads(pyright.stdout)
    except json.JSONDecodeError:
        return None, pyright.stdout or "(pyright produced no output)"
    return _pyright_errors(report), ""


def check_package(
    package: Package,
    python_version: str,
    wheelhouse: Path | None,
    versions: dict[str, Version],
) -> Result:
    """Check that a package type-checks no worse at its declared minimums than at latest.

    Installs the package twice in isolated environments — once with dependencies at their
    latest compatible versions, once pinned to their declared minimums — and compares
    pyright errors. Errors present only at the minimum versions indicate the code depends
    on a newer dependency than its declared lower bound allows.

    Args:
        package: The package to validate.
        python_version: The interpreter version for the isolated environments.
        wheelhouse: The run's index of workspace sibling wheels, or ``None`` when nothing
            in the selection declares a sibling.
        versions: Every distribution in that wheelhouse, from :func:`build_wheelhouse`.

    Returns:
        The result of the check.
    """
    with tempfile.TemporaryDirectory(prefix=f"min-deps-{package.name}-") as tmp:
        tmp_path = Path(tmp)
        config = tmp_path / "pyrightconfig.json"
        config.write_text(json.dumps({"reportIncompatibleMethodOverride": False}))

        latest_pins, minimum_pins = (
            _workspace_pins(package, versions) if package.local_sources else ([], [])
        )

        baseline, detail = _resolve_and_check(
            package,
            python_version,
            tmp_path / ".venv-latest",
            config,
            wheelhouse,
            latest_pins,
            lowest=False,
        )
        if baseline is None:
            return Result(
                package.name,
                False,
                "resolution",
                f"installing latest deps failed:\n{detail}",
            )

        minimum, detail = _resolve_and_check(
            package,
            python_version,
            tmp_path / ".venv-lowest",
            config,
            wheelhouse,
            minimum_pins,
            lowest=True,
        )
        if minimum is None:
            return Result(
                package.name,
                False,
                "resolution",
                f"installing minimum deps failed:\n{detail}",
            )

        new_errors = sorted(minimum.keys() - baseline.keys())
        if new_errors:
            return Result(
                package.name,
                False,
                "min-version",
                "\n".join(minimum[key] for key in new_errors),
            )

        return Result(package.name, True, "ok", "")


def check_dev_pins(package_names: list[str]) -> int:
    """Fail if a workspace package declares a development-release dependency pin.

    Development releases (``*.dev``) are not published to PyPI, so a package whose published
    metadata pins one cannot be installed by downstream users. This gate keeps such pins out
    of a release. Only each package's *own* published dependencies are inspected — siblings
    are not followed — so the usual leaf-first release flow (publish the depended-on package,
    then drop the dev pin in the dependent) is never deadlocked by a pin in another package.

    Args:
        package_names: Directory names to inspect (e.g. ``"reflex"``, ``"reflex-lucide"``).
            Empty inspects every workspace package.

    Returns:
        ``0`` if no development-release pins are found, ``1`` otherwise.
    """
    pyprojects = dict(_workspace_pyprojects())
    unknown = [name for name in package_names if name not in pyprojects]
    if unknown:
        print(
            f"unknown package(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(pyprojects)}"
        )
        return 1
    targets = (
        {name: pyprojects[name] for name in package_names}
        if package_names
        else pyprojects
    )

    offenders: list[tuple[str, str]] = []
    for name, project_file in targets.items():
        project = _load_pyproject(project_file).get("project", {})
        offenders += [
            (name, dependency)
            for dependency in _published_dependencies(project)
            if _parse_requirement(dependency)[1]
        ]

    if offenders:
        print("Development-release dependency pins must not be published:\n")
        for name, dependency in offenders:
            print(f"  {name}: {dependency}")
        print(
            f"\n{len(offenders)} development-release pin(s) found. Release the depended-on "
            "package(s) and re-pin to a published version before publishing."
        )
        return 1

    print(f"No development-release dependency pins found in {len(targets)} package(s).")
    return 0


def main() -> int:
    """Validate the declared minimum dependency versions of workspace packages.

    Returns:
        ``0`` if all checked packages pass, ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "packages",
        nargs="*",
        help="Package directory names to check (default: all checkable packages).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the checkable packages as a JSON array and exit.",
    )
    parser.add_argument(
        "--check-dev-pins",
        action="store_true",
        help="Instead of type-checking, scan the selected packages' declared dependencies "
        "for development-release (*.dev) pins and exit non-zero if any are found.",
    )
    parser.add_argument(
        "--python",
        default=DEFAULT_PYTHON,
        help=f"Interpreter version for the isolated environment (default: {DEFAULT_PYTHON}).",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        help="Number of packages to check in parallel (default: 1).",
    )
    parser.add_argument(
        "--wheelhouse",
        type=Path,
        help="Directory of prebuilt workspace wheels to resolve siblings from. CI points "
        "this at the artifacts the build workflow already produced, and a sibling the "
        "directory does not hold is then an error rather than something built over, "
        "which would hide a drift between this check and those jobs. One that falls below "
        "a *.dev floor is still rebuilt at that floor, which names a release the tags have "
        "not reached. Omit it and the wheels are built here instead.",
    )
    args = parser.parse_args()

    if args.check_dev_pins:
        return check_dev_pins(args.packages)

    all_packages = discover_packages()

    if args.list:
        print(json.dumps([p.name for p in all_packages]))
        return 0

    by_name = {p.name: p for p in all_packages}
    if args.packages:
        unknown = [name for name in args.packages if name not in by_name]
        if unknown:
            parser.error(
                f"unknown package(s): {', '.join(unknown)}. "
                f"Choose from: {', '.join(by_name)}"
            )
        selected = [by_name[name] for name in args.packages]
    else:
        selected = all_packages

    print(
        f"Checking {len(selected)} package(s) against minimum declared dependencies "
        f"(python {args.python})...\n"
    )

    with tempfile.TemporaryDirectory(prefix="min-deps-wheelhouse-") as tmp:
        wheelhouse = Path(tmp) / "wheelhouse"
        if args.wheelhouse is not None:
            # Copied rather than used in place, so a wheel rebuilt at a development floor
            # never lands in the caller's directory.
            shutil.copytree(args.wheelhouse, wheelhouse)
        # A caller who supplied the wheels means them to cover every sibling; one who
        # did not has nowhere else to get them.
        versions, detail = build_wheelhouse(
            selected, wheelhouse, build=args.wheelhouse is None
        )
        if detail is not None:
            # One index serves the whole run, so a failed build stops every package in it.
            print(f"building workspace sibling wheels failed:\n{detail}")
            return 1

        def check(package: Package) -> Result:
            return check_package(package, args.python, wheelhouse, versions)

        if args.jobs > 1:
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                results = list(executor.map(check, selected))
        else:
            results = [check(package) for package in selected]

    failures = [r for r in results if not r.ok]
    for result in sorted(results, key=lambda r: r.package):
        status = "PASS" if result.ok else f"FAIL ({result.stage})"
        print(f"  {status:<18} {result.package}")

    reason = {
        "min-version": "type errors that only appear at the declared minimum versions "
        "(bump the corresponding lower bound)",
        "resolution": "the isolated environment could not be built",
    }
    if failures:
        print("\n" + "=" * 72)
        for result in failures:
            print(f"\n{result.package} — {reason.get(result.stage, result.stage)}:")
            print(result.detail or "(no output captured)")
        print(f"\n{len(failures)} of {len(results)} package(s) failed.")
        return 1

    print(f"\nAll {len(results)} package(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
