"""Tests for reflex_release.discovery."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from reflex_release.actions import ReleaseError
from reflex_release.changelog import DEFAULT_TITLE_FORMAT
from reflex_release.config import Config, load_config
from reflex_release.discovery import (
    alpha_train_packages,
    associate_orphan_fragments,
    changelog_packages,
    fragment_types,
    orphan_prefix,
    pending_fragment_packages,
    pull_request_number,
    releasable_packages,
    split_fragment_name,
    title_format,
)

from .conftest import commit_all, git


def set_title_format(repo: Path, value: str) -> Config:
    """Replace the repository's towncrier ``title_format`` setting.

    Args:
        repo: The repository root.
        value: The TOML value to write, verbatim.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    start = text.index("title_format = ")
    end = text.index("\n", start)
    pyproject.write_text(
        text[:start] + f"title_format = {value}" + text[end:], encoding="utf-8"
    )
    return load_config(repo)


def test_title_format_defaults_when_unset(config: Config, repo: Path) -> None:
    assert title_format(set_title_format(repo, '""')) == DEFAULT_TITLE_FORMAT


def test_title_format_rejects_a_disabled_heading(config: Config, repo: Path) -> None:
    """A `title_format = false` writes towncrier sections with no version heading."""
    reloaded = set_title_format(repo, "false")
    with pytest.raises(ReleaseError, match="no version heading"):
        title_format(reloaded)


def test_title_format_rejects_a_non_string(config: Config, repo: Path) -> None:
    reloaded = set_title_format(repo, "3")
    with pytest.raises(ReleaseError, match="must be a string"):
        title_format(reloaded)


def set_orphan_prefix(repo: Path, value: str) -> Config:
    """Configure the repository's towncrier ``orphan_prefix``.

    Args:
        repo: The repository root.
        value: The TOML value to write, verbatim.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\n[tool.towncrier]\n",
            f"\n[tool.towncrier]\norphan_prefix = {value}\n",
        ),
        encoding="utf-8",
    )
    return load_config(repo)


def commit_fragment(config: Config, package: str, name: str, message: str) -> Path:
    """Write a news fragment and commit it with a message.

    Args:
        config: The repository configuration.
        package: The package name.
        name: The fragment filename.
        message: The commit message to land it with.

    Returns:
        The fragment path.
    """
    path = config.news_dir(package) / name
    path.write_text("Something.\n", encoding="utf-8")
    commit_all(config.root, message)
    return path


def test_orphan_prefix_defaults_to_towncriers_own(config: Config) -> None:
    assert orphan_prefix(config) == "+"


def test_orphan_prefix_is_configurable(config: Config, repo: Path) -> None:
    assert orphan_prefix(set_orphan_prefix(repo, '"~"')) == "~"


def test_orphan_prefix_rejects_a_non_string(config: Config, repo: Path) -> None:
    with pytest.raises(ReleaseError, match="must be a string"):
        orphan_prefix(set_orphan_prefix(repo, "3"))


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("feat: add a thing (#1234)", "1234"),
        ("ENG-1 refactor(log): split it up (4/5) (#6866)", "6866"),
        ("Merge pull request #77 from someone/branch\n\nfeat: a thing", "77"),
        ("feat: add a thing (#1234)\n\nA body.", "1234"),
        ("feat: add a thing", None),
        # A number in the body references an issue, not the pull request.
        ("feat: add a thing\n\nFixes #12", None),
        ("feat: add a thing\n\n(#12)", None),
        ("feat: add a thing (#12) and more", None),
        ("", None),
    ],
)
def test_pull_request_number(message: str, expected: str | None) -> None:
    assert pull_request_number(message) == expected


@pytest.mark.parametrize(
    ("basename", "expected"),
    [
        ("+something.feature.md", ("+something", "feature.md")),
        ("1234.bugfix.md", ("1234", "bugfix.md")),
        ("+something.feature.1.md", ("+something", "feature.1.md")),
        ("+something.feature", ("+something", "feature")),
        # The last part naming a type wins, as in towncrier.
        ("+feature.bugfix.md", ("+feature", "bugfix.md")),
        ("README.md", None),
        ("feature", None),
    ],
)
def test_split_fragment_name(
    config: Config, basename: str, expected: tuple[str, str] | None
) -> None:
    assert split_fragment_name(basename, fragment_types(config)) == expected


def test_associate_names_an_orphan_after_its_pull_request(
    config: Config, repo: Path
) -> None:
    commit_fragment(config, "widget-core", "+a-thing.feature.md", "feat: a thing (#42)")

    assert associate_orphan_fragments(config, "widget-core") == [
        ("+a-thing.feature.md", "42.feature.md")
    ]
    news = config.news_dir("widget-core")
    assert not (news / "+a-thing.feature.md").exists()
    assert (news / "42.feature.md").is_file()


def test_associate_stages_the_rename(config: Config, repo: Path) -> None:
    """Only fragments git knows about get their deletion staged by towncrier."""
    commit_fragment(config, "widget-core", "+a-thing.feature.md", "feat: a thing (#42)")

    associate_orphan_fragments(config, "widget-core")

    staged = git(repo, "diff", "--cached", "--name-status", "--no-renames").split()
    assert staged == [
        "D",
        "packages/widget-core/news/+a-thing.feature.md",
        "A",
        "packages/widget-core/news/42.feature.md",
    ]


def test_associate_reads_a_merge_commit_subject(config: Config, repo: Path) -> None:
    """A repository that lands pull requests as merge commits names them there."""
    git(repo, "checkout", "-q", "-b", "feature")
    commit_fragment(config, "widget-core", "+a-thing.feature.md", "add a fragment")
    git(repo, "checkout", "-q", "main")
    git(
        repo,
        "merge",
        "--no-ff",
        "-q",
        "-m",
        "Merge pull request #99 from someone/feature",
        "feature",
    )

    assert associate_orphan_fragments(config, "widget-core") == [
        ("+a-thing.feature.md", "99.feature.md")
    ]


def test_associate_looks_past_a_merge_that_is_not_a_pull_request(
    config: Config, repo: Path
) -> None:
    """A prerelease train pulls new work in by merging main, which names no PR."""
    git(repo, "branch", "r/pre-1")
    commit_fragment(config, "widget-core", "+a-thing.feature.md", "feat: a thing (#55)")
    git(repo, "checkout", "-q", "r/pre-1")
    git(
        repo, "merge", "--no-ff", "-q", "-m", "Merge branch 'main' into r/pre-1", "main"
    )

    assert associate_orphan_fragments(config, "widget-core") == [
        ("+a-thing.feature.md", "55.feature.md")
    ]


def test_associate_ignores_the_history_of_a_reused_path(
    config: Config, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A new fragment is not the one an earlier release consumed at that path."""
    news = config.news_dir("widget-core")
    commit_fragment(config, "widget-core", "+.feature.md", "feat: an old thing (#7)")
    (news / "+.feature.md").unlink()
    commit_all(repo, "release: v0.1.0")
    (news / "+.feature.md").write_text("A new thing.\n", encoding="utf-8")

    assert associate_orphan_fragments(config, "widget-core") == []
    assert (news / "+.feature.md").is_file()
    assert "::warning::" in capsys.readouterr().out


def test_associate_matches_a_glob_like_filename_literally(
    config: Config, repo: Path
) -> None:
    """A fragment name holding brackets is a path, not a git pathspec."""
    commit_fragment(
        config, "widget-core", "+a[b].feature.md", "feat: the real one (#222)"
    )
    commit_fragment(config, "widget-core", "+ab.feature.md", "feat: a sibling (#111)")

    assert associate_orphan_fragments(config, "widget-core") == [
        ("+a[b].feature.md", "222.feature.md"),
        ("+ab.feature.md", "111.feature.md"),
    ]


def test_associate_leaves_numbered_fragments_alone(config: Config, repo: Path) -> None:
    commit_fragment(config, "widget-core", "7.feature.md", "feat: a thing (#42)")

    assert associate_orphan_fragments(config, "widget-core") == []
    assert (config.news_dir("widget-core") / "7.feature.md").is_file()


def test_associate_keeps_an_orphan_without_a_pull_request(
    config: Config, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit_fragment(
        config, "widget-core", "+a-thing.feature.md", "pushed straight to main"
    )

    assert associate_orphan_fragments(config, "widget-core") == []
    assert (config.news_dir("widget-core") / "+a-thing.feature.md").is_file()
    assert "::warning::" in capsys.readouterr().out


def test_associate_keeps_an_uncommitted_orphan(
    config: Config, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fragment that never landed has no commit to read a number from."""
    (config.news_dir("widget-core") / "+a-thing.feature.md").write_text(
        "Something.\n", encoding="utf-8"
    )

    assert associate_orphan_fragments(config, "widget-core") == []
    assert (config.news_dir("widget-core") / "+a-thing.feature.md").is_file()
    assert "::warning::" in capsys.readouterr().out


def test_associate_counts_up_on_a_name_collision(config: Config, repo: Path) -> None:
    """A pull request can leave behind more than one fragment of a type."""
    news = config.news_dir("widget-core")
    (news / "42.feature.md").write_text("Numbered.\n", encoding="utf-8")
    (news / "+one.feature.md").write_text("One.\n", encoding="utf-8")
    (news / "+two.feature.md").write_text("Two.\n", encoding="utf-8")
    commit_all(repo, "feat: three entries (#42)")

    assert associate_orphan_fragments(config, "widget-core") == [
        ("+one.feature.md", "42.feature.1.md"),
        ("+two.feature.md", "42.feature.2.md"),
    ]
    assert sorted(path.name for path in news.iterdir()) == [
        ".gitkeep",
        "42.feature.1.md",
        "42.feature.2.md",
        "42.feature.md",
    ]


def test_associate_honors_a_custom_orphan_prefix(config: Config, repo: Path) -> None:
    reloaded = set_orphan_prefix(repo, '"~"')
    commit_fragment(
        reloaded, "widget-core", "~a-thing.feature.md", "feat: a thing (#42)"
    )

    assert associate_orphan_fragments(reloaded, "widget-core") == [
        ("~a-thing.feature.md", "42.feature.md")
    ]


def test_associate_skips_a_package_without_a_news_directory(
    config: Config, repo: Path
) -> None:
    shutil.rmtree(config.news_dir("mypkg"))
    assert associate_orphan_fragments(config, "mypkg") == []


def test_associate_is_a_no_op_when_orphans_are_disabled(
    config: Config, repo: Path
) -> None:
    reloaded = set_orphan_prefix(repo, '""')
    commit_fragment(
        reloaded, "widget-core", "+a-thing.feature.md", "feat: a thing (#42)"
    )

    assert associate_orphan_fragments(reloaded, "widget-core") == []
    assert (reloaded.news_dir("widget-core") / "+a-thing.feature.md").is_file()


def never_publish(repo: Path, package: str) -> Config:
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


def test_never_published_packages_are_not_releasable(
    config: Config, repo: Path
) -> None:
    assert releasable_packages(config) == ["mypkg", "widget-core"]
    assert releasable_packages(never_publish(repo, "widget-core")) == ["mypkg"]


def test_never_published_packages_are_never_auto_selected(
    config: Config, repo: Path
) -> None:
    reloaded = never_publish(repo, "widget-core")
    (reloaded.news_dir("widget-core") / "1.feature.md").write_text(
        "Something.\n", encoding="utf-8"
    )
    assert pending_fragment_packages(reloaded) == []


def test_never_published_packages_are_not_publish_triggers(
    config: Config, repo: Path
) -> None:
    """A changelog in a package that never ships must not start a release.

    Detection reads changelogs, not the release selection, so excluding the
    package from the selection alone would leave a stray or leftover
    CHANGELOG.md publishing it on the next push.
    """
    reloaded = never_publish(repo, "widget-core")
    reloaded.changelog_path("widget-core").write_text(
        "## v1.0.0a1 (2026-01-01)\n\nNo significant changes.\n", encoding="utf-8"
    )
    assert changelog_packages(reloaded) == []
    assert alpha_train_packages(reloaded) == []
