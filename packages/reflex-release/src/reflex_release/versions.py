"""Release actions and the version arithmetic behind them."""

from __future__ import annotations

import datetime
import zoneinfo

from packaging.version import Version

from .actions import fail

#: Maps a dispatch action to the ``(mode, submode)`` driving :func:`next_version`.
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

#: Actions that materialize a final version (as opposed to an alpha).
FINAL_ACTIONS = frozenset(
    action for action, (mode, _) in ACTIONS.items() if mode == "release"
)


def next_version(current: Version | None, action: str, package: str) -> str:
    """Compute the next version for a package given a release action.

    Args:
        current: The baseline version, or None if the package was never
            released.
        action: One of the keys in :data:`ACTIONS`.
        package: Package name, used for error messages.

    Returns:
        The next version string (canonical PEP 440, no ``v`` prefix).
    """
    mode, sub = ACTIONS[action]

    if current is None:
        major = minor = patch = alpha_n = post_n = 0
        is_alpha = False
    else:
        major, minor, patch = current.major, current.minor, current.micro
        is_alpha = current.pre is not None and current.pre[0] == "a"
        alpha_n = current.pre[1] if is_alpha and current.pre is not None else 0
        post_n = current.post or 0

    display = str(current) if current is not None else "<none>"
    # Only aN prereleases are produced by this tooling; a b/rc heading means the
    # changelog was edited outside the sanctioned flow.
    alpha_hint = (
        " (only alpha aN prereleases are supported)"
        if current is not None and current.pre is not None and not is_alpha
        else ""
    )

    if mode == "new-prerelease":
        if current is not None and current.is_prerelease:
            fail(
                f"new-prerelease-* would abandon the in-progress {display} train "
                f"for {package}; use continued-prerelease or "
                "release-from-prerelease on its prerelease branch, or dispatch "
                "from the main branch to start a new train"
            )
        if sub == "patch":
            return f"{major}.{minor}.{patch + 1}a1"
        if sub == "minor":
            return f"{major}.{minor + 1}.0a1"
        return f"{major + 1}.0.0a1"

    if mode == "continued-prerelease":
        if not is_alpha:
            fail(
                "continued-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}{alpha_hint}"
            )
        return f"{major}.{minor}.{patch}a{alpha_n + 1}"

    if sub == "from-prerelease":
        if not is_alpha:
            fail(
                "release-from-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}{alpha_hint}"
            )
        return f"{major}.{minor}.{patch}"
    if sub == "post":
        if current is None:
            fail(f"release-post requires an existing release; none for {package}")
        if current.is_prerelease or current.is_devrelease:
            fail(
                "release-post can only follow a final release; newest for "
                f"{package} is {display!r}"
            )
        return f"{major}.{minor}.{patch}.post{post_n + 1}"
    if sub == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if sub == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"


def release_date_today(timezone: str) -> str:
    """Return today's date in the project's release timezone.

    CI runners run on UTC, which would date an evening release with tomorrow's
    date, so changelog headings and prerelease branch names are both stamped in
    the project's home timezone.

    Args:
        timezone: An IANA timezone name.

    Returns:
        The date in ISO format (YYYY-MM-DD).
    """
    try:
        tz = zoneinfo.ZoneInfo(timezone)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        fail(f"unknown release-timezone {timezone!r}")
    return datetime.datetime.now(tz).date().isoformat()
