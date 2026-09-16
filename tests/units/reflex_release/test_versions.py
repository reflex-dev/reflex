"""Tests for reflex_release.versions."""

from __future__ import annotations

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.versions import (
    ACTIONS,
    FINAL_ACTIONS,
    next_version,
    release_date_today,
)


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        ("1.2.3", "new-prerelease-patch", "1.2.4a1"),
        ("1.2.3", "new-prerelease-minor", "1.3.0a1"),
        ("1.2.3", "new-prerelease-major", "2.0.0a1"),
        ("1.2.4a1", "continued-prerelease", "1.2.4a2"),
        ("1.2.4a9", "continued-prerelease", "1.2.4a10"),
        ("1.2.4a3", "release-from-prerelease", "1.2.4"),
        ("1.2.3", "release-patch", "1.2.4"),
        ("1.2.3", "release-minor", "1.3.0"),
        ("1.2.3", "release-major", "2.0.0"),
        ("1.2.3", "release-post", "1.2.3.post1"),
        ("1.2.3.post1", "release-post", "1.2.3.post2"),
        (None, "release-minor", "0.1.0"),
        (None, "new-prerelease-patch", "0.0.1a1"),
    ],
)
def test_next_version(current: str | None, action: str, expected: str) -> None:
    baseline = Version(current) if current is not None else None
    assert next_version(baseline, action, "pkg") == expected


@pytest.mark.parametrize(
    ("current", "action", "message"),
    [
        ("1.2.4a1", "new-prerelease-patch", "would abandon the in-progress"),
        ("1.2.3", "continued-prerelease", "requires the newest version to be an alpha"),
        (
            "1.2.3",
            "release-from-prerelease",
            "requires the newest version to be an alpha",
        ),
        ("1.2.4a1", "release-post", "can only follow a final release"),
        ("1.2.4b1", "release-post", "can only follow a final release"),
        ("1.2.4rc1", "release-post", "can only follow a final release"),
        ("1.2.4.dev1", "release-post", "can only follow a final release"),
    ],
)
def test_next_version_rejects_impossible_transitions(
    current: str, action: str, message: str
) -> None:
    with pytest.raises(ReleaseError, match=message):
        next_version(Version(current), action, "pkg")


def test_release_post_needs_a_release() -> None:
    with pytest.raises(ReleaseError, match="requires an existing release"):
        next_version(None, "release-post", "pkg")


def test_beta_versions_get_an_actionable_hint() -> None:
    with pytest.raises(ReleaseError, match="only alpha aN prereleases are supported"):
        next_version(Version("1.2.4b1"), "continued-prerelease", "pkg")


def test_final_actions_cover_every_release_action() -> None:
    assert {
        action for action in ACTIONS if action.startswith("release-")
    } == FINAL_ACTIONS


def test_release_date_today_uses_the_configured_timezone() -> None:
    assert len(release_date_today("America/Los_Angeles")) == len("2026-01-01")


def test_release_date_today_rejects_unknown_timezone() -> None:
    with pytest.raises(ReleaseError, match="unknown release-timezone"):
        release_date_today("Mars/Olympus_Mons")
