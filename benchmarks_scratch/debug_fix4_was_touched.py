"""Validate RUF029 fix on eng-10095: ruff + proxy tests."""

import subprocess
import sys


def run(label: str, cmd: list[str]) -> int:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-4:])
    print(f"[{label}] exit={proc.returncode}\n{tail}\n", flush=True)
    return proc.returncode


def main():
    ruff = run("ruff", ["ruff", "check", "tests/units/istate/test_proxy.py", "tests/units/reflex_base/vars/test_base.py"])
    tests = run(
        "pytest",
        [sys.executable, "-m", "pytest", "tests/units/istate/test_proxy.py", "tests/units/reflex_base/vars/test_base.py", "-q", "--no-header", "-p", "no:cacheprovider"],
    )
    print(f"RESULTS: ruff={ruff} pytest={tests}")


main()
