"""Run the rx.ui parity harness: one command for the look and the behaviour.

    uv run python scripts/ui_parity.py box            one component, in Chromium
    uv run python scripts/ui_parity.py                every component, in Chromium
    uv run python scripts/ui_parity.py --all-engines  and in Firefox and WebKit
    uv run python scripts/ui_parity.py differences    the intended differences, as markdown

The checks are the tests of tests/integration/tests_playwright/test_ui_parity.py;
this builds the pytest command for them.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
PARITY = REPO_ROOT / "packages" / "reflex-components-ui" / "parity"
TESTS = "tests/integration/tests_playwright/test_ui_parity.py"
ENGINES = ("chromium", "firefox", "webkit")
DIFFERENCES = "differences"


def pytest_command(
    components: list[str], engines: list[str], extra: list[str]
) -> list[str]:
    """Build the pytest command of a run.

    Args:
        components: The components to check: every one when empty.
        engines: The browser engines to run in.
        extra: Arguments passed on to pytest.

    Returns:
        The command.
    """
    command = [sys.executable, "-m", "pytest", TESTS, "-rs"]
    for engine in engines:
        command += ["--browser", engine]
    if components:
        # A test id holds its component after the engine: "chromium-box]" for
        # a matrix, "chromium-box-rx.ui-..." for a step. The run time is
        # recorded whatever ran, and is named first: an expression that starts
        # with "-center" would be read as the option "-c".
        selected = [f"-{name}] or -{name}-" for name in components]
        command += ["-k", " or ".join(["test_run_time", *selected])]
    return command + extra


def main(argv: list[str] | None = None) -> int:
    """Run the harness, or print the intended differences.

    Args:
        argv: The command line, without the program name.

    Returns:
        The exit code: that of pytest.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument(
        "components",
        nargs="*",
        help=f'components to check (default: all), or "{DIFFERENCES}"',
    )
    parser.add_argument(
        "--engine",
        action="append",
        choices=ENGINES,
        help="a browser engine to run in; may be repeated (default: chromium)",
    )
    parser.add_argument(
        "--all-engines", action="store_true", help="run in every browser engine"
    )
    parser.add_argument(
        "--report",
        type=Path,
        help=f"where the report goes (default: {PARITY / 'report'})",
    )
    args, extra = parser.parse_known_args(argv)
    if args.components == [DIFFERENCES]:
        sys.path.insert(0, str(PARITY))
        from ui_parity import allowlist

        print(allowlist.differences_markdown(allowlist.load()))
        return 0
    env = dict(os.environ)
    if args.report is not None:
        env["UI_PARITY_REPORT"] = str(args.report.resolve())
    engines: list[str] = (
        list(ENGINES) if args.all_engines else args.engine or [ENGINES[0]]
    )
    return subprocess.run(
        pytest_command(args.components, engines, extra),
        cwd=REPO_ROOT,
        env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
