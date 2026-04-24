# /// script
# requires-python = ">=3.10"
# dependencies = ["packaging"]
# ///
"""Plan the next version for each selected package.

Reads PACKAGES_JSON and ACTION from env, computes the next version per package
using packaging.Version, writes a markdown summary to GITHUB_STEP_SUMMARY and a
JSON array to GITHUB_OUTPUT for the release matrix.
"""

from __future__ import annotations

import json
import operator
import os
import pathlib
import subprocess
import sys
from typing import NoReturn

from packaging.version import InvalidVersion, Version

ACTIONS: dict[str, tuple[str, str | None]] = {
    "new-prerelease-patch": ("new-prerelease", "patch"),
    "new-prerelease-minor": ("new-prerelease", "minor"),
    "new-prerelease-major": ("new-prerelease", "major"),
    "continued-prerelease": ("continued-prerelease", None),
    "release-from-prerelease": ("release", "from-prerelease"),
    "release-post": ("release", "post"),
    "release-patch": ("release", "patch"),
    "release-minor": ("release", "minor"),
    "release-major": ("release", "major"),
}


def fail(message: str) -> NoReturn:
    """Print to stderr and exit 1."""
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(1)


def pick_latest(prefix: str) -> str | None:
    """Return the largest PEP 440 tag under prefix (prefix stripped), or None.

    Args:
        prefix: Tag prefix, e.g. ``v`` or ``reflex-base-v``.
    """
    raw = subprocess.check_output(["git", "tag", "-l", f"{prefix}*"], text=True)
    pairs: list[tuple[Version, str]] = []
    for line in raw.splitlines():
        tag = line.removeprefix(prefix).strip()
        if not tag:
            continue
        try:
            pairs.append((Version(tag), tag))
        except InvalidVersion:
            continue
    if not pairs:
        return None
    _, original = max(pairs, key=operator.itemgetter(0))
    return original


def next_version(latest: str | None, action: str, pkg: str) -> str:
    """Compute the next version for pkg given action and latest.

    Args:
        latest: Current latest version string, or None if the package has no prior tags.
        action: One of the keys in ACTIONS.
        pkg: Package name, used for error messages.

    Returns:
        The next version string.
    """
    mode, sub = ACTIONS[action]

    if latest is None:
        major = minor = patch = alpha_n = post_n = 0
        is_alpha = False
    else:
        ver = Version(latest)
        major, minor, patch = ver.major, ver.minor, ver.micro
        is_alpha = ver.pre is not None and ver.pre[0] == "a"
        alpha_n = ver.pre[1] if is_alpha and ver.pre is not None else 0
        post_n = ver.post or 0

    display = latest if latest is not None else "<none>"

    if mode == "new-prerelease":
        if sub == "patch":
            return f"{major}.{minor}.{patch + 1}a1"
        if sub == "minor":
            return f"{major}.{minor + 1}.0a1"
        return f"{major + 1}.0.0a1"

    if mode == "continued-prerelease":
        if not is_alpha:
            fail(
                f"continued-prerelease requires latest to be an alpha; "
                f"latest for {pkg} is {display!r}"
            )
        return f"{major}.{minor}.{patch}a{alpha_n + 1}"

    if sub == "from-prerelease":
        if not is_alpha:
            fail(
                f"release-from-prerelease requires latest to be an alpha; "
                f"latest for {pkg} is {display!r}"
            )
        return f"{major}.{minor}.{patch}"
    if sub == "post":
        if latest is None:
            fail(f"release-post requires an existing release; no tags for {pkg}")
        if is_alpha:
            fail(
                f"release-post cannot follow an alpha; latest for {pkg} is {display!r}"
            )
        return f"{major}.{minor}.{patch}.post{post_n + 1}"
    if sub == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if sub == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"


def tag_exists(tag: str) -> bool:
    """Return whether a local git tag exists."""
    return (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def main() -> None:
    """Entry point."""
    action = os.environ["ACTION"]
    packages_json = os.environ["PACKAGES_JSON"]
    github_output = os.environ["GITHUB_OUTPUT"]
    github_step_summary = os.environ["GITHUB_STEP_SUMMARY"]

    if action not in ACTIONS:
        fail(f"unknown action '{action}'")

    packages: list[str] = json.loads(packages_json)

    summary_rows = [
        "## Release plan",
        "",
        f"Action: `{action}`",
        "",
        "| Package | Current | Next | Tag |",
        "|---------|---------|------|-----|",
    ]
    releases: list[dict[str, str]] = []

    for pkg in packages:
        tag_prefix = "v" if pkg == "reflex" else f"{pkg}-v"
        current = pick_latest(tag_prefix)
        next_ver = next_version(current, action, pkg)
        tag = f"{tag_prefix}{next_ver}"

        if tag_exists(tag):
            fail(f"tag {tag} already exists")

        display = current if current is not None else "<none>"
        summary_rows.append(f"| `{pkg}` | `{display}` | `{next_ver}` | `{tag}` |")
        releases.append({
            "package": pkg,
            "current": current or "",
            "next": next_ver,
            "tag": tag,
        })

    # reflex is not independently releasable via dispatch: when reflex-base is
    # released, reflex is released alongside it with a matching version. The
    # publish workflow pins reflex-base exactly when building reflex.
    reflex_base_release = next(
        (r for r in releases if r["package"] == "reflex-base"), None
    )
    if reflex_base_release is not None:
        reflex_version = reflex_base_release["next"]
        reflex_tag = f"v{reflex_version}"
        if tag_exists(reflex_tag):
            fail(f"tag {reflex_tag} already exists")
        current_reflex = pick_latest("v")
        display = current_reflex if current_reflex is not None else "<none>"
        summary_rows.append(
            f"| `reflex` | `{display}` | `{reflex_version}` | `{reflex_tag}` |"
        )
        releases.append({
            "package": "reflex",
            "current": current_reflex or "",
            "next": reflex_version,
            "tag": reflex_tag,
        })

    with pathlib.Path(github_step_summary).open("a") as f:
        f.write("\n".join(summary_rows) + "\n")
    with pathlib.Path(github_output).open("a") as f:
        f.write(f"releases={json.dumps(releases)}\n")


if __name__ == "__main__":
    main()
