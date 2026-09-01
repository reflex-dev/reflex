"""Discover what a release train ships and confirm every package published to PyPI.

Reads the root CHANGELOG.md plus every packages/*/CHANGELOG.md at a git ref, takes the
top version entry from each, maps it to the PyPI distribution name declared in that
package's pyproject.toml, and checks the version exists on PyPI.

An unpublished version is a release blocker in its own right, so a missing package makes
this exit non-zero.

Usage (the script carries PEP 723 metadata and no shebang, so run it through uv):
    uv run --script check_release_versions.py --ref origin/r/pre-2026-08-27-1234
    uv run --script check_release_versions.py --ref origin/main --json
    uv run --script check_release_versions.py --ref origin/main --specs   # pkg==ver lines
"""

# /// script
# requires-python = ">=3.10"
# ///

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
QUOTED = re.compile(r"[\"']([^\"']+)[\"']")
ROOT_PACKAGE = re.compile(r"^root-package\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
PACKAGE_CHANGELOG = re.compile(r"packages/[^/]+/CHANGELOG\.md")
# Packages whose CHANGELOG.md does not name a release version, for two different
# reasons: never-published ones have no PyPI release at all, and internal ones are
# patch-released on every push to main rather than through the changelog.
EXCLUDED_KEYS = ("never-publish-packages", "internal-packages")


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


def excluded_changelogs(ref: str, repo: str) -> set[str]:
    """Read the changelogs that do not name a release version.

    A changelog in one of these packages must not be read as the version this train
    ships: a never-published package has no PyPI release for it to name, and an
    internal package is patch-released outside the changelog flow, so its heading
    would be checked against a version that was never cut. Either way the result would
    be a false blocker. Both lists name packages, and reflex-release resolves those
    names against the root package as well as the directories under ``packages-dir``,
    so the root changelog is excluded on the same terms as any other. Parsed with a
    regex rather than a TOML library to keep this script dependency-free on 3.10.

    Args:
        ref: The git ref to read the root ``pyproject.toml`` from.
        repo: Path to the reflex checkout.

    Returns:
        The set of repo-relative changelog paths to skip.
    """
    content = git_show(ref, "pyproject.toml", repo) or ""
    skip: set[str] = set()
    for key in EXCLUDED_KEYS:
        match = re.search(rf"^{key}\s*=\s*\[([^\]]*)\]", content, re.MULTILINE)
        if match:
            skip.update(QUOTED.findall(match.group(1)))
    root_match = ROOT_PACKAGE.search(content)
    root = root_match.group(1) if root_match else None
    return {
        "CHANGELOG.md" if name == root else f"packages/{name}/CHANGELOG.md"
        for name in skip
    }


def changelog_paths(ref: str, repo: str) -> list[str]:
    """Find the changelogs that describe a release train.

    Args:
        ref: The git ref to list files from.
        repo: Path to the reflex checkout.

    Returns:
        Paths of the root ``CHANGELOG.md`` and every ``packages/*/CHANGELOG.md``,
        minus the packages excluded by the release configuration.

    Raises:
        LookupError: The ref does not exist in that checkout.
    """
    result = subprocess.run(
        ["git", "-C", repo, "ls-tree", "-r", "--name-only", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # A mistyped ref is the likeliest way to misuse this, and a CalledProcessError
        # traceback buries that under a stack it has no use for.
        msg = f"cannot read ref {ref!r} in {repo}: {result.stderr.strip()}"
        raise LookupError(msg)
    skip = excluded_changelogs(ref, repo)
    return [
        path
        for path in result.stdout.splitlines()
        if path not in skip
        and (path == "CHANGELOG.md" or PACKAGE_CHANGELOG.fullmatch(path))
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


def pypi_status(name: str, version: str) -> tuple[str, str]:
    """Check whether a distribution version is installable from PyPI.

    The result distinguishes "definitely not published" from "could not tell", because a
    proxy hiccup reported as a missing package would be a false release blocker.

    Args:
        name: The PyPI distribution name.
        version: The version to look for.

    Returns:
        A ``(status, detail)`` tuple where status is ``"published"``, ``"missing"`` or
        ``"error"``, and detail names the artifact kinds found or why the check failed.
    """
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "missing", "NOT ON PYPI"
        return "error", f"HTTP {exc.code}"
    except Exception as exc:
        # Network/proxy trouble is indeterminate, not evidence the package is missing.
        return "error", f"check failed: {type(exc).__name__}"

    if not isinstance(data, dict) or not isinstance(data.get("urls"), list):
        # A proxy or error page that happens to parse as JSON is not evidence about the
        # release. Only PyPI's own shape, with urls present and empty, means "no files".
        return "error", "unexpected PyPI response shape"
    files = data["urls"]
    if not files:
        return "missing", "published but no files"
    if not all(
        isinstance(f, dict)
        and isinstance(f.get("packagetype"), str)
        # Absent means not yanked, which is fine; present but not a boolean means the
        # entry is not PyPI's and its yank state cannot be read from it.
        and isinstance(f.get("yanked", False), bool)
        for f in files
    ):
        # The list is there but its entries are not PyPI's, so reading them would raise
        # out of this function and end the run rather than reporting one bad check.
        return "error", "unexpected PyPI response shape"
    live = [u for u in files if not u.get("yanked")]
    if not live:
        # The version exists but every file is withdrawn: resolvers skip a yanked release
        # unless it is pinned exactly, and it was withdrawn for a reason.
        return "missing", "published but all files yanked"
    kinds = sorted({u["packagetype"] for u in live})
    detail = "+".join(k.replace("bdist_wheel", "wheel") for k in kinds)
    yanked = len(files) - len(live)
    return "published", f"{detail} ({yanked} yanked)" if yanked else detail


def main() -> int:
    """Run the discovery and print the results.

    Returns:
        ``1`` when a package is confirmed missing from PyPI (a release blocker), ``2``
        when a check could not be completed and the result is indeterminate, else ``0``.
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

    try:
        paths = sorted(changelog_paths(args.ref, args.repo))
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 2

    rows = []
    for path in paths:
        content = git_show(args.ref, path, args.repo) or ""
        name = dist_name(path, args.ref, args.repo)
        match = VERSION_HEADING.search(content)
        if match:
            version = match.group(1)
            status, detail = pypi_status(name, version)
        else:
            # Skipping the package silently would leave it unchecked, which is the exact
            # failure this script exists to catch; report it as indeterminate instead.
            version = "?"
            status, detail = "error", "no version heading in changelog"
        rows.append({
            "package": name,
            "version": version,
            "status": status,
            "detail": detail,
            "changelog": path,
            "prerelease": bool(re.search(r"[abc]|rc|dev", version.split(".")[-1])),
        })

    missing = [r for r in rows if r["status"] == "missing"]
    errors = [r for r in rows if r["status"] == "error"]
    marks = {"published": "OK ", "missing": "!! ", "error": "?? "}

    if args.specs:
        # Only confirmed-published rows: specs feed a downloader, so emitting a missing or
        # indeterminate package just moves the failure downstream. Skips go to stderr so
        # a short list is never silently mistaken for a complete one.
        for row in rows:
            if row["status"] == "published":
                print(f"{row['package']}=={row['version']}")
        for row in missing + errors:
            print(
                f"skipped {row['package']}=={row['version']} ({row['detail']})",
                file=sys.stderr,
            )
    elif args.json:
        print(
            json.dumps(
                {
                    "ref": args.ref,
                    "packages": rows,
                    "missing": len(missing),
                    "errors": len(errors),
                },
                indent=2,
            )
        )
    else:
        width = max((len(r["package"]) for r in rows), default=10)
        print(f"Release train at {args.ref}: {len(rows)} packages\n")
        for row in rows:
            tag = " (prerelease)" if row["prerelease"] else ""
            print(
                f"  {marks[row['status']]}{row['package']:<{width}}  "
                f"{row['version']:<12} {row['detail']}{tag}"
            )
        print()
        if missing:
            print(f"BLOCKER: {len(missing)} package(s) not installable from PyPI:")
            for row in missing:
                print(f"  - {row['package']}=={row['version']} ({row['detail']})")
        if errors:
            print(f"INDETERMINATE: {len(errors)} package(s) could not be checked:")
            for row in errors:
                print(f"  - {row['package']}=={row['version']} ({row['detail']})")
            print(
                "  Unchecked is not the same as missing — resolve each before releasing."
            )
        if not missing and not errors:
            print("All packages are published and installable.")

    if missing:
        return 1
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
