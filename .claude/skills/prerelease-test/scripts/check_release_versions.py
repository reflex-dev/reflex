#!/usr/bin/env python3
"""Discover what a release train ships and confirm every package published to PyPI.

Reads the root CHANGELOG.md plus every packages/*/CHANGELOG.md at a git ref, takes the
top version entry from each, maps it to the PyPI distribution name declared in that
package's pyproject.toml, and checks the version exists on PyPI.

An unpublished version is a release blocker in its own right, so a missing package makes
this exit non-zero.

Usage:
    check_release_versions.py --ref origin/r/pre-2026-08-27-1234
    check_release_versions.py --ref origin/main --json
    check_release_versions.py --ref origin/main --specs   # pkg==ver lines for audit_pyi.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

VERSION_HEADING = re.compile(r"^##\s+v?([0-9][^\s]*)", re.MULTILINE)
PROJECT_NAME = re.compile(r"^name\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def git_show(ref: str, path: str, repo: str) -> str | None:
    """Read a file's contents at a git ref.

    Args:
        ref: The git ref to read from.
        path: Repo-relative path of the file.
        repo: Path to the reflex checkout.

    Returns:
        The file contents, or ``None`` when the path does not exist at that ref.
    """
    result = subprocess.run(
        ["git", "-C", repo, "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def changelog_paths(ref: str, repo: str) -> list[str]:
    """Find the changelogs that describe a release train.

    Args:
        ref: The git ref to list files from.
        repo: Path to the reflex checkout.

    Returns:
        Paths of the root ``CHANGELOG.md`` and every ``packages/*/CHANGELOG.md``.
    """
    listing = subprocess.run(
        ["git", "-C", repo, "ls-tree", "-r", "--name-only", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [
        p
        for p in listing
        if p == "CHANGELOG.md" or re.fullmatch(r"packages/[^/]+/CHANGELOG.md", p)
    ]


def dist_name(changelog_path: str, ref: str, repo: str) -> str:
    """Resolve the PyPI distribution name for the package owning a changelog.

    Args:
        changelog_path: Repo-relative path of the package's ``CHANGELOG.md``.
        ref: The git ref to read ``pyproject.toml`` from.
        repo: Path to the reflex checkout.

    Returns:
        The declared project name, falling back to the package directory name.
    """
    pyproject_path = changelog_path.replace("CHANGELOG.md", "pyproject.toml")
    content = git_show(ref, pyproject_path, repo) or ""
    match = PROJECT_NAME.search(content)
    if match:
        return match.group(1)
    # Fall back to the directory name, which matches the dist name by convention.
    parts = changelog_path.split("/")
    return parts[1] if len(parts) > 2 else "reflex"


def pypi_status(name: str, version: str) -> tuple[bool, str]:
    """Check whether a distribution version is installable from PyPI.

    Args:
        name: The PyPI distribution name.
        version: The version to look for.

    Returns:
        A ``(published, detail)`` tuple, where detail names the artifact kinds found or
        why the check failed.
    """
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
        kinds = sorted({u["packagetype"] for u in data.get("urls", [])})
        if not kinds:
            return False, "published but no files"
        return True, "+".join(
            k.replace("bdist_wheel", "wheel").replace("sdist", "sdist") for k in kinds
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, "NOT ON PYPI"
        return False, f"HTTP {exc.code}"
    except (
        Exception
    ) as exc:  # network/proxy trouble should not look like a missing package
        return False, f"check failed: {type(exc).__name__}"


def main() -> int:
    """Run the discovery and print the results.

    Returns:
        ``1`` when any package is missing from PyPI, otherwise ``0``.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref", required=True, help="git ref carrying the release changelogs"
    )
    parser.add_argument(
        "--repo", default=".", help="path to the reflex checkout (default: cwd)"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of a table"
    )
    parser.add_argument(
        "--specs",
        action="store_true",
        help="emit 'name==version' lines only (feed to audit_pyi.py)",
    )
    args = parser.parse_args()

    rows = []
    for path in sorted(changelog_paths(args.ref, args.repo)):
        content = git_show(args.ref, path, args.repo) or ""
        match = VERSION_HEADING.search(content)
        if not match:
            continue
        version = match.group(1)
        name = dist_name(path, args.ref, args.repo)
        published, detail = pypi_status(name, version)
        rows.append({
            "package": name,
            "version": version,
            "published": published,
            "detail": detail,
            "changelog": path,
            "prerelease": bool(re.search(r"[abc]|rc|dev", version.split(".")[-1])),
        })

    missing = [r for r in rows if not r["published"]]

    if args.specs:
        for row in rows:
            print(f"{row['package']}=={row['version']}")
    elif args.json:
        print(
            json.dumps(
                {"ref": args.ref, "packages": rows, "missing": len(missing)}, indent=2
            )
        )
    else:
        width = max((len(r["package"]) for r in rows), default=10)
        print(f"Release train at {args.ref}: {len(rows)} packages\n")
        for row in rows:
            mark = "OK " if row["published"] else "!! "
            tag = " (prerelease)" if row["prerelease"] else ""
            print(
                f"  {mark}{row['package']:<{width}}  {row['version']:<12} {row['detail']}{tag}"
            )
        print()
        if missing:
            print(f"BLOCKER: {len(missing)} package(s) not installable from PyPI:")
            for row in missing:
                print(f"  - {row['package']}=={row['version']} ({row['detail']})")
        else:
            print("All packages are published and installable.")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
