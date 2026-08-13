"""Validate review-fix commits on eng-10095: proxy + validation depth tests."""

import subprocess
import sys


def main():
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/units/istate/test_proxy.py",
            "tests/units/reflex_base/utils/test_types.py",
            "tests/units/test_state.py",
            "-q", "--no-header", "-p", "no:cacheprovider",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    print("\n".join(proc.stdout.strip().splitlines()[-6:]), flush=True)
    print(f"exit={proc.returncode}", flush=True)


main()
