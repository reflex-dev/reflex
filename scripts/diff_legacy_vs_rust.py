"""Compare `reflex run` (legacy) output against `reflex run-rust` output.

Run from a project directory (e.g. ``docs/app/``):

    uv run python ../../scripts/diff_legacy_vs_rust.py            # summary
    uv run python ../../scripts/diff_legacy_vs_rust.py utils/context.js  # diff one file
    uv run python ../../scripts/diff_legacy_vs_rust.py --paths-only

The script:
1. Wipes ``.web/`` and runs the **legacy** compile (``reflex compile``).
2. Moves the result to ``.web_legacy/``.
3. Wipes ``.web/`` and runs the **rust** compile (``reflex run-rust --frontend-only``)
   in a subprocess that exits as soon as the compile finishes.
4. Moves the result to ``.web_rust/``.
5. Compares the two snapshots and prints a summary + per-path diff (legacy
   vs rust).

Use ``--keep`` to skip step 1-4 if the two snapshots are already on disk
from a previous run.
"""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

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
    "nocompile",
}


def _wipe(p: Path) -> None:
    if p.is_dir():
        shutil.rmtree(p)


def _move(src: Path, dst: Path) -> None:
    _wipe(dst)
    if src.is_dir():
        shutil.move(str(src), str(dst))


def _run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 600) -> None:
    print(f"$ {' '.join(cmd)}")
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    subprocess.run(cmd, check=True, env=full_env, timeout=timeout)


def _walk(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in _IGNORE for part in p.relative_to(root).parts):
            continue
        out[rel] = p
    return out


def _make_snapshots(project: Path) -> tuple[Path, Path]:
    web = project / ".web"
    legacy = project / ".web_legacy"
    rust = project / ".web_rust"

    # ---- legacy ----
    _wipe(web)
    print("=== legacy compile (reflex compile) ===")
    t0 = time.monotonic()
    _run(["uv", "run", "reflex", "compile"], env={"CI": "1"})
    print(f"  legacy compile finished in {time.monotonic() - t0:.1f}s")
    _move(web, legacy)

    # ---- rust ----
    _wipe(web)
    print("=== rust-only compile (reflex run-rust) ===")
    t0 = time.monotonic()
    # ``REFLEX_RUN_RUST_COMPILE_ONLY`` is read by ``run_rust`` (added by this
    # branch) — it exits cleanly right after the rust pipeline + dep install
    # so this script never has to start a dev server it would then have to
    # kill.
    _run(
        ["uv", "run", "reflex", "run-rust", "--frontend-only"],
        env={
            "CI": "1",
            "REFLEX_RUN_RUST_COMPILE_ONLY": "1",
            "REFLEX_RUST_NO_LEGACY_REBUILD": "1",
        },
    )
    print(f"  rust compile finished in {time.monotonic() - t0:.1f}s")
    _move(web, rust)

    return legacy, rust


def _summary(legacy: Path, rust: Path) -> int:
    a_files = _walk(legacy)
    b_files = _walk(rust)
    all_paths = sorted(set(a_files) | set(b_files))

    only_legacy: list[str] = []
    only_rust: list[str] = []
    differ: list[tuple[str, int, int]] = []
    same: int = 0

    for rel in all_paths:
        a = a_files.get(rel)
        b = b_files.get(rel)
        if a is None:
            only_rust.append(rel)
            continue
        if b is None:
            only_legacy.append(rel)
            continue
        ba = a.read_bytes()
        bb = b.read_bytes()
        if ba == bb:
            same += 1
        else:
            differ.append((rel, len(ba), len(bb)))

    print()
    print(f"legacy snapshot: {legacy}")
    print(f"rust snapshot:   {rust}")
    print()
    print(f"identical files:   {same}")
    print(f"differ:            {len(differ)}")
    print(f"only in legacy:    {len(only_legacy)}")
    print(f"only in rust:      {len(only_rust)}")
    print()

    if differ:
        print(f"{'path':<60} {'legacy':>10} {'rust':>10} {'Δ':>8}")
        print("-" * 92)
        for rel, na, nb in differ:
            print(f"  {rel:<58} {na:>10} {nb:>10} {nb - na:>+8}")
        print()

    if only_legacy:
        print("Only in legacy (rust must produce these):")
        for rel in only_legacy:
            print(f"  {rel}")
        print()
    if only_rust:
        print("Only in rust:")
        for rel in only_rust:
            print(f"  {rel}")
        print()

    return 0 if not (only_legacy or only_rust or differ) else 1


def _diff_one(legacy: Path, rust: Path, target: str) -> int:
    a_files = _walk(legacy)
    b_files = _walk(rust)

    matches: list[str] = []
    if target in a_files or target in b_files:
        matches.append(target)
    else:
        for rel in sorted(set(a_files) | set(b_files)):
            if rel.endswith("/" + target) or rel.endswith(target):
                matches.append(rel)
    if not matches:
        print(f"no match for {target!r}", file=sys.stderr)
        return 1
    for rel in matches:
        a = a_files.get(rel)
        b = b_files.get(rel)
        a_lines = a.read_text(errors="replace").splitlines(keepends=True) if a else []
        b_lines = b.read_text(errors="replace").splitlines(keepends=True) if b else []
        diff = list(
            difflib.unified_diff(
                a_lines,
                b_lines,
                fromfile=f"legacy/{rel}",
                tofile=f"rust/{rel}",
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
    parser.add_argument(
        "--keep",
        action="store_true",
        help="skip the compile steps; assume .web_legacy/ and .web_rust/ exist",
    )
    parser.add_argument("--project", default=".")
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="list mismatching paths, no byte counts",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    legacy = project / ".web_legacy"
    rust = project / ".web_rust"

    if not args.keep:
        _make_snapshots(project)

    if not legacy.is_dir() or not rust.is_dir():
        print(
            f"expected {legacy} and {rust} to exist. Re-run without --keep.",
            file=sys.stderr,
        )
        return 2

    if args.target:
        return _diff_one(legacy, rust, args.target)
    return _summary(legacy, rust)


if __name__ == "__main__":
    raise SystemExit(main())
