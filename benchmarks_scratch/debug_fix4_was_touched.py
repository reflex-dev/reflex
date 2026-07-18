"""Bisect test_app_modify_state_clean failure scope (debug for PR #6757)."""

import subprocess
import sys


def run(args: list[str]) -> int:
    print(f"$ pytest {' '.join(args)}", flush=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-q", "--no-header", "-p", "no:cacheprovider"],
        check=False,
    )
    print(f"exit={proc.returncode}", flush=True)
    return proc.returncode


def main():
    rc1 = run(["tests/units/test_app.py", "-k", "modify_state_clean"])
    rc2 = run(["tests/units/test_app.py"])
    rc3 = run(["tests/units/istate", "tests/units/reflex_base", "tests/units/test_app.py", "-k", "modify_state_clean or istate or reflex_base"])
    print(f"RESULTS: selection={rc1} file={rc2} cross-file={rc3}")


main()
