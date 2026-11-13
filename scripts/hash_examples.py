"""Update or check the content hash of the examples/playground benchmark fixture.

The macro benchmarks drive examples/playground and key their result series on its
content hash, so a change to the playground resets the benchmark baselines. The
hash covers every file under examples/playground that git tracks or would track
(untracked but not ignored), minus build output, so running the app locally never
changes it.

Run ``uv run python scripts/hash_examples.py`` to rewrite
``examples/playground/.content-hash``, or pass ``--check`` to fail when it is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

PLAYGROUND_DIR = Path(__file__).resolve().parent.parent / "examples" / "playground"
HASH_FILE_NAME = ".content-hash"
EXCLUDED_DIRS = frozenset({".web", ".states", "__pycache__", "uploaded_files"})
EXCLUDED_SUFFIXES = frozenset({".db", ".pyc"})
STALE_MESSAGE = (
    "examples/playground changed: benchmark baselines reset by this PR "
    "(update with: uv run python scripts/hash_examples.py)"
)


def hashed_files(root: Path) -> list[str]:
    """List the files the content hash covers.

    Args:
        root: The directory to hash, inside a git work tree.

    Returns:
        Sorted POSIX paths relative to ``root`` of the files git tracks or would
        track, excluding build output, the hash file and tracked files deleted
        from the work tree.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode()
    # A set: during a merge conflict, git lists a path once per stage.
    return sorted({
        path
        for path in listing.split("\0")
        if path
        and path != HASH_FILE_NAME
        and (posix_path := PurePosixPath(path)).suffix not in EXCLUDED_SUFFIXES
        and EXCLUDED_DIRS.isdisjoint(posix_path.parts[:-1])
        and (root / path).is_file()
    })


def content_hash(root: Path) -> str:
    """Compute the content hash of a directory.

    Args:
        root: The directory to hash, inside a git work tree.

    Returns:
        ``sha256:<hex>`` over each hashed file's relative path and bytes.
    """
    digest = hashlib.sha256()
    for path in hashed_files(root):
        # LF line endings, so a Windows checkout (core.autocrlf) hashes like CI.
        data = (root / path).read_bytes().replace(b"\r\n", b"\n")
        digest.update(f"{path}\0{len(data)}\0".encode())
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def main(argv: Sequence[str] | None = None) -> int:
    """Rewrite the playground's content hash file, or check that it is current.

    Args:
        argv: Command-line arguments, or None to read ``sys.argv``.

    Returns:
        The process exit code: 1 when ``--check`` finds a stale hash, else 0.
    """
    parser = argparse.ArgumentParser(
        description="Update the examples/playground content hash."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting the hash file when it is stale",
    )
    args = parser.parse_args(argv)

    hash_file = PLAYGROUND_DIR / HASH_FILE_NAME
    current = content_hash(PLAYGROUND_DIR)
    if hash_file.is_file() and hash_file.read_text().strip() == current:
        return 0
    if args.check:
        print(STALE_MESSAGE, file=sys.stderr)
        return 1
    hash_file.write_text(f"{current}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
