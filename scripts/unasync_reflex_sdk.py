"""Generate the synchronous reflex-sdk client and its tests from the asynchronous source.

The ``_async`` packages are the source of truth; each module is copied to the
matching ``_sync`` package with the async syntax and names replaced, then
formatted with ruff. Run with ``--check`` to fail when the generated files are
stale instead of writing them.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Source directory -> generated directory.
DIRECTORIES = {
    ROOT / "packages/reflex-sdk/src/reflex_sdk/_async": ROOT
    / "packages/reflex-sdk/src/reflex_sdk/_sync",
    ROOT / "tests/units/reflex_sdk/_async": ROOT / "tests/units/reflex_sdk/_sync",
}

SUBSTITUTIONS = [
    (re.compile(pattern), replacement)
    for pattern, replacement in (
        (r"\bAsync([A-Z]\w*)", r"\1"),
        (r"\bAsynchronous\b", "Synchronous"),
        (r"\basynchronous\b", "synchronous"),
        (r"\basync def\b", "def"),
        (r"\basync with\b", "with"),
        (r"\basync for\b", "for"),
        (r"\bawait ", ""),
        (r"\b__aenter__\b", "__enter__"),
        (r"\b__aexit__\b", "__exit__"),
        (r"\b__aiter__\b", "__iter__"),
        (r"\b__anext__\b", "__next__"),
        (r"\baclose\b", "close"),
        (r"\baread\b", "read"),
        (r"\baiter_bytes\b", "iter_bytes"),
        (r"\bimport asyncio\b", "import time"),
        (r"\basyncio\.sleep\b", "time.sleep"),
        (r"\b_async\b", "_sync"),
    )
]


def unasync_source(source: str) -> str:
    """Translate asynchronous source code to its synchronous equivalent.

    Args:
        source: The asynchronous module source.

    Returns:
        The synchronous module source, not yet formatted.
    """
    for pattern, replacement in SUBSTITUTIONS:
        source = pattern.sub(replacement, source)
    return source


def _ruff(args: list[str], source: str, filename: Path) -> str:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args, "--stdin-filename", str(filename), "-"],
        input=source,
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    ).stdout


def generate(source_path: Path) -> str:
    """Generate the synchronous version of an asynchronous module.

    Args:
        source_path: The asynchronous module.

    Returns:
        The formatted synchronous module source.
    """
    header = (
        f"# Generated from {source_path.relative_to(ROOT).as_posix()} by "
        "scripts/unasync_reflex_sdk.py. Do not edit.\n"
    )
    source = header + unasync_source(source_path.read_text())
    # Renamed imports can fall out of sort order and shortened lines can fit
    # on fewer lines, so the output is formatted like any checked-in module.
    # Ruff is pointed at the source path: it tells first-party imports apart by
    # the file's package, which a not-yet-generated target does not have.
    source = _ruff(["check", "--fix", "--select", "I", "--quiet"], source, source_path)
    return _ruff(["format", "--quiet"], source, source_path)


def expected_files() -> dict[Path, str]:
    """Generate every synchronous module.

    Returns:
        The content of each generated module, by path.
    """
    return {
        target_dir / source_path.relative_to(source_dir): generate(source_path)
        for source_dir, target_dir in DIRECTORIES.items()
        for source_path in sorted(source_dir.rglob("*.py"))
    }


def stale_files(expected: dict[Path, str]) -> list[Path]:
    """Find generated files that are missing, outdated or no longer generated.

    Args:
        expected: The content of each generated module, by path.

    Returns:
        The stale paths.
    """
    stale = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_text() != content
    ]
    stale.extend(
        path
        for target_dir in DIRECTORIES.values()
        if target_dir.is_dir()
        for path in sorted(target_dir.rglob("*.py"))
        if path not in expected
    )
    return stale


def main() -> int:
    """Write or check the generated modules.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the generated files are stale instead of writing them",
    )
    args = parser.parse_args()
    expected = expected_files()
    stale = stale_files(expected)
    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}")
        return 1 if stale else 0
    for path in stale:
        if path in expected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected[path])
            print(f"wrote {path.relative_to(ROOT)}")
        else:
            path.unlink()
            print(f"removed {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
