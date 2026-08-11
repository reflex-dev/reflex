"""Tests for reflex_release.config."""

from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.config import Config, is_final, load_config


def write_config(repo: Path, body: str) -> None:
    """Replace the ``[tool.reflex-release]`` table of a repository.

    Args:
        repo: The repository root.
        body: The table body (without the header line).
    """
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text()
    head, _, rest = text.partition("[tool.reflex-release]\n")
    _, _, tail = rest.partition("\n[tool.towncrier]")
    pyproject.write_text(f"{head}[tool.reflex-release]\n{body}\n[tool.towncrier]{tail}")


def test_paths_and_tags(config: Config) -> None:
    assert config.package_dir("mypkg") == "."
    assert config.package_dir("widget-core") == "packages/widget-core"
    assert config.tag_for("mypkg", "1.2.3") == "v1.2.3"
    assert config.tag_for("widget-core", "1.2.3") == "widget-core-v1.2.3"
    assert config.changelog_path("widget-core").name == "CHANGELOG.md"
    assert config.all_packages() == ["mypkg", "widget-core"]


def test_tag_prefix_applies_to_sub_packages_too(config: Config, repo: Path) -> None:
    write_config(
        repo, 'root-package = "mypkg"\npackages-dir = "packages"\ntag-prefix = ""\n'
    )
    reloaded = load_config(repo)
    assert reloaded.tag_for("mypkg", "1.2.3") == "1.2.3"
    assert reloaded.tag_for("widget-core", "1.2.3") == "widget-core-1.2.3"


def test_root_source_dirs_default_to_src_layout(config: Config) -> None:
    assert config.root_source_dirs == ("src",)


def test_root_source_dirs_default_to_flat_module(tmp_path: Path) -> None:
    (tmp_path / "my_pkg").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-pkg"\n\n[tool.reflex-release]\nroot-package = "my-pkg"\n'
    )
    assert load_config(tmp_path).root_source_dirs == ("my_pkg",)


def test_is_package_source(config: Config) -> None:
    assert config.is_package_source("mypkg", "src/mypkg/app.py")
    assert not config.is_package_source("mypkg", "docs/index.md")
    assert not config.is_package_source("mypkg", "news/1.feature.md")
    assert not config.is_package_source("mypkg", "CHANGELOG.md")
    assert config.is_package_source("widget-core", "packages/widget-core/src/w.py")
    assert not config.is_package_source(
        "widget-core", "packages/widget-core/news/2.bugfix.md"
    )
    assert not config.is_package_source(
        "widget-core", "packages/widget-core/CHANGELOG.md"
    )
    # The sub-package's src/ exists, so its tests are not published source.
    assert not config.is_package_source(
        "widget-core", "packages/widget-core/tests/t.py"
    )


def test_towncrier_layout_settings_are_honored(config: Config, repo: Path) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject
        .read_text()
        .replace('directory = "news"', 'directory = "changes"')
        .replace('filename = "CHANGELOG.md"', 'filename = "NEWS.md"')
    )
    reloaded = load_config(repo)
    assert reloaded.news_dir("widget-core").name == "changes"
    assert reloaded.changelog_path("widget-core").name == "NEWS.md"
    assert not reloaded.is_package_source("widget-core", "packages/widget-core/NEWS.md")
    assert not reloaded.is_package_source(
        "widget-core", "packages/widget-core/changes/1.bugfix.md"
    )


def test_package_without_src_layout_counts_whole_directory(
    config: Config, repo: Path
) -> None:
    flat = repo / "packages" / "flat"
    flat.mkdir()
    (flat / "pyproject.toml").write_text('[project]\nname = "flat"\n')
    reloaded = load_config(repo)
    assert reloaded.is_package_source("flat", "packages/flat/flat/mod.py")
    assert not reloaded.is_package_source("flat", "packages/flat/news/1.misc.md")


@pytest.mark.parametrize(
    ("version", "branch", "allowed"),
    [
        ("1.2.3", "main", True),
        ("1.2.3", "r/hotfix/0.9", True),
        ("1.2.3", "r/pre-2026.01.01", False),
        ("1.2.3", "feature/x", False),
        ("1.2.3a1", "r/pre-2026.01.01", True),
        ("1.2.3a1", "r/hotfix/0.9", True),
        ("1.2.3a1", "main", False),
        ("1.2.3.post1", "main", True),
    ],
)
def test_branch_allows_publish(
    config: Config, version: str, branch: str, allowed: bool
) -> None:
    assert config.branch_allows_publish(Version(version), branch) is allowed


def test_custom_branch_names(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\nmain-branch = "trunk"\nprerelease-branch-prefix = "pre/"\n',
    )
    reloaded = load_config(repo)
    assert reloaded.branch_allows_publish(Version("1.0.0"), "trunk")
    assert not reloaded.branch_allows_publish(Version("1.0.0"), "main")
    assert reloaded.branch_allows_publish(Version("1.0.0a1"), "pre/2026")


def test_lockstep_helpers(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.lockstep]]\n"
        'members = ["mypkg", "widget-core"]\npublish-last = ["mypkg"]\npin-exact = true\n',
    )
    reloaded = load_config(repo)
    assert reloaded.lockstep_partners("mypkg") == ("widget-core",)
    assert reloaded.lockstep_partners("widget-core") == ("mypkg",)
    assert reloaded.publishes_last("mypkg")
    assert not reloaded.publishes_last("widget-core")
    assert reloaded.exact_pin_targets("mypkg") == ("widget-core",)
    assert reloaded.exact_pin_targets("widget-core") == ()


def test_no_lockstep_by_default(config: Config) -> None:
    assert config.lockstep_partners("mypkg") == ()
    assert not config.publishes_last("mypkg")
    assert config.exact_pin_targets("mypkg") == ()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('root-package = "mypkg"\nbogus = 1\n', "unknown key"),
        ('root-package = "nope"\ninternal-packages = ["ghost"]\n', "unknown package"),
        ('root-package = "mypkg"\nlatest-release-package = "ghost"\n', "unknown"),
        (
            'root-package = "mypkg"\n\n[[tool.reflex-release.lockstep]]\nmembers = ["mypkg"]\n',
            "at least two members",
        ),
        (
            (
                'root-package = "mypkg"\n\n[[tool.reflex-release.lockstep]]\n'
                'members = ["mypkg", "ghost"]\n'
            ),
            "not a package",
        ),
        (
            (
                'root-package = "mypkg"\npackages-dir = "packages"\n\n'
                "[[tool.reflex-release.lockstep]]\n"
                'members = ["mypkg", "widget-core"]\npublish-last = ["ghost"]\n'
            ),
            "not members of the group",
        ),
        (
            (
                'root-package = "mypkg"\npackages-dir = "packages"\n\n'
                "[[tool.reflex-release.lockstep]]\n"
                'members = ["mypkg", "widget-core"]\npin-exact = true\n'
            ),
            "pin-exact requires publish-last",
        ),
        (
            (
                'root-package = "mypkg"\npackages-dir = "packages"\n\n'
                "[[tool.reflex-release.lockstep]]\n"
                'members = ["mypkg", "widget-core"]\n'
                'publish-last = ["mypkg", "widget-core"]\n'
            ),
            "cannot list every member",
        ),
    ],
)
def test_invalid_config(repo: Path, body: str, message: str) -> None:
    write_config(repo, body)
    with pytest.raises(ReleaseError, match=message):
        load_config(repo)


def test_missing_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    with pytest.raises(ReleaseError, match=r"no \[tool\.reflex-release\] table"):
        load_config(tmp_path)


def test_missing_pyproject(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match=r"no pyproject\.toml"):
        load_config(tmp_path)


def test_repo_without_packages_dir(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\n\n[tool.reflex-release]\nroot-package = "solo"\n'
    )
    config = load_config(tmp_path)
    assert config.packages_dir is None
    assert config.all_packages() == ["solo"]
    assert config.sub_packages() == []


def test_repo_describing_no_packages(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.reflex-release]\n")
    with pytest.raises(ReleaseError, match="describes no packages"):
        load_config(tmp_path)


def test_existing_changelogs(config: Config, repo: Path) -> None:
    assert config.existing_changelogs() == []
    (repo / "CHANGELOG.md").write_text("## v1.0.0 (2026-01-01)\n")
    (repo / "packages" / "widget-core" / "CHANGELOG.md").write_text(
        "## v1.0.0 (2026-01-01)\n"
    )
    assert config.existing_changelogs() == [
        "CHANGELOG.md",
        "packages/widget-core/CHANGELOG.md",
    ]


def test_requires_fragments(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n'
        'changelog-exempt-packages = ["widget-core"]\n',
    )
    reloaded = load_config(repo)
    assert reloaded.requires_fragments("mypkg")
    assert not reloaded.requires_fragments("widget-core")


@pytest.mark.parametrize(
    ("version", "final"),
    [("1.0.0", True), ("1.0.0.post1", True), ("1.0.0a1", False), ("1.0.0.dev1", False)],
)
def test_is_final(version: str, final: bool) -> None:
    assert is_final(Version(version)) is final
