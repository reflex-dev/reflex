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

Development-release pins are the exception to ``--no-sources``. A package may pin a sibling
workspace package to an unreleased ``*.dev`` version (e.g. ``reflex-base >= 0.9.5.dev1``)
while that version is still unpublished, which would otherwise make resolution from PyPI
impossible. For such pins — and only those — the depended-on package is installed editable
from its local workspace checkout in both environments, so every *non-dev* dependency is
still required to resolve from PyPI.

Run with ``uv run python scripts/check_min_deps.py [package ...]``. With no arguments,
every checkable package is validated. ``--check-dev-pins [package ...]`` instead scans the
declared dependencies for development-release pins and fails if any are found (used by the
publish pipeline to keep ``*.dev`` pins out of released package metadata).
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tomli; python_version < '3.11'",
# ]
# ///

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

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

# Leading distribution name (and optional ``[extras]``) of a PEP 508 requirement.
_REQUIREMENT_NAME = re.compile(r"\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?")

# A PEP 440 development-release segment within a version specifier: a digit, an optional
# ``.``/``-``/``_`` separator, then ``dev`` (e.g. ``0.9.5.dev1``, ``1.0dev``, ``1.0-dev0``).
# Anchoring on a preceding digit keeps it from matching a stray ``dev`` (such as a ``.dev``
# URL host); it is only ever matched against the version-specifier region of a requirement,
# never the package name or the environment marker.
_DEV_RELEASE = re.compile(r"[0-9][._-]?dev", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    """Normalize a distribution name to its PEP 503 canonical form.

    Args:
        name: A distribution name as written in a requirement or ``[project].name``.

    Returns:
        The lowercased name with runs of ``-``, ``_`` and ``.`` collapsed to a single ``-``.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement(requirement: str) -> tuple[str, bool]:
    """Split a PEP 508 requirement into its name and whether its lower bound is a dev release.

    Args:
        requirement: A dependency string such as ``"reflex-base >= 0.9.5.dev1"``.

    Returns:
        A ``(normalized_name, is_dev_pinned)`` tuple. ``is_dev_pinned`` is ``True`` when the
        requirement's version specifier references a development release, which by convention
        is not published to PyPI.
    """
    match = _REQUIREMENT_NAME.match(requirement)
    if not match:
        return "", False
    name = _normalize_name(match.group(1))
    specifier = requirement[match.end() :].split(";", 1)[0]
    if specifier.lstrip().startswith("@"):  # direct URL reference, not a version pin
        return name, False
    return name, bool(_DEV_RELEASE.search(specifier))


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

    local_dev_sources: tuple[Path, ...] = ()
    """Project dirs of sibling workspace packages this package pins to a ``*.dev`` release.

    These are installed editable from the local checkout (rather than PyPI) in both
    resolutions, because the pinned development version is not published.
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
            dirs[_normalize_name(name)] = project_file.parent
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


def _local_dev_sources(
    project: dict, workspace_dirs: dict[str, Path]
) -> tuple[Path, ...]:
    """Resolve a package's ``*.dev`` dependency pins to local workspace project directories.

    Args:
        project: The ``[project]`` table of the package being checked.
        workspace_dirs: Mapping from distribution name to project dir (see
            :func:`_workspace_package_dirs`).

    Returns:
        The project directories of the sibling workspace packages this package pins to an
        unpublished development release, deduplicated and in declaration order.
    """
    sources: list[Path] = []
    seen: set[str] = set()
    for dependency in _published_dependencies(project):
        name, is_dev = _parse_requirement(dependency)
        if is_dev and name in workspace_dirs and name not in seen:
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
            local_dev_sources=_local_dev_sources(root_project, workspace_dirs),
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
                local_dev_sources=_local_dev_sources(project, workspace_dirs),
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


def _resolve_and_check(
    package: Package,
    python_version: str,
    venv: Path,
    config: Path,
    lowest: bool,
) -> tuple[dict[tuple[str, int, int, str], str] | None, str]:
    """Install a package into an isolated venv and run pyright against its source.

    Args:
        package: The package to install and check.
        python_version: The interpreter version for the venv.
        venv: Directory in which to create the virtualenv.
        config: Path to the pyright options config.
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
    if lowest:
        install_cmd += ["--resolution", "lowest-direct"]
    install_cmd += ["-e", package.install_target()]
    # ``--no-sources`` forces every dependency to resolve from PyPI; the lone exception is a
    # sibling pinned to an unpublished ``*.dev`` release, which is provided here as an explicit
    # editable from its local checkout so resolution can succeed without reaching PyPI for it.
    for source in package.local_dev_sources:
        install_cmd += ["-e", str(source)]
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

        baseline, detail = _resolve_and_check(
            package, python_version, tmp_path / ".venv-latest", config, lowest=False
        )
        if baseline is None:
            return Result(
                package.name,
                False,
                "resolution",
                f"installing latest deps failed:\n{detail}",
            )

        minimum, detail = _resolve_and_check(
            package, python_version, tmp_path / ".venv-lowest", config, lowest=True
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
