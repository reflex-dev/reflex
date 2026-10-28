"""Check that the installed release packages carry exactly the source a release tag contains.

Lists every Python package source file that changed between two git refs (``reflex/`` and
``packages/<pkg>/src/<module>/``), maps each to its location in a venv's site-packages,
and compares the bytes. A file that differs, or one deleted at the tag that is still
installed, means PyPI serves something other than the tag: a mis-built or mis-tagged
release. A changed file of a package that is not installed in the venv is reported
separately — expected for unpublished workspace packages and for ones outside the
install graph, a finding when the package should be there.

Usage (PEP 723 script, no dependencies; run it from any directory):
    uv run --script check_wheel_sources.py --repo <checkout> --base v0.10.0 --ref v0.10.1a1 \
        --site-packages $SB/envs/new/lib/python3.12/site-packages
"""

# /// script
# requires-python = ">=3.11"
# ///

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_NAME = re.compile(r"^name\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
PACKAGE_SOURCE = re.compile(r"packages/([^/]+)/src/(.+)")


def git(repo: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run a git command in the checkout.

    Args:
        repo: Path to the reflex checkout.
        *args: The git arguments.

    Returns:
        The completed process, with stdout and stderr as bytes.
    """
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=False)


def installed_dists(site: Path) -> set[str]:
    """Collect the normalized distribution names installed in a site-packages directory.

    Args:
        site: The site-packages directory.

    Returns:
        Normalized names (lowercase, ``-``/``_``/``.`` folded to ``-``).
    """
    return {
        re.sub(
            r"[-_.]+", "-", d.name.removesuffix(".dist-info").rsplit("-", 1)[0]
        ).lower()
        for d in site.glob("*.dist-info")
    }


def dist_name(repo: str, ref: str, package_dir: str) -> str:
    """Read the distribution name a workspace package declares.

    Args:
        repo: Path to the reflex checkout.
        ref: The git ref to read ``pyproject.toml`` at.
        package_dir: The directory name under ``packages/``.

    Returns:
        The normalized distribution name, falling back to the directory name.
    """
    shown = git(repo, "show", f"{ref}:packages/{package_dir}/pyproject.toml")
    match = (
        PROJECT_NAME.search(shown.stdout.decode()) if shown.returncode == 0 else None
    )
    return re.sub(r"[-_.]+", "-", match.group(1) if match else package_dir).lower()


def classify(
    repo: str, ref: str, path: str, site: Path, names: dict[str, str]
) -> tuple[str, str] | None:
    """Compare one changed file of the checkout with its installed copy.

    Args:
        repo: Path to the reflex checkout.
        ref: The tag under test.
        path: The changed file, relative to the checkout.
        site: The site-packages directory.
        names: Cache of distribution names by ``packages/`` directory, filled as needed.

    Returns:
        The distribution and one of ``same``, ``differs``, ``stale`` (deleted at the tag,
        still installed) or ``deleted``; ``None`` for a file no distribution ships.
    """
    if not path.endswith((".py", ".pyi", ".js", ".jsx", ".json", ".css")):
        return None
    if path.startswith("reflex/"):
        target, dist = site / path, "reflex"
    elif match := PACKAGE_SOURCE.fullmatch(path):
        package_dir, rel = match.groups()
        if package_dir not in names:
            names[package_dir] = dist_name(repo, ref, package_dir)
        target, dist = site / rel, names[package_dir]
    else:
        return None
    at_ref = git(repo, "show", f"{ref}:{path}")
    if at_ref.returncode != 0:
        return dist, "stale" if target.exists() else "deleted"
    if not target.exists() or target.read_bytes() != at_ref.stdout:
        return dist, "differs"
    return dist, "same"


def report(results: dict[str, list[str]], uninstalled: dict[str, list[str]]) -> int:
    """Print the files that do not match the tag and the overall verdict.

    Args:
        results: Changed files of installed distributions, by status.
        uninstalled: Changed files of distributions missing from the venv, by name.

    Returns:
        ``1`` when a file differs or a deleted file is still installed, otherwise ``0``.
    """
    for path in results["differs"]:
        print(f"  DIFFERS OR MISSING  {path}")
    for path in results["stale"]:
        print(f"  DELETED AT TAG, STILL INSTALLED  {path}")
    for dist, paths in sorted(uninstalled.items()):
        print(f"  not installed: {dist} ({len(paths)} changed files)")
    if results["differs"] or results["stale"]:
        print("FAIL: the installed packages do not match the tag")
        return 1
    print("PASS")
    return 0


def main() -> int:
    """Compare the changed source files and print a summary.

    Returns:
        ``1`` when an installed file differs from the tag or a deleted file is still
        installed, ``2`` when the refs or the site-packages directory cannot be read or
        ``reflex`` is not installed there, otherwise ``0``.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="path to the reflex checkout")
    parser.add_argument("--base", required=True, help="previous release tag")
    parser.add_argument("--ref", required=True, help="tag under test")
    parser.add_argument(
        "--site-packages", required=True, type=Path, help="site-packages of the venv"
    )
    args = parser.parse_args()
    site: Path = args.site_packages
    dists = installed_dists(site) if site.is_dir() else set()
    if "reflex" not in dists:
        print(f"reflex is not installed in {site}", file=sys.stderr)
        return 2
    # Without renames, a moved file is a deletion plus an addition, so a stale copy at
    # the old path is still caught.
    diff = git(
        args.repo,
        "diff",
        "--no-renames",
        "--name-only",
        f"{args.base}..{args.ref}",
        "--",
    )
    if diff.returncode != 0:
        print(diff.stderr.decode().strip(), file=sys.stderr)
        return 2

    names: dict[str, str] = {}
    results: dict[str, list[str]] = {"same": [], "differs": [], "stale": []}
    uninstalled: dict[str, list[str]] = {}
    for path in diff.stdout.decode().splitlines():
        if (found := classify(args.repo, args.ref, path, site, names)) is None:
            continue
        dist, status = found
        if dist not in dists:
            uninstalled.setdefault(dist, []).append(path)
        elif status in results:
            results[status].append(path)

    print(
        f"{args.base}..{args.ref}: {len(results['same'])} changed source files "
        f"identical in {site}"
    )
    return report(results, uninstalled)


if __name__ == "__main__":
    sys.exit(main())
