"""Side-by-side diff of the Python-compiled ``.web_python`` reference vs the
current ``.web``.

Run from a project directory after::

    reflex run-rust --snapshot-python ...

Usage::

    python -m reflex.compiler.diff_pipelines              # summary table
    python -m reflex.compiler.diff_pipelines _index.jsx   # unified diff of one file
    python -m reflex.compiler.diff_pipelines --paths-only # just list mismatches
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Files/folders that don't carry pipeline-significant info — skip them so the
# diff focuses on semantic differences.
_IGNORE = {
    "node_modules",
    ".vite",
    "bun.lock",
    "package-lock.json",
    ".gitignore",
    "reflex.lock",
    "reflex.json",
    "reflex.install_frontend_packages.cached",
    ".npmrc",
    "bunfig.toml",
}


def _walk(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        # Skip any path that contains an ignored segment.
        if any(part in _IGNORE for part in p.relative_to(root).parts):
            continue
        out[rel] = p
    return out


def _summary(py_root: Path, rs_root: Path) -> int:
    py_files = _walk(py_root)
    rs_files = _walk(rs_root)
    all_paths = sorted(set(py_files) | set(rs_files))

    only_py: list[str] = []
    only_rs: list[str] = []
    differ: list[tuple[str, int, int]] = []
    same: int = 0
    for rel in all_paths:
        a = py_files.get(rel)
        b = rs_files.get(rel)
        if a is None:
            only_rs.append(rel)
            continue
        if b is None:
            only_py.append(rel)
            continue
        ba = a.read_bytes()
        bb = b.read_bytes()
        if ba == bb:
            same += 1
        else:
            differ.append((rel, len(ba), len(bb)))

    print(f"python reference: {py_root}")
    print(f"current .web:     {rs_root}")
    print()
    print(f"identical files:  {same}")
    print(f"differ:           {len(differ)}")
    print(f"only in python:   {len(only_py)}")
    print(f"only in current:  {len(only_rs)}")
    print()

    if differ:
        print(f"{'path':<60} {'py-bytes':>10} {'rs-bytes':>10} {'Δ':>8}")
        print("-" * 92)
        for rel, na, nb in differ:
            print(f"  {rel:<58} {na:>10} {nb:>10} {nb - na:>+8}")
        print()

    if only_py:
        print("Only in python reference:")
        for rel in only_py:
            print(f"  {rel}")
        print()
    if only_rs:
        print("Only in current .web:")
        for rel in only_rs:
            print(f"  {rel}")
        print()

    return 0 if not (only_py or only_rs or differ) else 1


def _diff_one(py_root: Path, rs_root: Path, target: str) -> int:
    """Print a unified diff for a single relative path or basename match."""
    py_files = _walk(py_root)
    rs_files = _walk(rs_root)

    matches: list[str] = []
    if target in py_files or target in rs_files:
        matches.append(target)
    else:
        for rel in sorted(set(py_files) | set(rs_files)):
            if rel.endswith("/" + target) or rel.endswith(target):
                matches.append(rel)
    if not matches:
        print(f"no match for {target!r}", file=sys.stderr)
        return 1
    for rel in matches:
        a = py_files.get(rel)
        b = rs_files.get(rel)
        a_lines = a.read_text(errors="replace").splitlines(keepends=True) if a else []
        b_lines = b.read_text(errors="replace").splitlines(keepends=True) if b else []
        diff = list(
            difflib.unified_diff(
                a_lines,
                b_lines,
                fromfile=f"python/{rel}",
                tofile=f"current/{rel}",
                n=3,
            )
        )
        if not diff:
            print(f"=== {rel}: identical ===")
            continue
        print(f"=== {rel} ===")
        sys.stdout.writelines(diff)
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        help="basename or relative path to show a unified diff for",
    )
    parser.add_argument("--python-dir", default=".web_python")
    parser.add_argument("--web-dir", default=".web")
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="list mismatching paths, no byte counts",
    )
    args = parser.parse_args()

    py_root = Path(args.python_dir).resolve()
    rs_root = Path(args.web_dir).resolve()

    if not py_root.is_dir():
        print(
            f"python reference not found at {py_root}. "
            f"Run `reflex run-rust --snapshot-python` first.",
            file=sys.stderr,
        )
        return 2
    if not rs_root.is_dir():
        print(f"current .web not found at {rs_root}", file=sys.stderr)
        return 2

    if args.target:
        return _diff_one(py_root, rs_root, args.target)
    return _summary(py_root, rs_root)


if __name__ == "__main__":
    raise SystemExit(main())
