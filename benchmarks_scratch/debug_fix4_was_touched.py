"""Bisect the suite-order polluter of test_app_modify_state_clean (PR #6757)."""

import subprocess
import sys

TARGET = "tests/units/test_app.py::test_app_modify_state_clean"
PRE_DIRS = [
    "tests/units/app_mixins",
    "tests/units/compiler",
    "tests/units/components",
    "tests/units/docgen",
    "tests/units/istate",
    "tests/units/middleware",
    "tests/units/plugins",
    "tests/units/reflex_base",
    "tests/units/reflex_cli",
    "tests/units/states",
]


def run(label: str, args: list[str]) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, TARGET, "-q", "--no-header", "-p", "no:cacheprovider"],
        check=False,
        capture_output=True,
        text=True,
    )
    tail = "\n".join(proc.stdout.strip().splitlines()[-3:])
    print(f"[{label}] exit={proc.returncode}\n{tail}\n", flush=True)
    return proc.returncode


def main():
    results = {
        "all-pre": run("all-pre", PRE_DIRS),
        "first-half": run("first-half", PRE_DIRS[:5]),
        "second-half": run("second-half", PRE_DIRS[5:]),
    }
    print("RESULTS:", results)


main()
