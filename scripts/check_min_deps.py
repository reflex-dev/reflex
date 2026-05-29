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

Run with ``uv run python scripts/check_min_deps.py [package ...]``. With no arguments,
every checkable package is validated.
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
import subprocess
import sys
import tempfile
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


def discover_packages() -> list[Package]:
    """Discover every checkable workspace package.

    Returns:
        The checkable packages, sorted by name, with the root ``reflex`` package first.
    """
    packages: list[Package] = []

    root_pyproject = _load_pyproject(REPO_ROOT / "pyproject.toml")
    packages.append(
        Package(
            name="reflex",
            project_dir=REPO_ROOT,
            source_dir=REPO_ROOT / "reflex",
            extras=tuple(root_pyproject["project"].get("optional-dependencies", {})),
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
        start = diagnostic["range"]["start"]
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
