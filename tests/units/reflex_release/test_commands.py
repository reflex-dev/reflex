"""Tests for the reflex_release subcommands."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

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
        config, [{"package": "mypkg", "next": "1.0.0"}], "Materialize changelogs"
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
        config, "new-prerelease-minor", "main", json.dumps(PLAN)
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
        config, "new-prerelease-minor", "main", json.dumps(PLAN)
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
        config, "new-prerelease-minor", "main", json.dumps(PLAN)
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
    commands.cmd_open_release_pr(config, "release-minor", "main", json.dumps(PLAN))
    text = summary()
    assert f"Pull request: [#42]({url})" in text
    assert "/tree/release/release-minor-" in text
    assert "→ `main`" in text
    assert f"::notice::release pull request opened: {url}" in capsys.readouterr().out


@pytest.fixture
def release_args(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], list[str]]:
    """Capture the ``gh release create`` arguments instead of running gh.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A callable returning the arguments of the last ``gh`` invocation.
    """
    captured: list[list[str]] = []
    monkeypatch.setattr(commands, "gh_output", lambda *args, **kwargs: "")
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


def test_post_release_without_a_configured_workflow_does_nothing(
    config: Config, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    captured: list[list[str]] = []
    monkeypatch.setattr(
        commands, "gh_run", lambda args, *rest, **kwargs: captured.append(args) or 0
    )
    commands.cmd_post_release(config, "v1.2.3", "mypkg", "1.2.3")
    assert captured == []
    assert "no post-release-workflow is configured" in capsys.readouterr().out


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
    commands._commit_materialized(
        reloaded, [{"package": "mypkg", "next": "0.1.0"}], "Materialize"
    )

    assert sorted(git(repo, "show", "--name-only", "--format=", "HEAD").split()) == [
        "CHANGELOG.md",
        "news/5.feature.md",
        "pyproject.toml",
    ]
