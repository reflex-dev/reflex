"""Bisect the suite-order polluter of test_app_modify_state_clean (PR #6757)."""

import subprocess
import sys

TARGET = "tests/units/test_app.py::test_app_modify_state_clean"


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
        "app_mixins+compiler": run("app_mixins+compiler", ["tests/units/app_mixins", "tests/units/compiler"]),
        "components": run("components", ["tests/units/components"]),
        "docgen+middleware+plugins": run("docgen+middleware+plugins", ["tests/units/docgen", "tests/units/middleware", "tests/units/plugins"]),
        "reflex_cli+states": run("reflex_cli+states", ["tests/units/reflex_cli", "tests/units/states"]),
    }
    print("RESULTS:", results)


main()
