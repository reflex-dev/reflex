"""Tests for reflex_release.devpins."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.config import Config, load_config
from reflex_release.devpins import (
    LOCK_FILE,
    PinUpgrade,
    blocker_advice,
    blocking_pins,
    check_dev_pins,
    parse_requirement,
    pin_upgrades,
    published_dependencies,
    upgrade_dev_pins,
)

from .conftest import git, write_lockstep


def set_root_dependency(repo: Path, requirement: str) -> Config:
    """Replace the root package's single dependency and reload the configuration.

    Args:
        repo: The repository root.
        requirement: The requirement string to declare instead.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            '"widget-core >= 0.1.0"', f'"{requirement}"'
        ),
        encoding="utf-8",
    )
    return load_config(repo)


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("widget-core >= 0.1.0", ("widget-core", False)),
        ("widget-core >= 0.1.0.dev1", ("widget-core", True)),
        ("widget-core == 1.0.dev3", ("widget-core", True)),
        ("widget-core ~= 1.0.dev3", ("widget-core", True)),
        # An upper bound or exclusion on a dev release stays resolvable.
        ("widget-core >= 1, != 2.0.dev1", ("widget-core", False)),
        ("widget-core < 2.0.dev1", ("widget-core", False)),
        ("widget-core == 1.2.*", ("widget-core", False)),
        ("Widget_Core[extra] >= 1; python_version > '3.10'", ("widget-core", False)),
        ("not a requirement !!", ("", False)),
    ],
)
def test_parse_requirement(requirement: str, expected: tuple[str, bool]) -> None:
    assert parse_requirement(requirement) == expected


def test_published_dependencies_includes_extras_but_not_groups() -> None:
    project = {
        "dependencies": ["a >= 1"],
        "optional-dependencies": {"extra": ["b >= 2"]},
        "dependency-groups": {"dev": ["c >= 3"]},
    }
    assert published_dependencies(project) == ["a >= 1", "b >= 2"]


def test_check_dev_pins_accepts_published_pins(
    config: Config, capsys: pytest.CaptureFixture
) -> None:
    check_dev_pins(config, [])
    assert "No development-release dependency pins" in capsys.readouterr().out


def test_check_dev_pins_rejects_a_dev_pin(config: Config, repo: Path) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(">= 0.1.0", ">= 0.2.0.dev1"),
        encoding="utf-8",
    )
    with pytest.raises(ReleaseError, match="must not be published"):
        check_dev_pins(config, [])


def test_check_dev_pins_is_scoped_to_the_selected_package(
    config: Config, repo: Path
) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(">= 0.1.0", ">= 0.2.0.dev1"),
        encoding="utf-8",
    )
    # The sibling can still be released while its dependent dev-pins it.
    check_dev_pins(config, ["widget-core"])
    with pytest.raises(ReleaseError, match="must not be published"):
        check_dev_pins(config, ["mypkg"])


def test_check_dev_pins_rejects_unknown_packages(config: Config) -> None:
    with pytest.raises(ReleaseError, match="unknown package"):
        check_dev_pins(config, ["ghost"])


@pytest.mark.parametrize(
    ("requirement", "bounds", "expected"),
    [
        ("widget-core >= 0.2.0.dev1", ("0.2.0.dev1",), "widget-core >= 0.2.0"),
        ("widget-core>=0.2.0.dev1", ("0.2.0.dev1",), "widget-core>=0.2.0"),
        # Extras, the other specifiers and the marker all survive the lift.
        (
            "widget-core[extra] >= 0.2.0.dev1, < 1.0 ; python_version > '3.10'",
            ("0.2.0.dev1",),
            "widget-core[extra] >= 0.2.0, < 1.0 ; python_version > '3.10'",
        ),
        # An upper bound naming a dev release is resolvable as it stands.
        (
            "widget-core >= 0.2.0a1, != 0.3.0.dev1",
            ("0.2.0a1",),
            "widget-core >= 0.2.0, != 0.3.0.dev1",
        ),
        # A second lower bound that is already publishable stays put.
        (
            "widget-core >= 0.2.0.dev1, > 0.1.0",
            ("0.2.0.dev1",),
            "widget-core >= 0.2.0, > 0.1.0",
        ),
    ],
)
def test_pin_upgrade_rewrites_only_the_offending_bound(
    requirement: str, bounds: tuple[str, ...], expected: str
) -> None:
    upgrade = PinUpgrade("mypkg", requirement, "widget-core", bounds, Version("0.2.0"))
    assert upgrade.rewritten() == expected


def test_pin_upgrades_resolves_to_the_earliest_published_version(
    repo: Path,
) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    for tag in ("widget-core-v0.1.9", "widget-core-v0.2.0", "widget-core-v0.3.0"):
        git(repo, "tag", tag)
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert upgrade.resolved == Version("0.2.0")
    assert upgrade.rewritten() == "widget-core >= 0.2.0"


def test_pin_upgrades_ignores_a_published_lower_bound(repo: Path) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.1.0")
    assert pin_upgrades(reloaded, "mypkg", allow_prereleases=False) == []


def test_pin_upgrades_holds_back_an_unreleased_dev_pin(repo: Path) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.1.9")
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert upgrade.resolved is None
    assert "newest tagged: 0.1.9" in upgrade.reason


def test_pin_upgrades_only_takes_a_prerelease_for_a_prerelease(repo: Path) -> None:
    """An alpha may depend on a sibling's alpha; a final version may not."""
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0a1")

    (final,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert final.resolved is None
    assert "no final release of widget-core" in final.reason

    (alpha,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=True)
    assert alpha.resolved == Version("0.2.0a1")


def test_pin_upgrades_lifts_a_prerelease_floor_for_a_final_release(repo: Path) -> None:
    """A final version must not floor its users on a sibling's alpha."""
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0a1")
    git(repo, "tag", "widget-core-v0.2.0a1")
    git(repo, "tag", "widget-core-v0.2.0")

    (final,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert final.resolved == Version("0.2.0")
    # The same floor is fine in a prerelease, which may ship it as it stands.
    assert pin_upgrades(reloaded, "mypkg", allow_prereleases=True) == []


def test_pin_upgrades_leaves_an_outside_prerelease_pin_alone(repo: Path) -> None:
    """Only siblings' releases are recorded here; an outside pin is deliberate."""
    reloaded = set_root_dependency(repo, "third-party >= 2.0b1")
    assert pin_upgrades(reloaded, "mypkg", allow_prereleases=False) == []


def test_pin_upgrades_holds_back_an_outside_dev_pin(repo: Path) -> None:
    """A dev pin is unpublishable whoever owns the dependency."""
    reloaded = set_root_dependency(repo, "third-party >= 2.0.dev1")
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=True)
    assert upgrade.resolved is None
    assert "not a package in this repository" in upgrade.reason


def test_pin_upgrades_skips_exactly_pinned_lockstep_siblings(repo: Path) -> None:
    """pin-lockstep rewrites those at build time, so nothing here is shipped."""
    write_lockstep(repo)
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    assert reloaded.exact_pin_targets("mypkg") == ("widget-core",)
    assert pin_upgrades(reloaded, "mypkg", allow_prereleases=False) == []


def test_pin_upgrades_respects_the_whole_specifier_set(repo: Path) -> None:
    """The lifted version has to satisfy the upper bound too."""
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1, < 0.3")
    git(repo, "tag", "widget-core-v0.3.0")
    (blocked,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert blocked.resolved is None

    git(repo, "tag", "widget-core-v0.2.5")
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert upgrade.resolved == Version("0.2.5")


def test_blocking_pins_groups_by_package(repo: Path) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    blocked = blocking_pins(reloaded, ["mypkg", "widget-core"], allow_prereleases=False)
    assert list(blocked) == ["mypkg"]


def test_upgrade_dev_pins_rewrites_the_pyproject(repo: Path) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    assert upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False) == [
        "pyproject.toml"
    ]
    assert '"widget-core >= 0.2.0"' in (repo / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    # The gate the publish job runs is satisfied by the rewrite.
    check_dev_pins(reloaded, ["mypkg"])


def stub_uv_lock(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    lock: Path | None = None,
) -> list[list[str]]:
    """Answer ``uv lock`` with a fixed status, letting git run for real.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        returncode: The status ``uv lock`` should report.
        lock: A lock file the stubbed run should rewrite, standing in for a
            re-resolution that actually moves it. Left alone when None, which is
            what a uv workspace does for a sibling pin.

    Returns:
        The list the intercepted commands are recorded in.
    """
    real_run = subprocess.run
    recorded: list[list[str]] = []

    def run(cmd, **kwargs):
        if cmd[:2] != ["uv", "lock"]:
            return real_run(cmd, **kwargs)
        recorded.append(cmd)
        if lock is not None:
            lock.write_text("version = 2\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode)

    monkeypatch.setattr(subprocess, "run", run)
    return recorded


def test_upgrade_dev_pins_refreshes_the_lock_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    lock = repo / LOCK_FILE
    lock.write_text("version = 1\n", encoding="utf-8")
    recorded = stub_uv_lock(monkeypatch, 0, lock=lock)
    assert upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False) == [
        "pyproject.toml",
        LOCK_FILE,
    ]
    assert recorded == [["uv", "lock"]]


def test_upgrade_dev_pins_omits_a_lock_file_the_pins_did_not_move(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A uv workspace records siblings with no specifier, so a sibling pin
    cannot move the lock — reporting it would stage an unrelated diff.
    """
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    (repo / LOCK_FILE).write_text("version = 1\n", encoding="utf-8")
    recorded = stub_uv_lock(monkeypatch, 0)
    assert upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False) == [
        "pyproject.toml"
    ]
    assert recorded == [["uv", "lock"]]


def test_upgrade_dev_pins_fails_when_the_lock_cannot_be_refreshed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    (repo / LOCK_FILE).write_text("version = 1\n", encoding="utf-8")
    stub_uv_lock(monkeypatch, 1)
    with pytest.raises(ReleaseError, match="uv lock` failed"):
        upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)


def test_upgrade_dev_pins_refuses_an_unsatisfiable_pin(repo: Path) -> None:
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    with pytest.raises(ReleaseError, match="no published version satisfies"):
        upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)


def test_upgrade_dev_pins_is_a_no_op_without_pins(repo: Path) -> None:
    reloaded = load_config(repo)
    before = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False) == []
    assert (repo / "pyproject.toml").read_text(encoding="utf-8") == before


def test_upgrade_dev_pins_lifts_every_published_copy(repo: Path) -> None:
    """The same pin in `dependencies` and in an extra is published twice."""
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'dependencies = ["widget-core >= 0.1.0"]',
            'dependencies = ["widget-core >= 0.2.0.dev1"]\n'
            '[project.optional-dependencies]\nextra = ["widget-core >= 0.2.0.dev1"]',
        ),
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    git(repo, "tag", "widget-core-v0.2.0")
    upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)
    text = pyproject.read_text(encoding="utf-8")
    assert text.count('"widget-core >= 0.2.0"') == 2
    assert "0.2.0.dev1" not in text


def test_upgrade_dev_pins_ignores_an_unpublished_copy(repo: Path) -> None:
    """`[dependency-groups]` is development-only, so it is neither counted nor
    rewritten — the same rule `check_dev_pins` applies.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'dependencies = ["widget-core >= 0.1.0"]',
            'dependencies = ["widget-core >= 0.2.0.dev1"]',
        )
        + '\n[dependency-groups]\ndev = ["widget-core >= 0.2.0.dev1"]\n',
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    git(repo, "tag", "widget-core-v0.2.0")
    upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)
    text = pyproject.read_text(encoding="utf-8")
    assert 'dependencies = ["widget-core >= 0.2.0"]' in text
    assert 'dev = ["widget-core >= 0.2.0.dev1"]' in text


def test_pin_upgrade_relaxes_a_strict_floor(repo: Path) -> None:
    """`> 0.2.0.dev1` admits 0.2.0, so `> 0.2.0` would exclude what it resolved to."""
    reloaded = set_root_dependency(repo, "widget-core > 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert upgrade.resolved == Version("0.2.0")
    assert upgrade.rewritten() == "widget-core >= 0.2.0"


def test_pin_upgrade_rejects_a_rewrite_its_version_would_not_satisfy() -> None:
    """The guard against a future operator gap shipping an unsatisfiable pin."""
    upgrade = PinUpgrade(
        "mypkg",
        # A bound the rewrite cannot lift, since 0.2.0 is not below 0.3.
        "widget-core >= 0.2.0.dev1, < 0.3",
        "widget-core",
        ("0.2.0.dev1",),
        Version("0.4.0"),
    )
    with pytest.raises(ReleaseError, match="does not satisfy"):
        upgrade.rewritten()


def test_upgrade_dev_pins_rewrites_an_escaped_toml_marker(repo: Path) -> None:
    """A basic string escapes its quotes; the parsed value does not carry them."""
    requirement = 'widget-core >= 0.2.0.dev1; python_version > \\"3.10\\"'
    reloaded = set_root_dependency(repo, requirement)
    git(repo, "tag", "widget-core-v0.2.0")
    upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)
    assert 'widget-core >= 0.2.0; python_version > \\"3.10\\"' in (
        repo / "pyproject.toml"
    ).read_text(encoding="utf-8")


def test_upgrade_dev_pins_rewrites_a_literal_toml_string(repo: Path) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            '"widget-core >= 0.1.0"', "'widget-core >= 0.2.0.dev1'"
        ),
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    git(repo, "tag", "widget-core-v0.2.0")
    upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)
    assert "'widget-core >= 0.2.0'" in pyproject.read_text(encoding="utf-8")


def test_upgrade_dev_pins_rolls_back_when_the_lock_cannot_follow(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins and lock file move together: a half-applied upgrade would be committed."""
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    (repo / LOCK_FILE).write_text("version = 1\n", encoding="utf-8")
    pyproject = repo / "pyproject.toml"
    before = pyproject.read_text(encoding="utf-8")
    stub_uv_lock(monkeypatch, 1)

    with pytest.raises(ReleaseError, match="uv lock` failed"):
        upgrade_dev_pins(reloaded, ["mypkg"], allow_prereleases=False)

    assert pyproject.read_text(encoding="utf-8") == before
    # A re-run therefore still has the pin to lift, rather than finding nothing
    # to do and leaving the stale lock file to be committed.
    assert pin_upgrades(reloaded, "mypkg", allow_prereleases=False)


def test_upgrade_dev_pins_rolls_back_an_earlier_package(repo: Path) -> None:
    """The rewrites run package by package; one that fails must strand none."""
    reloaded = set_root_dependency(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    git(repo, "tag", "v1.0")
    # The sibling's own pin resolves, but is spelled with an escape, so the
    # parsed value cannot be found in the file — and it is rewritten after the
    # root package's.
    sub = repo / "packages" / "widget-core" / "pyproject.toml"
    sub.write_text(
        sub.read_text(encoding="utf-8")
        + 'dependencies = ["mypkg \\u003E= 1.0.dev1"]\n',
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    root = repo / "pyproject.toml"
    before = root.read_text(encoding="utf-8")

    with pytest.raises(ReleaseError, match="published copy"):
        upgrade_dev_pins(reloaded, ["mypkg", "widget-core"], allow_prereleases=False)

    assert root.read_text(encoding="utf-8") == before


def test_pin_upgrades_calls_an_exact_dev_pin_a_dead_end(repo: Path) -> None:
    """No release can satisfy `== 0.2.0.dev1`, so "release it first" is a circle."""
    reloaded = set_root_dependency(repo, "widget-core == 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.3.0")
    (upgrade,) = pin_upgrades(reloaded, "mypkg", allow_prereleases=False)
    assert upgrade.resolved is None
    assert upgrade.exact
    assert "re-pin it by hand" in upgrade.reason
    # The tags say nothing useful here, so the reason must not cite them.
    assert "newest tagged" not in upgrade.reason


def test_blocker_advice_matches_what_can_be_waited_for(repo: Path) -> None:
    waitable = PinUpgrade("mypkg", "a >= 1.dev1", "a", ("1.dev1",), None, "r")
    dead_end = PinUpgrade(
        "mypkg", "b == 1.dev1", "b", ("1.dev1",), None, "r", exact=True
    )

    assert "lifts those pins automatically" in blocker_advice({"mypkg": [waitable]})
    assert "re-pin it by hand" in blocker_advice({"mypkg": [dead_end]})

    only_exact = blocker_advice({"mypkg": [dead_end]})
    assert "Release the depended-on package(s) first" not in only_exact

    mixed = blocker_advice({"mypkg": [waitable, dead_end]})
    assert "lifts those pins automatically" in mixed
    assert "re-pin it by hand" in mixed
