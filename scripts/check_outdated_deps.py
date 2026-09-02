"""Report outdated backend and frontend dependencies, ignoring deliberately held packages.

Wraps ``uv pip list --outdated`` (backend) and ``bun outdated`` (frontend) and fails when
anything outside the configured hold lists is behind its latest release. The hold lists live
in the root ``pyproject.toml`` under ``[tool.check-outdated-deps]`` rather than in this
script, so adding or removing one is a config change:

    [tool.check-outdated-deps]
    backend_held = ["pydantic-core", "pyee", "redis"]
    backend_pinned = ["pyright", "ruff"]
    frontend_held = ["react-moment", "plotly.js"]
    frontend_pinned = ["@chakra-ui/*", "ag-grid*"]

An entry matches a package by exact name, or by prefix when it ends in ``*``. Prefix entries
are what cover a whole scope (``@chakra-ui/*``) or a release-locked family (``ag-grid*``,
which is three separate packages moving together).

The two lists differ in whether staleness is checked. ``*_held`` is for packages blocked on
work we own, so a hold that is no longer doing anything is an error: if a held package is
installed but absent from the outdated report it is already at its latest version and the
entry should be deleted, and if it matches no installed package at all it is stale in a
different way. ``*_pinned`` is for packages we do not drive -- pinned by policy, or owned by
another repo -- where reaching latest says nothing about whether the entry can go, so only
suppression applies.

Run with ``uv run python scripts/check_outdated_deps.py {backend,frontend}``. The frontend
check needs a compiled app, so it takes the directory holding the generated
``package.json`` (``--web-dir``, default ``.``) and must run where ``bun`` can see the
installed tree.
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
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).parent.parent

CONFIG_TABLE = "check-outdated-deps"

# `bun outdated` tags rows outside `dependencies` in the package cell.
BUN_ANNOTATIONS = (" (dev)", " (peer)", " (optional)")

# The dependency sections `bun outdated` reports on, and so the ones a held entry can
# legitimately name.
BUN_DEPENDENCY_FIELDS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


class CheckError(Exception):
    """A dependency check failed, with a message meant for the console."""


def _load_config(kind: str) -> tuple[list[str], list[str]]:
    """Read the hold lists for one side of the check out of the root ``pyproject.toml``.

    Args:
        kind: Either ``"backend"`` or ``"frontend"``.

    Returns:
        ``(held, pinned)`` package patterns, in declaration order.

    Raises:
        CheckError: If the config table or either list is missing or malformed.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f).get("tool", {}).get(CONFIG_TABLE)
    if config is None:
        msg = f"pyproject.toml is missing the [tool.{CONFIG_TABLE}] table"
        raise CheckError(msg)

    lists = []
    for key in (f"{kind}_held", f"{kind}_pinned"):
        patterns = config.get(key)
        if patterns is None:
            msg = f"[tool.{CONFIG_TABLE}] is missing the `{key}` list"
            raise CheckError(msg)
        if not isinstance(patterns, list) or not all(
            isinstance(name, str) for name in patterns
        ):
            msg = f"[tool.{CONFIG_TABLE}] `{key}` must be a list of strings"
            raise CheckError(msg)
        lists.append(patterns)
    return lists[0], lists[1]


def matches(pattern: str, package: str) -> bool:
    """Check whether a hold pattern covers a package name.

    Args:
        pattern: A hold entry: an exact package name, or a prefix ending in ``*``.
        package: The package name to test.

    Returns:
        Whether the pattern covers the package.
    """
    if pattern.endswith("*"):
        return package.startswith(pattern[:-1])
    return package == pattern


def partition(
    outdated: Iterable[str],
    installed: Iterable[str],
    held: Sequence[str],
    pinned: Sequence[str] = (),
) -> tuple[list[str], list[str], list[str]]:
    """Split packages into the reportable, the suppressed, and the stale holds.

    Args:
        outdated: Names of packages behind their latest release.
        installed: Names of every installed/declared package.
        held: Patterns for packages blocked on work we own; checked for staleness.
        pinned: Patterns for packages we do not drive; suppressed but never stale.

    Returns:
        ``(reportable, suppressed, stale_holds)`` — the outdated packages nothing covers,
        the outdated packages either list covers, and the ``held`` patterns that no longer
        suppress anything (each annotated with why).
    """
    outdated = list(outdated)
    installed_set = set(installed)
    covering = [*held, *pinned]

    reportable: list[str] = []
    suppressed: list[str] = []
    for name in outdated:
        covered = any(matches(pattern, name) for pattern in covering)
        (suppressed if covered else reportable).append(name)

    stale_holds = []
    for pattern in held:
        covered = [name for name in installed_set if matches(pattern, name)]
        if not covered:
            stale_holds.append(f"{pattern} (matches no installed package)")
            continue
        if not any(matches(pattern, name) for name in outdated):
            at_latest = ", ".join(sorted(covered))
            stale_holds.append(f"{pattern} (already at latest: {at_latest})")

    return reportable, suppressed, sorted(stale_holds)


def _run(command: Sequence[str], cwd: Path | None = None) -> str:
    """Run a command and return its stdout.

    Args:
        command: The command and its arguments.
        cwd: Directory to run in, or None for the current directory.

    Returns:
        The command's stdout.

    Raises:
        CheckError: If the command is unavailable or exits non-zero.
    """
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        msg = f"`{command[0]}` is not available on PATH"
        raise CheckError(msg) from exc
    if result.returncode != 0:
        msg = f"`{' '.join(command)}` failed:\n{result.stderr.strip()}"
        raise CheckError(msg)
    return result.stdout


def backend_packages() -> tuple[list[str], list[str]]:
    """Collect the backend outdated and installed package names via uv.

    Returns:
        ``(outdated, installed)`` package names.

    Raises:
        CheckError: If uv's JSON output cannot be parsed.
    """
    try:
        outdated = [
            entry["name"]
            for entry in json.loads(
                _run(["uv", "pip", "list", "--outdated", "--format", "json"])
            )
        ]
        installed = [
            entry["name"]
            for entry in json.loads(_run(["uv", "pip", "list", "--format", "json"]))
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        msg = f"could not parse `uv pip list` output: {exc}"
        raise CheckError(msg) from exc
    return outdated, installed


def parse_bun_outdated(output: str) -> list[str]:
    """Extract package names from a ``bun outdated`` table.

    Bun renders a markdown-style table whose package column is right-padded, with ``|---|``
    rules between rows and a ``Package`` header. Everything but the data rows is dropped.

    Rows for anything outside ``dependencies`` carry a behavior annotation in the package
    cell (``tailwindcss (dev)``, ``react (peer)``, ``clsx (optional)``), which is stripped
    so the bare name is what gets matched. npm names cannot contain spaces, so the suffix is
    unambiguous.

    Args:
        output: Raw stdout from ``bun outdated``.

    Returns:
        The outdated package names, without behavior annotations.
    """
    names = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-"):
            continue
        name = stripped.split("|")[1].strip()
        for annotation in BUN_ANNOTATIONS:
            if name.endswith(annotation):
                name = name[: -len(annotation)].rstrip()
                break
        if not name or name == "Package":
            continue
        names.append(name)
    return names


def frontend_packages(web_dir: Path) -> tuple[list[str], list[str]]:
    """Collect the frontend outdated and declared package names via bun.

    Args:
        web_dir: Directory holding the generated ``package.json``.

    Returns:
        ``(outdated, declared)`` package names.

    Raises:
        CheckError: If ``package.json`` is missing or unparseable.
    """
    outdated = parse_bun_outdated(_run(["bun", "outdated"], cwd=web_dir))

    package_json = web_dir / "package.json"
    try:
        with package_json.open() as f:
            manifest = json.load(f)
    except FileNotFoundError as exc:
        msg = f"{package_json} not found; compile the app before checking"
        raise CheckError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"could not parse {package_json}: {exc}"
        raise CheckError(msg) from exc

    declared = [
        name for field in BUN_DEPENDENCY_FIELDS for name in manifest.get(field, {})
    ]
    return outdated, declared


def report(kind: str, outdated: list[str], installed: list[str]) -> int:
    """Print the outcome for one side of the check and return its exit code.

    Args:
        kind: Either ``"backend"`` or ``"frontend"``.
        outdated: Names of packages behind their latest release.
        installed: Names of every installed/declared package.

    Returns:
        0 if everything outdated is deliberately held, 1 otherwise.
    """
    held, pinned = _load_config(kind)
    reportable, suppressed, stale_holds = partition(outdated, installed, held, pinned)

    if suppressed:
        print(f"Held back ({len(suppressed)}), not reported:")
        for name in sorted(suppressed):
            print(f"  {name}")

    exit_code = 0

    if reportable:
        print(f"\nOutdated {kind} dependencies found:")
        for name in sorted(reportable):
            print(f"  {name}")
        exit_code = 1
    else:
        print(f"\nAll {kind} dependencies are up to date.")

    if stale_holds:
        print(
            f"\nStale `{kind}_held` entries in [tool.{CONFIG_TABLE}] "
            "(remove them, the hold is no longer needed):"
        )
        for entry in stale_holds:
            print(f"  {entry}")
        exit_code = 1

    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested dependency check.

    Args:
        argv: Command-line arguments, or None to read ``sys.argv``.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(
        description="Report outdated dependencies, ignoring deliberately held packages."
    )
    parser.add_argument("kind", choices=("backend", "frontend"))
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=Path(),
        help="directory holding the generated package.json (frontend only)",
    )
    args = parser.parse_args(argv)

    try:
        if args.kind == "backend":
            outdated, installed = backend_packages()
        else:
            outdated, installed = frontend_packages(args.web_dir)
        return report(args.kind, outdated, installed)
    except CheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
