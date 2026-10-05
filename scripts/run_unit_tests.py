"""Run an owning suite with its package coverage floor, or every suite separately.

Usage: uv run python -m scripts.run_unit_tests reflex-base [-- pytest arguments]
Coverage files are retained as .coverage.<distribution> for later combination.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from scripts.unit_test_matrix import ROOT, suite_paths, tomllib


def run_suite(name: str, test_path: str, pytest_args: list[str]) -> int:
    """Run one suite and enforce coverage only for its owning distribution.

    Args:
        name: Distribution name.
        test_path: Suite path relative to the workspace root.
        pytest_args: Additional pytest arguments.

    Returns:
        A nonzero exit code if tests fail or the package coverage floor is missed.
    """
    package = ROOT if name == "reflex" else (ROOT / test_path).parents[1]
    config = tomllib.loads((package / "pyproject.toml").read_text())
    floor = config["tool"]["reflex-unit-tests"]["coverage"]
    source = package / ("reflex" if name == "reflex" else "src")
    print(f"\n{name}: coverage >= {floor}% of {source.relative_to(ROOT)}", flush=True)
    env = {**os.environ, "COVERAGE_FILE": str(ROOT / f".coverage.{name}")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "--cov",
            f"--cov-config={ROOT / 'pyproject.toml'}",
            "--cov-fail-under=0",
            "--cov-report=",
            "--no-cov-on-fail",
            *pytest_args,
        ],
        cwd=ROOT,
        env=env,
        check=False,
    ).returncode
    if result or "--no-cov" in pytest_args:
        return result
    # Collect workspace coverage for the secondary aggregate, but only this
    # package's own source contributes to its independently enforced floor.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "report",
            f"--rcfile={ROOT / 'pyproject.toml'}",
            f"--include={source}/*",
            f"--fail-under={floor}",
            "--skip-covered",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    ).returncode


def main() -> None:
    """Run selected suites independently, propagating any test or coverage failure."""
    suites = suite_paths(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", nargs="?", default="all", choices=["all", *suites])
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    selected = suites if args.suite == "all" else {args.suite: suites[args.suite]}
    failed = False
    for name, path in selected.items():
        if name == "reflex-bench" and sys.platform != "linux":
            print("Skipping reflex-bench: its tests require Linux.", flush=True)
            continue
        failed |= run_suite(name, path, pytest_args) != 0
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
