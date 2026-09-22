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
the workspace, which is that opt-in. The minimum resolution is left unpinned, where
``lowest-direct`` selects the published release each declared floor asks for.

Run with ``uv run python scripts/check_min_deps.py [package ...]``. With no arguments,
every checkable package is validated. ``--check-dev-pins [package ...]`` instead scans the
declared dependencies for development-release pins and fails if any are found (used by the
publish pipeline to keep ``*.dev`` pins out of released package metadata).
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
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
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
        target = str(self.project_dir)
        if self.extras:
            target += "[" + ",".join(self.extras) + "]"
        return target


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

    Args:
        project: The ``[project]`` table of the package being checked.
        workspace_dirs: Mapping from distribution name to project dir (see
            :func:`_workspace_package_dirs`).

    Returns:
        The project directories of the sibling workspace packages this package declares,
        deduplicated and in declaration order. Declaration order is preserved so a sibling
        listed before another can satisfy that other's build environment.
    """
    sources: list[Path] = []
    seen: set[str] = set()
    for dependency in _published_dependencies(project):
        name, _ = _parse_requirement(dependency)
        if name in workspace_dirs and name not in seen:
            seen.add(name)
            sources.append(workspace_dirs[name])
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
        if not project.get("dependencies"):
            continue
        packages.append(
            Package(
                name=name,
                project_dir=project_file.parent,
                source_dir=_single_source_dir(project_file.parent / "src"),
                extras=tuple(project.get("optional-dependencies", {})),
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


def _declared_requirements(project: dict) -> dict[str, list[Requirement]]:
    """Group a package's published requirements by canonical distribution name.

    Args:
        project: The ``[project]`` table of the package being checked.

    Returns:
        A mapping from canonical distribution name to every requirement declared against it,
        across the core dependencies and the optional groups.
    """
    requirements: dict[str, list[Requirement]] = {}
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


def _build_local_wheelhouse(package: Package, wheelhouse: Path) -> str | None:
    """Build wheels for the package's workspace siblings into a local index.

    Each sibling is built at the version its own checkout derives, so the wheelhouse is one
    consistent snapshot of the workspace and the siblings satisfy each other's requirements
    the same way they do in the repository. Only a build that lands *below* a declared
    development floor — a checkout whose tags predate the pin — is redone at that floor,
    which is what keeps an unpublished ``*.dev`` requirement resolvable at all.

    Args:
        package: The package whose declared siblings should be built.
        wheelhouse: Directory to write the wheels into.

    Returns:
        ``None`` on success, otherwise the captured output of the failing build.
    """
    wheelhouse.mkdir(parents=True, exist_ok=True)
    project = _load_pyproject(package.project_dir / "pyproject.toml")["project"]
    requirements = _declared_requirements(project)
    for source in package.local_sources:
        name = canonicalize_name(
            _load_pyproject(source / "pyproject.toml")["project"]["name"]
        )
        declared = requirements.get(name, [])
        detail = _build_sibling(source, wheelhouse, None)
        if detail is not None:
            return detail
        built = _wheel_versions(wheelhouse).get(name)
        if built is not None and _satisfies(declared, built):
            continue
        floor = _dev_build_version(declared)
        if floor is not None:
            detail = _build_sibling(source, wheelhouse, floor)
            if detail is not None:
                return detail
    return None


def _workspace_pins(package: Package, wheelhouse: Path) -> list[str]:
    """Pin each workspace sibling to the wheel built from its local checkout.

    A workspace build carries a development version (``0.9.12.post1.dev0+<sha>``), and a
    resolver only considers pre-releases for a requirement that names one, so a plain floor
    such as ``reflex-base >= 0.9.12`` would skip the wheel and take the published release
    instead. Naming the exact version is that opt-in, and it makes the baseline independent
    of how the workspace version happens to sort against PyPI.

    Args:
        package: The package being checked.
        wheelhouse: Directory holding the wheels built from its siblings.

    Returns:
        ``name==version`` requirements for the siblings whose local build satisfies what the
        package declares for them. A build that does not — a checkout whose tags predate the
        declared floor — is left out, so that sibling resolves from PyPI as it did before.
    """
    requirements = _declared_requirements(
        _load_pyproject(package.project_dir / "pyproject.toml")["project"]
    )
    return [
        f"{name}=={version}"
        for name, version in sorted(_wheel_versions(wheelhouse).items())
        if _satisfies(requirements.get(name, []), version)
    ]


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
            :func:`_workspace_pins`); empty for the minimum resolution, whose declared floors
            are exactly what is under test.
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
    # delta. The minimum resolution passes no pins, leaving ``lowest-direct`` to take the
    # lowest version satisfying each declared floor — the published release under test. Unlike
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

    pyright = _run(
        [
            "pyright",
            "--outputjson",
            "--pythonpath",
            venv_python,
            "--project",
            str(config),
            str(package.source_dir),
        ],
        cwd=REPO_ROOT,
    )
    try:
        report = json.loads(pyright.stdout)
    except json.JSONDecodeError:
        return None, pyright.stdout or "(pyright produced no output)"
    return _pyright_errors(report), ""


def check_package(package: Package, python_version: str) -> Result:
    """Check that a package type-checks no worse at its declared minimums than at latest.

    Installs the package twice in isolated environments — once with dependencies at their
    latest compatible versions, once pinned to their declared minimums — and compares
    pyright errors. Errors present only at the minimum versions indicate the code depends
    on a newer dependency than its declared lower bound allows.

    Args:
        package: The package to validate.
        python_version: The interpreter version for the isolated environments.

    Returns:
        The result of the check.
    """
    with tempfile.TemporaryDirectory(prefix=f"min-deps-{package.name}-") as tmp:
        tmp_path = Path(tmp)
        config = tmp_path / "pyrightconfig.json"
        config.write_text(json.dumps({"reportIncompatibleMethodOverride": False}))

        wheelhouse = None
        pins: list[str] = []
        if package.local_sources:
            wheelhouse = tmp_path / "wheelhouse"
            detail = _build_local_wheelhouse(package, wheelhouse)
            if detail is not None:
                return Result(
                    package.name,
                    False,
                    "resolution",
                    f"building workspace sibling wheels failed:\n{detail}",
                )
            pins = _workspace_pins(package, wheelhouse)

        baseline, detail = _resolve_and_check(
            package,
            python_version,
            tmp_path / ".venv-latest",
            config,
            wheelhouse,
            pins,
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
            (),
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

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            results = list(
                executor.map(lambda p: check_package(p, args.python), selected)
            )
    else:
        results = [check_package(p, args.python) for p in selected]

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
