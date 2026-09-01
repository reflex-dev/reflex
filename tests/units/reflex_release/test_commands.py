"""Tests for the reflex_release subcommands."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from reflex_release import commands
from reflex_release.actions import ReleaseError
from reflex_release.config import Config, load_config

from .conftest import commit_all, git, set_post_release_workflow, write_lockstep

Outputs = Callable[[], dict[str, str]]


def set_changelog(config: Config, package: str, text: str) -> None:
    """Write a package's changelog.

    Args:
        config: The repository configuration.
        package: The package name.
        text: The changelog markdown.
    """
    config.changelog_path(package).write_text(text, encoding="utf-8")


def make_internal(repo: Path, package: str) -> Config:
    """Mark a package as internal and reload the configuration.

    Args:
        repo: The repository root.
        package: The package to list in ``internal-packages``.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'packages-dir = "packages"',
            f'packages-dir = "packages"\ninternal-packages = ["{package}"]',
        ),
        encoding="utf-8",
    )
    return load_config(repo)


def make_never_published(repo: Path, package: str) -> Config:
    """Mark a package as never published and reload the configuration.

    Args:
        repo: The repository root.
        package: The package to list in ``never-publish-packages``.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'packages-dir = "packages"',
            f'packages-dir = "packages"\nnever-publish-packages = ["{package}"]',
        ),
        encoding="utf-8",
    )
    return load_config(repo)


def fragment(config: Config, package: str, name: str, text: str = "Something.") -> None:
    """Write a news fragment for a package.

    Args:
        config: The repository configuration.
        package: The package name.
        name: The fragment filename.
        text: The fragment body.
    """
    (config.news_dir(package) / name).write_text(text + "\n", encoding="utf-8")


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
    reloaded = make_internal(repo, "widget-core")
    with pytest.raises(ReleaseError, match="internal package"):
        commands.cmd_plan(reloaded, "release-minor", "widget-core")


def test_plan_rejects_never_published_packages(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = make_never_published(repo, "widget-core")
    with pytest.raises(ReleaseError, match="never-publish-packages"):
        commands.cmd_plan(reloaded, "release-minor", "widget-core")


def test_prepare_publish_refuses_never_published_packages(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """A manual publish dispatch is the only way to reach one, so it must fail.

    No release selection offers a never-published package and changelog
    detection skips it, which leaves typing it into the publish workflow's
    package field — refused here, in the first unprivileged job, rather than at
    verify-dist after a build.
    """
    reloaded = make_never_published(repo, "widget-core")
    with pytest.raises(ReleaseError, match="never-publish-packages"):
        commands.cmd_prepare_publish(reloaded, "widget-core", "1.0.0", "main")


def test_packages_omits_never_published_packages(
    config: Config, repo: Path, capsys: pytest.CaptureFixture
) -> None:
    commands.cmd_packages(make_never_published(repo, "widget-core"))
    assert capsys.readouterr().out.split() == ["mypkg"]


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
    text = config.changelog_path("widget-core").read_text(encoding="utf-8")
    assert text.startswith("## v0.2.0 (")
    assert "A new widget." in text
    assert not (config.news_dir("widget-core") / "7.feature.md").exists()


def test_materialize_associates_orphan_fragments_with_their_pull_request(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """An orphan fragment that landed is linked to the PR that merged it."""
    fragment(config, "widget-core", "+a-widget.feature.md", "A new widget.")
    commit_all(repo, "feat: a new widget (#4242)")
    releases = json.dumps([
        {
            "package": "widget-core",
            "current": "",
            "next": "0.2.0",
            "tag": "widget-core-v0.2.0",
        }
    ])

    commands.cmd_materialize(config, "release-minor", releases)

    text = config.changelog_path("widget-core").read_text(encoding="utf-8")
    assert "A new widget. ([#4242]" in text
    news = config.news_dir("widget-core")
    assert not (news / "+a-widget.feature.md").exists()
    assert not (news / "4242.feature.md").exists()
    # towncrier consumed the renamed fragment, so the orphan is gone for good.
    assert git(repo, "status", "--porcelain", "--", str(news)).split() == [
        "D",
        "packages/widget-core/news/+a-widget.feature.md",
    ]


def test_materialize_keeps_an_unassociated_orphan_entry(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    fragment(config, "widget-core", "+a-widget.feature.md", "A new widget.")
    commit_all(repo, "a commit with no pull request")
    releases = json.dumps([
        {
            "package": "widget-core",
            "current": "",
            "next": "0.2.0",
            "tag": "widget-core-v0.2.0",
        }
    ])

    commands.cmd_materialize(config, "release-minor", releases)

    text = config.changelog_path("widget-core").read_text(encoding="utf-8")
    assert "A new widget." in text
    assert "#" not in text.split("### Features")[1]


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
    text = config.changelog_path("widget-core").read_text(encoding="utf-8")
    assert text.startswith("## v0.2.0 (")
    assert "a1" not in text
    assert "First. (#1)" in text
    assert "A fix." in text


def test_materialize_writes_an_empty_entry_for_a_lockstep_partner(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """A member dragged along by its lockstep sibling needs no hand-written entry."""
    write_lockstep(repo)
    reloaded = load_config(repo)
    fragment(reloaded, "widget-core", "3.feature.md", "A real change.")
    # The partner has nothing to say — not even a news directory.
    shutil.rmtree(reloaded.news_dir("mypkg"))
    commit_all(repo)

    commands.cmd_plan(reloaded, "release-minor", "widget-core")
    commands.cmd_materialize(reloaded, "release-minor", outputs()["releases"])

    partner = reloaded.changelog_path("mypkg").read_text(encoding="utf-8")
    assert partner.startswith("## v0.1.0 (")
    assert "No significant changes." in partner
    assert "A real change." in reloaded.changelog_path("widget-core").read_text(
        encoding="utf-8"
    )
    # Both sides land on one version, so detection does not fail closed.
    commands.cmd_detect(reloaded, "main")
    assert outputs()["any"] == "true"


def test_commit_materialized_leaves_unrelated_work_alone(
    config: Config, repo: Path
) -> None:
    """A release commit carries the changelogs and nothing a human was mid-way through."""
    (repo / "unrelated.md").write_text("tracked\n", encoding="utf-8")
    commit_all(repo)
    (repo / "unrelated.md").write_text("edited by someone else\n", encoding="utf-8")
    set_changelog(config, "mypkg", "## v1.0.0 (2026-01-01)\n\nNo changes.\n")
    # A changelog edit and a fragment for a package that is not being released.
    set_changelog(config, "widget-core", "## v0.9.0 (2026-01-01)\n\nNot mine.\n")
    fragment(config, "widget-core", "3.bugfix.md")

    commands._commit_materialized(
        config, [{"package": "mypkg", "next": "1.0.0"}], [], "Materialize changelogs"
    )

    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == [
        "CHANGELOG.md"
    ]
    assert "unrelated.md" in git(repo, "diff", "--name-only")
    assert (config.news_dir("widget-core") / "3.bugfix.md").is_file()
    assert not git(repo, "diff", "--cached", "--name-only").strip()


def test_release_commit_removes_the_fragments_it_consumed(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """Towncrier stages the deletions; the commit has to carry them."""
    fragment(config, "widget-core", "9.feature.md", "A widget.")
    commit_all(repo)
    commands.cmd_plan(config, "release-minor", "widget-core")
    commands.cmd_materialize(config, "release-minor", outputs()["releases"])

    commands._commit_materialized(
        config,
        [{"package": "widget-core", "next": "0.1.0"}],
        [],
        "Materialize changelogs",
    )

    assert sorted(git(repo, "show", "--name-only", "--format=", "HEAD").split()) == [
        "packages/widget-core/CHANGELOG.md",
        "packages/widget-core/news/9.feature.md",
    ]
    # The deletion is committed, not left staged for the next release to carry.
    assert not (config.news_dir("widget-core") / "9.feature.md").exists()
    assert "news/9.feature.md" not in git(repo, "diff", "--cached", "--name-only")


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
    reloaded = make_internal(repo, "widget-core")
    git(repo, "tag", "widget-core-v0.4.0")
    commands.cmd_prepare_publish(reloaded, "widget-core", "", "main")
    assert outputs()["version"] == "0.4.1"


def test_prepare_publish_starts_an_unreleased_internal_package_at_0_0_1(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = make_internal(repo, "widget-core")
    commands.cmd_prepare_publish(reloaded, "widget-core", "", "main")
    assert outputs()["version"] == "0.0.1"


def test_prepare_publish_will_not_auto_bump_a_non_internal_package(
    config: Config, outputs: Outputs
) -> None:
    """A missing changelog must not become a way around the source-of-truth rule."""
    assert not config.changelog_path("widget-core").exists()
    with pytest.raises(ReleaseError, match="a target version is required"):
        commands.cmd_prepare_publish(config, "widget-core", "", "main")


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
    assert target.read_text(encoding="utf-8") == "Release of widget-core 9.9.9.\n"


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
    assert target.read_text(encoding="utf-8") == "### Features\n\n- Nice. (#1)\n"


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
    (repo / "docs.md").write_text("hello\n", encoding="utf-8")
    commit_all(repo)
    commands.cmd_changelog_check(config, base)


def test_changelog_check_requires_a_fragment(config: Config, repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "mypkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
    commit_all(repo)
    with pytest.raises(ReleaseError, match="no news fragment for: mypkg"):
        commands.cmd_changelog_check(config, base)


def test_changelog_check_passes_with_a_fragment(config: Config, repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "mypkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
    fragment(config, "mypkg", "12.feature.md", "Adds app.")
    commit_all(repo)
    commands.cmd_changelog_check(config, base)


def test_detect_internal_uses_the_dispatched_package(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = make_internal(repo, "widget-core")
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "widget-core")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_diffs_the_push(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = make_internal(repo, "widget-core")
    commit_all(repo)
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text(
        "y = 2\n", encoding="utf-8"
    )
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_covers_the_whole_pushed_range(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """A paths-filtered push can touch the package in any of its commits."""
    reloaded = make_internal(repo, "widget-core")
    commit_all(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text(
        "y = 2\n", encoding="utf-8"
    )
    commit_all(repo)
    # A later, unrelated commit must not hide the earlier package change.
    (repo / "docs.md").write_text("unrelated\n", encoding="utf-8")
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, base, "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_covers_a_branch_creating_push(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """An all-zero base means every file in the branch is new."""
    reloaded = make_internal(repo, "widget-core")
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text(
        "y = 2\n", encoding="utf-8"
    )
    commit_all(repo)
    # A later commit that touches nothing of the package must not hide it, the
    # way diffing only the final commit would.
    (repo / "docs.md").write_text("unrelated\n", encoding="utf-8")
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "0" * 40, "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_falls_back_when_the_push_base_is_unreachable(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """A non-zero base that is not present locally still has to produce a diff."""
    reloaded = make_internal(repo, "widget-core")
    commit_all(repo)
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text(
        "y = 2\n", encoding="utf-8"
    )
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "f" * 40, "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["widget-core"]


def test_detect_internal_ignores_a_sibling_only_push(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """The root package's prefix is empty; a bare startswith would match anything."""
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'packages-dir = "packages"',
            'packages-dir = "packages"\ninternal-packages = ["mypkg"]',
        ),
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    commit_all(repo)
    (repo / "packages" / "widget-core" / "src" / "w.py").write_text(
        "y = 2\n", encoding="utf-8"
    )
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "")
    assert json.loads(outputs()["packages"]) == []


def test_detect_internal_matches_a_root_package(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """The root package owns paths that are not nested under a directory."""
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'packages-dir = "packages"',
            'packages-dir = "packages"\ninternal-packages = ["mypkg"]',
        ),
        encoding="utf-8",
    )
    reloaded = load_config(repo)
    commit_all(repo)
    (repo / "src" / "mypkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
    commit_all(repo)
    commands.cmd_detect_internal(reloaded, "HEAD~1", "HEAD", "")
    assert json.loads(outputs()["packages"]) == ["mypkg"]


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


PLAN = [{"package": "mypkg", "current": "1.0.0", "next": "1.1.0a1", "tag": "v1.1.0a1"}]


@pytest.fixture
def dispatched(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> pytest.MonkeyPatch:
    """Stand in for the remote so the dispatch commands run against a bare repo.

    Args:
        config: The repository configuration.
        tmp_path: The pytest temporary directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The monkeypatch fixture, so a test can stub ``gh_output`` on top.
    """
    set_changelog(config, "mypkg", "# Changelog\n\n## v1.1.0a1 (2026-01-01)\n\nNew.\n")
    # The pull request body file lands here instead of the working directory.
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example.com")
    monkeypatch.setattr(commands, "git_push", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "gh_run", lambda *args, **kwargs: 0)
    monkeypatch.setattr(commands, "remote_branch_exists", lambda *args: False)
    return monkeypatch


def test_push_prerelease_summary_links_the_branch(
    config: Config, dispatched: pytest.MonkeyPatch, summary: Callable[[], str]
) -> None:
    commands.cmd_push_prerelease(
        config, "new-prerelease-minor", "main", json.dumps(PLAN), ""
    )
    text = summary()
    branch = next(
        line.split("`")[1] for line in text.splitlines() if line.startswith("Branch:")
    )
    assert (
        f"Branch: [`{branch}`](https://github.example.com/acme/widgets/tree/{branch})"
        in text
    )
    assert (
        "https://github.example.com/acme/widgets/actions/workflows/"
        "release_from_changelog.yml?query=branch%3A" in text
    )


def test_push_prerelease_annotates_the_branch_url(
    config: Config,
    dispatched: pytest.MonkeyPatch,
    summary: Callable[[], str],
    capsys: pytest.CaptureFixture,
) -> None:
    commands.cmd_push_prerelease(
        config, "new-prerelease-minor", "main", json.dumps(PLAN), ""
    )
    notices = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("::notice::prerelease branch pushed: ")
    ]
    assert len(notices) == 1
    assert "https://github.example.com/acme/widgets/tree/r/pre-" in notices[0]


def test_dispatch_summaries_degrade_outside_actions(
    config: Config, dispatched: pytest.MonkeyPatch, summary: Callable[[], str]
) -> None:
    dispatched.delenv("GITHUB_REPOSITORY")
    commands.cmd_push_prerelease(
        config, "new-prerelease-minor", "main", json.dumps(PLAN), ""
    )
    text = summary()
    assert "](" not in text
    assert "Branch: `r/pre-" in text


def test_open_release_pr_summary_links_the_pull_request(
    config: Config,
    dispatched: pytest.MonkeyPatch,
    summary: Callable[[], str],
    capsys: pytest.CaptureFixture,
) -> None:
    url = "https://github.example.com/acme/widgets/pull/42"
    dispatched.setattr(commands, "gh_output", lambda *args, **kwargs: url)
    commands.cmd_open_release_pr(config, "release-minor", "main", json.dumps(PLAN), "")
    text = summary()
    assert f"Pull request: [#42]({url})" in text
    assert "/tree/release/release-minor-" in text
    assert "→ `main`" in text
    assert f"::notice::release pull request opened: {url}" in capsys.readouterr().out


#: The ``gh release create`` flags that consume the argument after them, so a
#: fake gh can tell an option value from an asset to attach.
_VALUED_FLAGS = frozenset({"--title", "--notes-file", "--target"})


def release_payload(
    tag: str,
    title: str,
    assets: Sequence[Path | dict[str, Any]] = (),
    **overrides: Any,
) -> str:
    """Render the ``gh release view`` payload of a released version.

    Args:
        tag: The tag the release points at.
        title: The release title.
        assets: Files attached to the release — a path is rendered as the asset
            GitHub reports for it, a dict is used as the asset entry itself, to
            model an upload that did not finish.
        **overrides: Fields to replace, to model a partial or stale release.

    Returns:
        The JSON ``gh release view --json`` would print.
    """
    payload: dict[str, Any] = {
        "tagName": tag,
        "name": title,
        "isDraft": False,
        "isPrerelease": False,
        "assets": [
            asset
            if isinstance(asset, dict)
            else {
                "name": asset.name,
                "state": "uploaded",
                "size": asset.stat().st_size,
            }
            for asset in assets
        ],
    }
    return json.dumps(payload | overrides)


def created_release_payload(create_args: list[str]) -> str:
    """Render the release a ``gh release create`` invocation would leave behind.

    Args:
        create_args: The arguments of the ``gh release create`` call.

    Returns:
        The JSON ``gh release view --json`` would print for it.
    """
    title = ""
    assets: list[Path] = []
    index = 3
    while index < len(create_args):
        arg = create_args[index]
        if arg in _VALUED_FLAGS:
            if arg == "--title":
                title = create_args[index + 1]
            index += 2
            continue
        if not arg.startswith("--"):
            assets.append(Path(arg))
        index += 1
    return release_payload(
        create_args[2],
        title,
        assets,
        isPrerelease="--prerelease" in create_args,
    )


#: What gh reports for a tag that simply has no release.
GH_NO_RELEASE = (1, "", "release not found")

#: The same answer phrased as the bare HTTP status, as gh reports it when the
#: release lookup itself is what 404s.
GH_NO_RELEASE_404 = (
    1,
    "",
    "gh: Not Found (HTTP 404) (https://api.github.com/repos/acme/widgets/releases/tags/v0.2.1)",
)

#: What gh reports when it could not ask GitHub at all.
GH_UNREACHABLE = (1, "", "HTTP 503: Service Unavailable (https://api.github.com)")


def gh_found(payload: str) -> tuple[int, str, str]:
    """Render what gh reports for a release it read successfully.

    Args:
        payload: The ``gh release view --json`` output.

    Returns:
        The exit status, stdout and stderr of that read.
    """
    return (0, payload, "")


#: What gh reports for a repository it read without trouble.
GH_REPO_READS = (0, '{"name": "widgets"}', "")

#: What gh reports for a repository it could not read at all.
GH_REPO_UNREADABLE = (1, "", "gh: Not Found (HTTP 404)")


def stub_gh(
    monkeypatch: pytest.MonkeyPatch,
    reads: list[tuple[int, str, str]],
    repo: tuple[int, str, str] = GH_REPO_READS,
) -> list[list[str]]:
    """Stub the two gh helpers the release commands use.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        reads: What ``gh release view`` reports, in order; the last entry
            answers every further read.
        repo: What the ``gh repo view`` probe reports — the check that a
            not-found is about the release and not about reaching GitHub.

    Returns:
        The list every ``gh`` command that is run is appended to.
    """
    calls: list[list[str]] = []
    queued = iter(reads[:-1])

    def capture(args: list[str], *rest: object, **kwargs: object):
        if args[:2] == ["repo", "view"]:
            return repo
        return next(queued, reads[-1])

    monkeypatch.setattr(commands, "gh_capture", capture)
    monkeypatch.setattr(
        commands, "gh_run", lambda args, *rest, **kwargs: calls.append(args) or 0
    )
    return calls


@pytest.fixture
def release_args(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], list[str]]:
    """Fake gh for a first release: no release yet, then the one just created.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A callable returning the arguments of the last ``gh`` invocation.
    """
    captured: list[list[str]] = []

    def view(args: list[str], *rest: object, **kwargs: object) -> tuple[int, str, str]:
        if args[:2] == ["repo", "view"]:
            return GH_REPO_READS
        creates = [call for call in captured if call[:2] == ["release", "create"]]
        if not creates:
            return GH_NO_RELEASE
        return gh_found(created_release_payload(creates[-1]))

    monkeypatch.setattr(commands, "gh_capture", view)
    monkeypatch.setattr(
        commands, "gh_run", lambda args, *rest, **kwargs: captured.append(args) or 0
    )
    return lambda: captured[-1]


def release_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write the release notes and checksum manifest a publish would have built.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The notes and checksum manifest paths.
    """
    notes = tmp_path / "notes.md"
    notes.write_text("Notes.\n", encoding="utf-8")
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text("abc123  dist/widget_core-0.2.1.whl\n", encoding="utf-8")
    return notes, checksums


def test_create_release_titles_the_root_package_with_its_tag(
    config: Config, tmp_path: Path, release_args: Callable[[], list[str]]
) -> None:
    notes, checksums = release_inputs(tmp_path)
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    args = release_args()
    assert args[args.index("--title") + 1] == "v0.2.1"


def test_create_release_names_the_package_for_a_sub_package(
    config: Config, tmp_path: Path, release_args: Callable[[], list[str]]
) -> None:
    notes, checksums = release_inputs(tmp_path)
    commands.cmd_create_release(
        config,
        "widget-core-v0.2.1",
        "widget-core",
        "0.2.1",
        False,
        False,
        notes,
        checksums,
    )
    args = release_args()
    assert args[args.index("--title") + 1] == "widget-core@0.2.1"


def test_create_release_attaches_the_checksum_manifest(
    config: Config, tmp_path: Path, release_args: Callable[[], list[str]]
) -> None:
    """The record of what a version contains has to outlive the workflow artifact."""
    notes, checksums = release_inputs(tmp_path)
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert release_args()[-1] == str(checksums)


def test_create_release_without_a_manifest_still_releases(
    config: Config, tmp_path: Path, release_args: Callable[[], list[str]]
) -> None:
    """A published version must not be left untagged over a missing manifest."""
    notes, checksums = release_inputs(tmp_path)
    checksums.unlink()
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert str(checksums) not in release_args()


def test_create_release_reports_the_verified_release(
    config: Config,
    tmp_path: Path,
    release_args: Callable[[], list[str]],
    capsys: pytest.CaptureFixture,
) -> None:
    notes, checksums = release_inputs(tmp_path)
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert "Release v0.2.1 created and verified" in capsys.readouterr().out


def test_create_release_fails_when_the_release_cannot_be_read_back(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zero exit from gh is not proof of the release GitHub actually holds."""
    notes, checksums = release_inputs(tmp_path)
    stub_gh(monkeypatch, [GH_NO_RELEASE])
    with pytest.raises(ReleaseError, match="reading it back found no release"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


def test_create_release_rejects_unparseable_release_metadata(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes, checksums = release_inputs(tmp_path)
    stub_gh(monkeypatch, [GH_NO_RELEASE, gh_found("not json")])
    with pytest.raises(ReleaseError, match="that is not JSON"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"isDraft": True}, "still a draft"),
        ({"isPrerelease": True}, "prerelease=True rather than prerelease=False"),
        ({"name": "v0.2.0"}, "titled 'v0.2.0' rather than 'v0.2.1'"),
        ({"tagName": "v0.2.0"}, "points at tag 'v0.2.0'"),
    ],
)
def test_create_release_rejects_a_release_that_is_not_the_one_asked_for(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    expected: str,
) -> None:
    """The next step hands this tag on, so a mismatch stops the job here."""
    notes, checksums = release_inputs(tmp_path)
    created = release_payload("v0.2.1", "v0.2.1", [checksums], **overrides)
    stub_gh(monkeypatch, [GH_NO_RELEASE, gh_found(created)])
    with pytest.raises(
        ReleaseError, match="is not the one that was asked for"
    ) as raised:
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )
    assert expected in str(raised.value)


@pytest.mark.parametrize(
    ("assets", "expected"),
    [
        ([], "manifest is not attached"),
        ([{"name": "SHA256SUMS", "state": "new", "size": 42}], "state 'new'"),
        ([{"name": "SHA256SUMS", "state": "uploaded", "size": 7}], "7 bytes rather"),
    ],
)
def test_create_release_rejects_an_incomplete_checksum_asset(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assets: list[dict[str, Any]],
    expected: str,
) -> None:
    """A release without the manifest of what was uploaded is not a record of it."""
    notes, checksums = release_inputs(tmp_path)
    created = release_payload("v0.2.1", "v0.2.1", assets=assets)
    stub_gh(monkeypatch, [GH_NO_RELEASE, gh_found(created)])
    with pytest.raises(ReleaseError, match=rf"is incomplete: .*{expected}"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


def test_create_release_skips_a_matching_existing_release(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """The safe re-run: the release is already exactly the one this run makes."""
    notes, checksums = release_inputs(tmp_path)
    existing = release_payload("v0.2.1", "v0.2.1", [checksums])
    calls = stub_gh(monkeypatch, [gh_found(existing)])
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert calls == []
    assert "already matches this publish" in capsys.readouterr().out


def test_create_release_attaches_a_manifest_an_earlier_attempt_left_off(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An attempt that died during the asset upload is finished, not accepted."""
    notes, checksums = release_inputs(tmp_path)
    partial = release_payload("v0.2.1", "v0.2.1")
    repaired = release_payload("v0.2.1", "v0.2.1", [checksums])
    calls = stub_gh(monkeypatch, [gh_found(partial), gh_found(repaired)])
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert calls == [["release", "upload", "v0.2.1", str(checksums), "--clobber"]]


def test_create_release_fails_when_attaching_the_manifest_does_not_take(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes, checksums = release_inputs(tmp_path)
    stub_gh(monkeypatch, [gh_found(release_payload("v0.2.1", "v0.2.1"))])
    with pytest.raises(ReleaseError, match="reading it back found that"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


@pytest.mark.parametrize(
    "overrides",
    [{"isDraft": True}, {"isPrerelease": True}, {"name": "something else"}],
)
def test_create_release_refuses_to_reuse_a_stale_release(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
) -> None:
    """A release nobody here made must not be handed on as this publish's."""
    notes, checksums = release_inputs(tmp_path)
    existing = release_payload("v0.2.1", "v0.2.1", [checksums], **overrides)
    calls = stub_gh(monkeypatch, [gh_found(existing)])
    with pytest.raises(ReleaseError, match=r"already exists for v0\.2\.1"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )
    assert calls == []


def test_create_release_reuses_a_release_without_a_local_manifest(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing to attach and nothing to verify: the metadata is the whole check."""
    notes, checksums = release_inputs(tmp_path)
    checksums.unlink()
    calls = stub_gh(monkeypatch, [gh_found(release_payload("v0.2.1", "v0.2.1"))])
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert calls == []


@pytest.mark.parametrize("absent", [GH_NO_RELEASE, GH_NO_RELEASE_404])
def test_create_release_creates_when_gh_says_there_is_no_release(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    absent: tuple[int, str, str],
) -> None:
    """Either phrasing of "no release" has to reach the create, not a failure."""
    notes, checksums = release_inputs(tmp_path)
    created = release_payload("v0.2.1", "v0.2.1", [checksums])
    calls = stub_gh(monkeypatch, [absent, gh_found(created)])
    commands.cmd_create_release(
        config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
    )
    assert calls[0][:3] == ["release", "create", "v0.2.1"]


@pytest.mark.parametrize("absent", [GH_NO_RELEASE, GH_NO_RELEASE_404])
def test_create_release_will_not_believe_a_not_found_it_cannot_corroborate(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    absent: tuple[int, str, str],
) -> None:
    """A 404 from an unreachable repository says nothing about the release."""
    notes, checksums = release_inputs(tmp_path)
    calls = stub_gh(monkeypatch, [absent], repo=GH_REPO_UNREADABLE)
    with pytest.raises(ReleaseError, match="could not read the GitHub release"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )
    assert calls == []


def test_create_release_fails_when_reading_the_created_release_fails(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gh that could not reach GitHub has not said the release is absent."""
    notes, checksums = release_inputs(tmp_path)
    calls = stub_gh(monkeypatch, [GH_NO_RELEASE, GH_UNREACHABLE])
    with pytest.raises(ReleaseError, match="could not read the GitHub release"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )
    assert calls[0][:2] == ["release", "create"]


def test_create_release_does_not_create_over_an_unreadable_release(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Treating an unreadable release as absent would release over it."""
    notes, checksums = release_inputs(tmp_path)
    calls = stub_gh(monkeypatch, [GH_UNREACHABLE])
    with pytest.raises(ReleaseError, match="re-run this job once gh can reach"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )
    assert calls == []


def malformed_assets_payload(assets: Any) -> str:
    """Render a release payload whose assets are not a list of assets.

    Args:
        assets: The malformed value to report as the release's assets.

    Returns:
        The JSON ``gh release view --json`` would print for it.
    """
    return json.dumps({
        "tagName": "v0.2.1",
        "name": "v0.2.1",
        "isDraft": False,
        "isPrerelease": False,
        "assets": assets,
    })


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("null", "is not an object"),
        ("[]", "is not an object"),
        (malformed_assets_payload(None), "rather than as a list of assets"),
        (malformed_assets_payload([None]), "rather than as a list of assets"),
        (malformed_assets_payload(["SHA256SUMS"]), "rather than as a list of assets"),
    ],
)
def test_create_release_rejects_metadata_of_the_wrong_shape(
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
    expected: str,
) -> None:
    """A shape gh should never send has to read as a diagnostic, not a traceback."""
    notes, checksums = release_inputs(tmp_path)
    stub_gh(monkeypatch, [gh_found(payload)])
    with pytest.raises(ReleaseError, match=expected):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


def test_create_release_rejects_metadata_missing_a_requested_field(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A field that was asked for but not answered must not read as a mismatch."""
    notes, checksums = release_inputs(tmp_path)
    payload = json.loads(release_payload("v0.2.1", "v0.2.1", [checksums]))
    del payload["isDraft"]
    stub_gh(monkeypatch, [gh_found(json.dumps(payload))])
    with pytest.raises(ReleaseError, match="carries no isDraft"):
        commands.cmd_create_release(
            config, "v0.2.1", "mypkg", "0.2.1", False, True, notes, checksums
        )


def test_post_release_without_a_configured_workflow_does_nothing(
    config: Config, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    captured: list[list[str]] = []
    monkeypatch.setattr(
        commands, "gh_run", lambda args, *rest, **kwargs: captured.append(args) or 0
    )
    commands.cmd_post_release(config, "v1.2.3", "mypkg", "1.2.3")
    assert captured == []
    out = capsys.readouterr().out
    assert "no post-release-workflow is configured" in out
    assert "::notice::" not in out


def test_pin_lockstep_pins_the_sibling_to_the_exact_version(
    config: Config, repo: Path
) -> None:
    write_lockstep(repo)
    commands.cmd_pin_lockstep(load_config(repo), "mypkg", "1.2.3")
    assert '"widget-core == 1.2.3"' in (repo / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_pin_lockstep_without_siblings_does_not_annotate_the_run(
    config: Config, repo: Path, capsys: pytest.CaptureFixture
) -> None:
    """A step that no-ops has nothing an approver needs to be shown.

    Every package outside an exact-pin lockstep group runs this step, so an
    annotation here is one "nothing to do" line per package on the summary of
    every release batch.
    """
    commands.cmd_pin_lockstep(config, "mypkg", "1.2.3")
    out = capsys.readouterr().out
    assert "mypkg has no exact-pin lockstep siblings" in out
    assert "::notice::" not in out
    assert "widget-core >= 0.1.0" in (repo / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_post_release_dispatches_the_workflow_on_the_tag(
    config: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reloaded = set_post_release_workflow(repo, "docs_publish.yml")
    captured: list[list[str]] = []
    monkeypatch.setattr(
        commands, "gh_run", lambda args, *rest, **kwargs: captured.append(args) or 0
    )
    commands.cmd_post_release(reloaded, "widget-core-v1.2.3", "widget-core", "1.2.3")
    assert captured == [
        [
            "workflow",
            "run",
            "docs_publish.yml",
            "--ref",
            "widget-core-v1.2.3",
            "--field",
            "tag=widget-core-v1.2.3",
            "--field",
            "package=widget-core",
            "--field",
            "version=1.2.3",
        ]
    ]


def test_post_release_reports_a_failed_dispatch_against_the_published_tag(
    config: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The version is already out; the failure has to name what needs redoing."""
    reloaded = set_post_release_workflow(repo, "docs_publish.yml")
    monkeypatch.setattr(commands, "gh_run", lambda *args, **kwargs: 1)
    with pytest.raises(ReleaseError, match=r"was published and tagged v1\.2\.3"):
        commands.cmd_post_release(reloaded, "v1.2.3", "mypkg", "1.2.3")


@pytest.mark.parametrize(
    ("tag", "package", "version"),
    [("", "mypkg", "1.2.3"), ("v1.2.3", "", "1.2.3"), ("v1.2.3", "mypkg", "")],
)
def test_post_release_refuses_to_dispatch_empty_facts(
    config: Config,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tag: str,
    package: str,
    version: str,
) -> None:
    """An unset env var would otherwise dispatch, green, telling it nothing."""
    reloaded = set_post_release_workflow(repo, "docs_publish.yml")
    monkeypatch.setattr(commands, "gh_run", lambda *args, **kwargs: 0)
    with pytest.raises(ReleaseError, match="post-release dispatch has no"):
        commands.cmd_post_release(reloaded, tag, package, version)


def test_post_release_rejects_an_unknown_package(
    config: Config, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reloaded = set_post_release_workflow(repo, "docs_publish.yml")
    monkeypatch.setattr(commands, "gh_run", lambda *args, **kwargs: 0)
    with pytest.raises(ReleaseError, match="unknown package"):
        commands.cmd_post_release(reloaded, "v1.2.3", "ghost", "1.2.3")


def dev_pin(repo: Path, requirement: str) -> Config:
    """Replace the root package's dependency and reload the configuration.

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


def test_plan_holds_back_an_auto_selected_unsatisfiable_pin(
    config: Config, repo: Path, outputs: Outputs, summary: Callable[[], str]
) -> None:
    reloaded = dev_pin(repo, "widget-core >= 9.9.9.dev1")
    fragment(reloaded, "mypkg", "1.feature.md")
    fragment(reloaded, "widget-core", "2.feature.md")
    commands.cmd_plan(reloaded, "release-minor", "")
    # The dependency can still be released; only its dependent is held back.
    assert [r["package"] for r in json.loads(outputs()["releases"])] == ["widget-core"]
    assert "### Held back" in summary()


def test_plan_rejects_an_explicit_unsatisfiable_pin(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = dev_pin(repo, "widget-core >= 9.9.9.dev1")
    with pytest.raises(ReleaseError, match="no published version satisfies"):
        commands.cmd_plan(reloaded, "release-minor", "mypkg")


def test_plan_holds_back_a_whole_lockstep_group(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """Members only ever release together, so one blocker holds back the group."""
    write_lockstep(repo)
    # Not the lockstep sibling, which pin-lockstep rewrites at build time.
    reloaded = dev_pin(repo, "third-party >= 9.9.9.dev1")
    fragment(reloaded, "widget-core", "2.feature.md")
    with pytest.raises(ReleaseError, match="every auto-selected package"):
        commands.cmd_plan(reloaded, "release-minor", "")


def test_plan_accepts_a_pin_a_prerelease_can_satisfy(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = dev_pin(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0a1")
    fragment(reloaded, "mypkg", "1.feature.md")
    # A final version cannot take the alpha; the alpha train can.
    with pytest.raises(ReleaseError, match="no published version satisfies"):
        commands.cmd_plan(reloaded, "release-minor", "mypkg")
    commands.cmd_plan(reloaded, "new-prerelease-minor", "mypkg")
    assert [r["package"] for r in json.loads(outputs()["releases"])] == ["mypkg"]


def test_materialize_lifts_the_dev_pin_it_can_resolve(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = dev_pin(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    fragment(reloaded, "mypkg", "4.feature.md", "Something.")
    commit_all(repo)

    commands.cmd_plan(reloaded, "release-minor", "mypkg")
    commands.cmd_materialize(reloaded, "release-minor", outputs()["releases"])

    assert '"widget-core >= 0.2.0"' in (repo / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_release_commit_carries_the_lifted_pins(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    reloaded = dev_pin(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    fragment(reloaded, "mypkg", "5.feature.md", "Something.")
    commit_all(repo)

    commands.cmd_plan(reloaded, "release-minor", "mypkg")
    commands.cmd_materialize(reloaded, "release-minor", outputs()["releases"])
    # The commit runs as its own process, so materialize hands it the paths.
    assert json.loads(outputs()["repinned"]) == ["pyproject.toml"]
    commands._commit_materialized(
        reloaded,
        [{"package": "mypkg", "next": "0.1.0"}],
        json.loads(outputs()["repinned"]),
        "Materialize",
    )

    assert sorted(git(repo, "show", "--name-only", "--format=", "HEAD").split()) == [
        "CHANGELOG.md",
        "news/5.feature.md",
        "pyproject.toml",
    ]


def test_release_commit_stages_no_pyproject_when_no_pin_moved(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """Only what the pin upgrade actually rewrote is staged beside the changelogs."""
    fragment(config, "mypkg", "6.feature.md", "Something.")
    commit_all(repo)
    commands.cmd_plan(config, "release-minor", "mypkg")
    commands.cmd_materialize(config, "release-minor", outputs()["releases"])
    assert json.loads(outputs()["repinned"]) == []

    commands._commit_materialized(
        config, [{"package": "mypkg", "next": "0.1.0"}], [], "Materialize"
    )

    assert (
        "pyproject.toml"
        not in git(repo, "show", "--name-only", "--format=", "HEAD").split()
    )


def test_release_commit_refuses_to_strand_a_lifted_pin(
    config: Config, repo: Path, outputs: Outputs
) -> None:
    """A workflow that predates the `repinned` output would otherwise commit the
    changelog bump with the old pin, and die at the publish-time gate.
    """
    reloaded = dev_pin(repo, "widget-core >= 0.2.0.dev1")
    git(repo, "tag", "widget-core-v0.2.0")
    fragment(reloaded, "mypkg", "7.feature.md", "Something.")
    commit_all(repo)
    commands.cmd_plan(reloaded, "release-minor", "mypkg")
    commands.cmd_materialize(reloaded, "release-minor", outputs()["releases"])
    assert json.loads(outputs()["repinned"]) == ["pyproject.toml"]

    # The delivery step of an un-synced workflow passes nothing through.
    with pytest.raises(ReleaseError, match="modified but unstaged"):
        commands._commit_materialized(
            reloaded, [{"package": "mypkg", "next": "0.1.0"}], [], "Materialize"
        )
