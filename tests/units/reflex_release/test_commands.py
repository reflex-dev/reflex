"""Tests for the reflex_release subcommands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_release import commands
from reflex_release.actions import ReleaseError
from reflex_release.config import Config, load_config

from .conftest import commit_all, git, write_lockstep

Outputs = Callable[[], dict[str, str]]


def set_changelog(config: Config, package: str, text: str) -> None:
    """Write a package's changelog.

    Args:
        config: The repository configuration.
        package: The package name.
        text: The changelog markdown.
    """
    config.changelog_path(package).write_text(text)


def fragment(config: Config, package: str, name: str, text: str = "Something.") -> None:
    """Write a news fragment for a package.

    Args:
        config: The repository configuration.
        package: The package name.
        name: The fragment filename.
        text: The fragment body.
    """
    (config.news_dir(package) / name).write_text(text + "\n")


def test_detect_lists_untagged_changelog_versions(
    config: Config, outputs: Outputs
) -> None:
    set_changelog(
        config, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    set_changelog(
        config, "widget-core", "## v0.3.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_detect(config, "main")
    result = outputs()
    assert json.loads(result["packages"]) == [
        {"package": "mypkg", "version": "1.2.0", "tag": "v1.2.0"},
        {"package": "widget-core", "version": "0.3.0", "tag": "widget-core-v0.3.0"},
    ]
    assert result["any"] == "true"
    assert result["any_last"] == "false"


def test_detect_skips_tagged_versions(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    set_changelog(
        config, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    git(repo, "tag", "v1.2.0")
    commands.cmd_detect(config, "main")
    assert outputs()["any"] == "false"


def test_detect_enforces_branch_rules(config: Config, outputs: Outputs) -> None:
    set_changelog(
        config, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_detect(config, "r/pre-2026.01.01")
    assert outputs()["any"] == "false"


def test_detect_splits_lockstep_publish_last(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    write_lockstep(repo)
    reloaded = load_config(repo)
    set_changelog(
        reloaded, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    set_changelog(
        reloaded, "widget-core", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_detect(reloaded, "main")
    result = outputs()
    assert [entry["package"] for entry in json.loads(result["packages"])] == [
        "widget-core"
    ]
    assert [entry["package"] for entry in json.loads(result["last_packages"])] == [
        "mypkg"
    ]
    assert result["any_last"] == "true"


def test_detect_fails_closed_on_lockstep_violation(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    write_lockstep(repo)
    reloaded = load_config(repo)
    set_changelog(
        reloaded, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    set_changelog(
        reloaded, "widget-core", "## v1.1.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    with pytest.raises(ReleaseError, match="lockstep invariant violated"):
        commands.cmd_detect(reloaded, "main")


def test_detect_accepts_an_already_tagged_lockstep_partner(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    write_lockstep(repo)
    reloaded = load_config(repo)
    set_changelog(
        reloaded, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    set_changelog(
        reloaded, "widget-core", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    git(repo, "tag", "widget-core-v1.2.0")
    commands.cmd_detect(reloaded, "main")
    result = outputs()
    assert json.loads(result["packages"]) == []
    assert [entry["package"] for entry in json.loads(result["last_packages"])] == [
        "mypkg"
    ]


def test_plan_auto_selects_packages_with_fragments(
    config: Config, outputs: Outputs
) -> None:
    fragment(config, "widget-core", "1.bugfix.md")
    commands.cmd_plan(config, "release-minor", "")
    releases = json.loads(outputs()["releases"])
    assert releases == [
        {
            "package": "widget-core",
            "current": "",
            "next": "0.1.0",
            "tag": "widget-core-v0.1.0",
        }
    ]


def test_plan_uses_explicit_selection(config: Config, outputs: Outputs) -> None:
    fragment(config, "widget-core", "1.bugfix.md")
    commands.cmd_plan(config, "release-minor", "mypkg")
    assert [r["package"] for r in json.loads(outputs()["releases"])] == ["mypkg"]


def test_plan_expands_lockstep_groups_to_one_version(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    write_lockstep(repo)
    reloaded = load_config(repo)
    set_changelog(
        reloaded, "mypkg", "## v1.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    set_changelog(
        reloaded, "widget-core", "## v1.3.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_plan(reloaded, "release-patch", "widget-core")
    releases = json.loads(outputs()["releases"])
    # The group shares the highest baseline, so both land on the same version.
    assert {r["package"]: r["next"] for r in releases} == {
        "widget-core": "1.4.1",
        "mypkg": "1.4.1",
    }


def test_plan_rejects_an_existing_tag(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    set_changelog(
        config, "mypkg", "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    git(repo, "tag", "v1.1.0")
    with pytest.raises(ReleaseError, match=r"tag v1\.1\.0 already exists"):
        commands.cmd_plan(config, "release-minor", "mypkg")


def test_plan_without_any_candidate_fails(config: Config, outputs: Outputs) -> None:
    with pytest.raises(ReleaseError, match="no packages selected"):
        commands.cmd_plan(config, "release-minor", "")


def test_plan_rejects_unknown_action(config: Config, outputs: Outputs) -> None:
    with pytest.raises(ReleaseError, match="unknown action"):
        commands.cmd_plan(config, "release-everything", "mypkg")


def test_plan_rejects_internal_packages(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'packages-dir = "packages"',
            'packages-dir = "packages"\ninternal-packages = ["widget-core"]',
        )
    )
    reloaded = load_config(repo)
    with pytest.raises(ReleaseError, match="internal package"):
        commands.cmd_plan(reloaded, "release-minor", "widget-core")


def test_materialize_writes_the_changelog(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    fragment(config, "widget-core", "7.feature.md", "A new widget.")
    commit_all(repo)
    releases = json.dumps([
        {
            "package": "widget-core",
            "current": "",
            "next": "0.2.0",
            "tag": "widget-core-v0.2.0",
        }
    ])
    commands.cmd_materialize(config, "release-minor", releases)
    text = config.changelog_path("widget-core").read_text()
    assert text.startswith("## v0.2.0 (")
    assert "A new widget." in text
    assert not (config.news_dir("widget-core") / "7.feature.md").exists()


def test_materialize_collapses_a_prerelease_train(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    set_changelog(
        config,
        "widget-core",
        "## v0.2.0a1 (2026-01-01)\n\n### Features\n\n- First. (#1)\n",
    )
    fragment(config, "widget-core", "2.bugfix.md", "A fix.")
    commit_all(repo)
    releases = json.dumps([
        {
            "package": "widget-core",
            "current": "0.2.0a1",
            "next": "0.2.0",
            "tag": "widget-core-v0.2.0",
        }
    ])
    commands.cmd_materialize(config, "release-from-prerelease", releases)
    text = config.changelog_path("widget-core").read_text()
    assert text.startswith("## v0.2.0 (")
    assert "a1" not in text
    assert "First. (#1)" in text
    assert "A fix." in text


def test_materialize_rejects_an_empty_plan(config: Config) -> None:
    with pytest.raises(ReleaseError, match="plan is empty"):
        commands.cmd_materialize(config, "release-minor", "[]")


def test_prepare_publish_emits_build_metadata(config: Config, outputs: Outputs) -> None:
    set_changelog(
        config, "widget-core", "## v0.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_prepare_publish(config, "widget-core", "0.4.0", "main")
    assert outputs() == {
        "package": "widget-core",
        "version": "0.4.0",
        "tag": "widget-core-v0.4.0",
        "build_dir": "packages/widget-core",
        "prerelease": "false",
        "mark_latest": "false",
        "skipped": "false",
    }


def test_prepare_publish_marks_the_flagship_package_latest(
    config: Config, outputs: Outputs
) -> None:
    set_changelog(
        config, "mypkg", "## v2.0.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_prepare_publish(config, "mypkg", "2.0.0", "main")
    assert outputs()["mark_latest"] == "true"


def test_prepare_publish_does_not_mark_an_older_hotfix_latest(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    git(repo, "tag", "v2.0.0")
    set_changelog(
        config, "mypkg", "## v1.9.1 (2026-01-01)\n\nNo significant changes.\n"
    )
    commands.cmd_prepare_publish(config, "mypkg", "1.9.1", "r/hotfix/1.9")
    assert outputs()["mark_latest"] == "false"


def test_prepare_publish_skips_an_already_tagged_version(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    set_changelog(
        config, "widget-core", "## v0.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    git(repo, "tag", "widget-core-v0.4.0")
    commands.cmd_prepare_publish(config, "widget-core", "0.4.0", "main")
    assert outputs()["skipped"] == "true"


def test_prepare_publish_requires_the_newest_changelog_version(
    config: Config, outputs: Outputs
) -> None:
    set_changelog(
        config, "widget-core", "## v0.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    with pytest.raises(ReleaseError, match="changelog is the source of truth"):
        commands.cmd_prepare_publish(config, "widget-core", "0.5.0", "main")


def test_prepare_publish_enforces_branch_rules(
    config: Config, outputs: Outputs
) -> None:
    set_changelog(
        config, "widget-core", "## v0.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    with pytest.raises(ReleaseError, match="can only be published from"):
        commands.cmd_prepare_publish(config, "widget-core", "0.4.0", "feature/x")


@pytest.mark.parametrize("version", ["1.0.0.dev1", "1.0.0+local", "1!1.0.0"])
def test_prepare_publish_rejects_unpublishable_versions(
    config: Config, outputs: Outputs, version: str
) -> None:
    with pytest.raises(ReleaseError, match="refusing to publish"):
        commands.cmd_prepare_publish(config, "widget-core", version, "main")


def test_prepare_publish_requires_a_version_for_changelog_packages(
    config: Config, outputs: Outputs
) -> None:
    set_changelog(
        config, "widget-core", "## v0.4.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    with pytest.raises(ReleaseError, match="a target version is required"):
        commands.cmd_prepare_publish(config, "widget-core", "", "main")


def test_prepare_publish_patch_bumps_internal_packages(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    git(repo, "tag", "widget-core-v0.4.0")
    commands.cmd_prepare_publish(config, "widget-core", "", "main")
    assert outputs()["version"] == "0.4.1"


def test_prepare_publish_starts_an_unreleased_package_at_0_0_1(
    config: Config, outputs: Outputs
) -> None:
    commands.cmd_prepare_publish(config, "widget-core", "", "main")
    assert outputs()["version"] == "0.0.1"


def test_prepare_publish_requires_a_materialized_lockstep_partner(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    write_lockstep(repo)
    reloaded = load_config(repo)
    set_changelog(
        reloaded, "mypkg", "## v1.2.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    with pytest.raises(ReleaseError, match="releases in lockstep"):
        commands.cmd_prepare_publish(reloaded, "mypkg", "1.2.0", "main")


def test_prepare_publish_rejects_unknown_packages(
    config: Config, outputs: Outputs
) -> None:
    with pytest.raises(ReleaseError, match="unknown package"):
        commands.cmd_prepare_publish(config, "ghost", "1.0.0", "main")


def test_extract_notes_falls_back_when_the_version_is_missing(
    config: Config, tmp_path: Path
) -> None:
    target = tmp_path / "notes.md"
    commands.cmd_extract_notes(config, "widget-core", "9.9.9", target)
    assert target.read_text() == "Release of widget-core 9.9.9.\n"


def test_extract_notes_writes_the_changelog_section(
    config: Config, tmp_path: Path
) -> None:
    set_changelog(
        config,
        "widget-core",
        "## v1.0.0 (2026-01-01)\n\n### Features\n\n- Nice. (#1)\n",
    )
    target = tmp_path / "notes.md"
    commands.cmd_extract_notes(config, "widget-core", "v1.0.0", target)
    assert target.read_text() == "### Features\n\n- Nice. (#1)\n"


def test_check_headings_accepts_an_unchanged_changelog(
    config: Config, repo: Path
) -> None:
    set_changelog(
        config, "mypkg", "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commit_all(repo)
    commands.cmd_check_headings(config, "HEAD")


def test_check_headings_rejects_a_new_heading(config: Config, repo: Path) -> None:
    set_changelog(
        config, "mypkg", "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n"
    )
    commit_all(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    set_changelog(
        config,
        "mypkg",
        "## v1.1.0 (2026-02-02)\n\nNo significant changes.\n\n"
        "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n",
    )
    with pytest.raises(ReleaseError, match="publish triggers"):
        commands.cmd_check_headings(config, base)


def test_check_headings_allows_editing_published_sections(
    config: Config, repo: Path
) -> None:
    set_changelog(config, "mypkg", "## v1.0.0 (2026-01-01)\n\nTypo.\n")
    commit_all(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    set_changelog(config, "mypkg", "## v1.0.0 (2026-01-01)\n\nFixed typo.\n")
    commands.cmd_check_headings(config, base)


def test_affected_packages(config: Config) -> None:
    assert commands.affected_packages(config, ["docs/x.md"]) == []
    assert commands.affected_packages(config, ["src/mypkg/a.py"]) == ["mypkg"]
    assert commands.affected_packages(
        config, ["src/mypkg/a.py", "packages/widget-core/src/b.py"]
    ) == ["mypkg", "widget-core"]


def test_changelog_check_passes_without_source_changes(
    config: Config, repo: Path
) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "docs.md").write_text("hello\n")
    commit_all(repo)
    commands.cmd_changelog_check(config, base)


def test_changelog_check_requires_a_fragment(config: Config, repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "mypkg" / "app.py").write_text("x = 1\n")
    commit_all(repo)
    with pytest.raises(ReleaseError, match="no news fragment for: mypkg"):
        commands.cmd_changelog_check(config, base)


def test_changelog_check_passes_with_a_fragment(config: Config, repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "mypkg" / "app.py").write_text("x = 1\n")
    fragment(config, "mypkg", "12.feature.md", "Adds app.")
    commit_all(repo)
    commands.cmd_changelog_check(config, base)


def test_detect_internal_uses_the_dispatched_package(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'packages-dir = "packages"',
            'packages-dir = "packages"\ninternal-packages = ["widget-core"]',
        )
    )
    reloaded = load_config(repo)
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "widget-core")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_diffs_the_push(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'packages-dir = "packages"',
            'packages-dir = "packages"\ninternal-packages = ["widget-core"]',
        )
    )
    commit_all(repo)
    reloaded = load_config(repo)
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text("y = 2\n")
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_rejects_a_non_internal_package(
    config: Config, outputs: Outputs
) -> None:
    with pytest.raises(ReleaseError, match="not listed in internal-packages"):
        commands.cmd_detect_internal(config, "HEAD~1", "HEAD", "widget-core")


def test_packages_lists_releasable_packages(
    config: Config, capsys: pytest.CaptureFixture
) -> None:
    commands.cmd_packages(config)
    assert capsys.readouterr().out.split() == ["mypkg", "widget-core"]
