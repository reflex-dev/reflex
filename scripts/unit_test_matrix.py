"""Select unit-test suites from the complete pull-request diff.

Consumes the same JSON-lines file records as changed_paths.py. Main-branch runs
use --all for a full suite with the workspace coverage floor. PRs run package
suites separately, following runtime workspace dependencies for source changes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10.
    import toml as tomllib

from scripts.changed_paths import changed_files

ROOT = Path(__file__).resolve().parents[1]
ALL_TESTS = "tests/units packages/*/tests/units"


def suite_paths(root: Path) -> dict[str, str]:
    """Discover package suites and the root suite.

    Args:
        root: Workspace directory.

    Returns:
        Test paths keyed by distribution name.
    """
    return {
        "reflex": "tests/units",
        **{
            tomllib.loads((path.parent.parent / "pyproject.toml").read_text())[
                "project"
            ]["name"]: path.relative_to(root).as_posix()
            for path in sorted((root / "packages").glob("*/tests/units"))
        },
    }


def dependency_graph(root: Path) -> dict[str, set[str]]:
    """Read runtime and optional workspace dependencies.

    Args:
        root: Workspace directory.

    Returns:
        Dependency names keyed by distribution name.
    """
    graph = {}
    for path in [
        root / "pyproject.toml",
        *sorted((root / "packages").glob("*/pyproject.toml")),
    ]:
        project = tomllib.loads(path.read_text())["project"]
        requirements = [*project.get("dependencies", [])]
        for extra in project.get("optional-dependencies", {}).values():
            requirements.extend(extra)
        graph[project["name"]] = {
            re
            .split(r"[\s\[<>=!~;@]", requirement, maxsplit=1)[0]
            .lower()
            .replace("_", "-")
            for requirement in requirements
        }
    return graph


def select_suites(changed: list[str], root: Path = ROOT) -> list[str]:
    """Select owners, runtime dependents, and root cross-package tests.

    Test-only edits run their owner alone. Shared fixtures, test tooling and
    dependency configuration run every suite. Empty diffs fail open.

    Args:
        changed: Changed paths, including both sides of renames.
        root: Workspace directory.

    Returns:
        Sorted distribution names whose suites should run.
    """
    suites = suite_paths(root)
    selected: set[str] = set()
    affected: set[str] = set()
    projects = {
        path.parent.name: tomllib.loads(path.read_text())["project"]["name"]
        for path in (root / "packages").glob("*/pyproject.toml")
    }
    if not changed:
        return sorted(suites)
    for path in changed:
        parts = Path(path).parts
        if path in {
            "pyproject.toml",
            "uv.lock",
            "conftest.py",
            ".python-version",
        } or path.startswith((
            "scripts/",
            ".github/actions/",
            ".github/workflows/unit_tests.yml",
        )):
            return sorted(suites)
        if path.startswith("tests/"):
            if (
                path.startswith((
                    "tests/units/",
                    "tests/integration/",
                    "tests/benchmarks/",
                    "tests/performance/",
                    "tests/type_checking/",
                ))
                and path
                not in {
                    "tests/units/conftest.py",
                    "tests/units/__init__.py",
                    "tests/units/mock_redis.py",
                }
                and not path.startswith("tests/units/states/")
            ):
                selected.add("reflex")
            else:
                return sorted(suites)
        elif path.startswith(".github/"):
            selected.add("reflex")
        elif path.startswith("reflex/"):
            # Package tests often construct rx.State or rx.App as test inputs.
            return sorted(suites)
        elif len(parts) >= 3 and parts[0] == "packages":
            if parts[1] not in projects:
                return sorted(suites)  # A removed or renamed package.
            name = projects[parts[1]]
            selected.add(name)
            if parts[2] != "tests":
                affected.add(name)
                selected.add("reflex")
    graph = dependency_graph(root)
    while (
        dependents := {name for name, deps in graph.items() if deps & affected}
        - affected
    ):
        affected.update(dependents)
    return sorted((selected | affected) & suites.keys())


def matrix(
    changed: list[str], *, all_tests: bool = False
) -> dict[str, list[dict[str, str]]]:
    """Build the suite axis consumed by the workflow.

    Args:
        changed: Complete changed-path list.
        all_tests: Whether to run everything together with full coverage.

    Returns:
        A matrix containing suite names, paths and coverage thresholds.
    """
    suites = suite_paths(ROOT)
    selected = select_suites(changed) if not all_tests else sorted(suites)
    if all_tests or selected == sorted(suites):
        return {"suite": [{"name": "all", "path": ALL_TESTS, "coverage": "72"}]}
    return {
        "suite": [
            {"name": name, "path": suites[name], "coverage": "0"} for name in selected
        ]
    }


def main() -> None:
    """Write the suite matrix and whether any suites were selected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    result = matrix(
        changed_files(sys.stdin) if not args.all else [], all_tests=args.all
    )
    print(f"matrix={json.dumps(result, separators=(',', ':'))}")
    print(f"run={'true' if result['suite'] else 'false'}")


if __name__ == "__main__":
    main()
