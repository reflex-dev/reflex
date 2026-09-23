"""Generate the synchronous reflex-build-sdk client and its tests from the asynchronous source.

The ``_async`` packages are the source of truth; each module is copied to the
matching ``_sync`` package with the async syntax and names replaced, then
formatted with ruff. The httpx2 transport and its tests are generated from the
httpx ones the same way. Run with ``--check`` to fail when the generated files
are stale instead of writing them.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# The repository root: this script lives in packages/reflex-build-sdk/scripts.
ROOT = Path(__file__).resolve().parents[3]

# Source directory -> generated directory.
DIRECTORIES = {
    ROOT / "packages/reflex-build-sdk/src/reflex_build_sdk/_async": ROOT
    / "packages/reflex-build-sdk/src/reflex_build_sdk/_sync",
    ROOT / "tests/units/reflex_build_sdk/_async": ROOT
    / "tests/units/reflex_build_sdk/_sync",
}

Substitutions = list[tuple[re.Pattern[str], str]]


def _compile(*substitutions: tuple[str, str]) -> Substitutions:
    return [
        (re.compile(pattern), replacement) for pattern, replacement in substitutions
    ]


UNASYNC = _compile(
    (r"\bAsync([A-Z]\w*)", r"\1"),
    (r"\basync_(\w)", r"\1"),
    (r"\bAiohttpTransport\b", "Httpx2Transport"),
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

# httpx2 is a fork of httpx with the same API under another name.
TO_HTTPX2 = _compile(
    (r"\bhttpx\b", "httpx2"),
    (r"Httpx(?=Transport)", "Httpx2"),
)

# Ends the first line of every generated module.
GENERATED_BY = "by packages/reflex-build-sdk/scripts/unasync.py. Do not edit."

# The trees searched for generated files that are no longer generated.
GENERATED_ROOTS = (
    ROOT / "packages/reflex-build-sdk/src",
    ROOT / "tests/units/reflex_build_sdk",
)

# Source file -> generated file, for files generated with TO_HTTPX2.
FILES = {
    ROOT / "packages/reflex-build-sdk/src/reflex_build_sdk/transports/_httpx.py": ROOT
    / "packages/reflex-build-sdk/src/reflex_build_sdk/transports/_httpx2.py",
    ROOT / "tests/units/reflex_build_sdk/transports/test_httpx.py": ROOT
    / "tests/units/reflex_build_sdk/transports/test_httpx2.py",
}


def substitute(source: str, substitutions: Substitutions) -> str:
    """Apply substitutions to source code.

    Args:
        source: The source code.
        substitutions: The patterns to replace, with their replacements, in order.

    Returns:
        The substituted source, not yet formatted.
    """
    for pattern, replacement in substitutions:
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


def generate(source_path: Path, substitutions: Substitutions) -> str:
    """Generate a module from its source module.

    Args:
        source_path: The source module.
        substitutions: The substitutions turning it into the generated module.

    Returns:
        The formatted generated module source.
    """
    header = (
        f"# Generated from {source_path.relative_to(ROOT).as_posix()} {GENERATED_BY}\n"
    )
    source = header + substitute(source_path.read_text(), substitutions)
    # Renamed imports can fall out of sort order and shortened lines can fit
    # on fewer lines, so the output is formatted like any checked-in module.
    # Ruff is pointed at the source path: it tells first-party imports apart by
    # the file's package, which a not-yet-generated target does not have.
    source = _ruff(["check", "--fix", "--select", "I", "--quiet"], source, source_path)
    return _ruff(["format", "--quiet"], source, source_path)


def expected_files() -> dict[Path, str]:
    """Generate every module.

    Returns:
        The content of each generated module, by path.
    """
    expected = {
        target_dir / source_path.relative_to(source_dir): generate(source_path, UNASYNC)
        for source_dir, target_dir in DIRECTORIES.items()
        for source_path in sorted(source_dir.rglob("*.py"))
    }
    expected.update(
        (target_path, generate(source_path, TO_HTTPX2))
        for source_path, target_path in FILES.items()
    )
    return expected


def _is_generated(path: Path) -> bool:
    with path.open() as file:
        return file.readline().rstrip("\n").endswith(GENERATED_BY)


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
    # Generated files outside DIRECTORIES share their directory with source files,
    # so only those carrying the generated header are orphans.
    stale.extend(
        path
        for root in GENERATED_ROOTS
        for path in sorted(root.rglob("*.py"))
        if path not in expected and _is_generated(path)
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
