"""Tests for reflex_release.config."""

from __future__ import annotations

import re
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
    text = pyproject.read_text(encoding="utf-8")
    head, _, rest = text.partition("[tool.reflex-release]\n")
    _, _, tail = rest.partition("\n[tool.towncrier]")
    pyproject.write_text(
        f"{head}[tool.reflex-release]\n{body}\n[tool.towncrier]{tail}", encoding="utf-8"
    )


def test_paths_and_tags(config: Config) -> None:
    assert config.package_dir("mypkg") == "."
    assert config.package_dir("widget-core") == "packages/widget-core"
    assert config.tag_for("mypkg", "1.2.3") == "v1.2.3"
    assert config.tag_for("widget-core", "1.2.3") == "widget-core-v1.2.3"
    assert config.changelog_path("widget-core").name == "CHANGELOG.md"
    assert config.all_packages() == ["mypkg", "widget-core"]


def test_path_prefix_of_the_root_package_is_empty(config: Config) -> None:
    """Root-package files are not nested under a directory of their own."""
    assert config.path_prefix("mypkg") == ""
    assert config.path_prefix("widget-core") == "packages/widget-core/"


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
        '[project]\nname = "my-pkg"\n\n[tool.reflex-release]\nroot-package = "my-pkg"\n',
        encoding="utf-8",
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
        .read_text(encoding="utf-8")
        .replace('directory = "news"', 'directory = "changes"')
        .replace('filename = "CHANGELOG.md"', 'filename = "NEWS.md"'),
        encoding="utf-8",
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
    (flat / "pyproject.toml").write_text('[project]\nname = "flat"\n', encoding="utf-8")
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


def test_empty_latest_release_package_disables_the_badge(
    config: Config, repo: Path
) -> None:
    write_config(repo, 'root-package = "mypkg"\nlatest-release-package = ""\n')
    assert load_config(repo).latest_release_package is None


def test_self_review_is_allowed_by_default(config: Config) -> None:
    assert config.allow_self_review is True


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
        # A duplicate must not slip past the "every member publishes last" check.
        (
            (
                'root-package = "mypkg"\npackages-dir = "packages"\n\n'
                "[[tool.reflex-release.lockstep]]\n"
                'members = ["mypkg", "widget-core"]\n'
                'publish-last = ["mypkg", "widget-core", "widget-core"]\n'
            ),
            "cannot list every member",
        ),
        ('root-package = "mypkg"\nmain-branch = 5\n', "main-branch must be a string"),
        (
            'root-package = "mypkg"\nallow-self-review = "yes"\n',
            "allow-self-review must be true or false",
        ),
        ('root-package = "mypkg"\nmain-branch = ""\n', "main-branch must not be empty"),
        (
            'root-package = "mypkg"\nrelease-branch-prefix = "main/"\n',
            "nests under the main branch",
        ),
        (
            'root-package = "mypkg"\nlatest-release-package = false\n',
            "latest-release-package must be a string",
        ),
        # An empty prefix matches every branch, collapsing the branch policy.
        (
            'root-package = "mypkg"\nhotfix-branch-prefix = ""\n',
            "hotfix-branch-prefix must not be empty",
        ),
        (
            'root-package = "mypkg"\nprerelease-branch-prefix = ""\n',
            "prerelease-branch-prefix must not be empty",
        ),
        (
            'root-package = "mypkg"\nrelease-branch-prefix = ""\n',
            "release-branch-prefix must not be empty",
        ),
        # A prefix the main branch matches has the same effect.
        (
            'root-package = "mypkg"\nhotfix-branch-prefix = "m"\n',
            "matches the main branch",
        ),
        (
            'root-package = "mypkg"\nrelease-timezone = 5\n',
            "release-timezone must be a string",
        ),
        (
            'root-package = "mypkg"\ndispatch-package-inputs = "maybe"\n',
            "must be one of",
        ),
    ],
)
def test_invalid_config(repo: Path, body: str, message: str) -> None:
    write_config(repo, body)
    with pytest.raises(ReleaseError, match=message):
        load_config(repo)


def test_missing_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8"
    )
    with pytest.raises(ReleaseError, match=r"no \[tool\.reflex-release\] table"):
        load_config(tmp_path)


def test_missing_pyproject(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match=r"no pyproject\.toml"):
        load_config(tmp_path)


def test_repo_without_packages_dir(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\n\n[tool.reflex-release]\nroot-package = "solo"\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.packages_dir is None
    assert config.all_packages() == ["solo"]
    assert config.sub_packages() == []


def test_repo_describing_no_packages(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.reflex-release]\n", encoding="utf-8"
    )
    with pytest.raises(ReleaseError, match="describes no packages"):
        load_config(tmp_path)


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


CUSTOM_BUILD = """\
root-package = "mypkg"
packages-dir = "packages"

[[tool.reflex-release.custom-build]]
packages = ["mypkg"]
workflow = "build_wheels.yml"
expect-artifacts = ["*.tar.gz"]
"""


def test_custom_build_is_resolved_per_package(config: Config, repo: Path) -> None:
    write_config(repo, CUSTOM_BUILD)
    reloaded = load_config(repo)
    entry = reloaded.custom_build_for("mypkg")
    assert entry is not None
    assert entry.workflow == "build_wheels.yml"
    assert reloaded.custom_build_packages() == ("mypkg",)
    assert reloaded.expect_artifacts("mypkg") == ("*.tar.gz",)
    # A package with no entry builds in-repo and carries no expectations.
    assert reloaded.custom_build_for("widget-core") is None
    assert reloaded.expect_artifacts("widget-core") == ()


def test_custom_build_rejects_an_unknown_package(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\n\n[[tool.reflex-release.custom-build]]\n'
        'packages = ["nope"]\nworkflow = "build.yml"\n',
    )
    with pytest.raises(ReleaseError, match="not a package in this repository"):
        load_config(repo)


def test_custom_build_rejects_an_empty_package_list(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\n\n[[tool.reflex-release.custom-build]]\n'
        'packages = []\nworkflow = "build.yml"\n',
    )
    with pytest.raises(ReleaseError, match="at least one package"):
        load_config(repo)


@pytest.mark.parametrize("workflow", ["", "build", "ci/build.yml"])
def test_custom_build_rejects_a_workflow_that_is_not_a_bare_filename(
    config: Config, repo: Path, workflow: str
) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\n\n[[tool.reflex-release.custom-build]]\n'
        f'packages = ["mypkg"]\nworkflow = "{workflow}"\n',
    )
    with pytest.raises(ReleaseError, match="must be a bare filename"):
        load_config(repo)


def test_custom_build_rejects_a_package_listed_twice(
    config: Config, repo: Path
) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["mypkg"]\nworkflow = "one.yml"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["mypkg", "widget-core"]\nworkflow = "two.yml"\n',
    )
    with pytest.raises(ReleaseError, match="more than one custom-build entry"):
        load_config(repo)


def test_custom_build_rejects_two_entries_sharing_a_workflow(
    config: Config, repo: Path
) -> None:
    """One job per entry, so a shared file would collide as a job id."""
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["mypkg"]\nworkflow = "build.yml"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["widget-core"]\nworkflow = "build.yml"\n',
    )
    with pytest.raises(ReleaseError, match="same publish job"):
        load_config(repo)


def test_custom_build_rejects_an_unknown_key(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\n\n[[tool.reflex-release.custom-build]]\n'
        'packages = ["mypkg"]\nworkflow = "build.yml"\nartifacts = ["x"]\n',
    )
    with pytest.raises(ReleaseError, match="unknown key"):
        load_config(repo)


def test_custom_build_is_incompatible_with_an_exact_lockstep_pin(
    config: Config, repo: Path
) -> None:
    """pin-exact rewrites a checkout the custom build workflow never sees."""
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.lockstep]]\n"
        'members = ["mypkg", "widget-core"]\n'
        'publish-last = ["mypkg"]\n'
        "pin-exact = true\n\n"
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["mypkg"]\nworkflow = "build.yml"\n',
    )
    with pytest.raises(ReleaseError, match="pin-exact"):
        load_config(repo)


def test_a_lockstep_member_that_does_not_pin_may_build_custom(
    config: Config, repo: Path
) -> None:
    """Only the pinning member rewrites metadata; its siblings are unaffected."""
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.lockstep]]\n"
        'members = ["mypkg", "widget-core"]\n'
        'publish-last = ["mypkg"]\n'
        "pin-exact = true\n\n"
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["widget-core"]\nworkflow = "build.yml"\n',
    )
    assert load_config(repo).custom_build_packages() == ("widget-core",)


def test_custom_build_rejects_workflows_that_share_a_job_id(
    config: Config, repo: Path
) -> None:
    """Distinct filenames can still collapse into one generated job."""
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["mypkg"]\nworkflow = "build.yml"\n\n'
        "[[tool.reflex-release.custom-build]]\n"
        'packages = ["widget-core"]\nworkflow = "build.yaml"\n',
    )
    with pytest.raises(ReleaseError, match="same publish job"):
        load_config(repo)


@pytest.mark.parametrize(
    "workflow", ["build.yml\njobs: bad", "build .yml: x", "~build.yml", "*.yml"]
)
def test_custom_build_rejects_a_yaml_unsafe_workflow_name(
    config: Config, repo: Path, workflow: str
) -> None:
    """The name is written into `uses:` as a bare scalar."""
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\n[tool.towncrier]",
            "\n[[tool.reflex-release.custom-build]]\n"
            'packages = ["mypkg"]\n'
            f"workflow = {workflow!r}\n\n[tool.towncrier]",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ReleaseError, match="must be a bare filename"):
        load_config(repo)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            'packages = ["mypkg"]\nworkflow = "b.yml"\nexpect-artifacts = "*.whl"\n',
            "[[tool.reflex-release.custom-build]] expect-artifacts",
        ),
        (
            'packages = [1]\nworkflow = "b.yml"\n',
            "[[tool.reflex-release.custom-build]] packages",
        ),
        (
            'packages = ["mypkg"]\nworkflow = 1\n',
            "[[tool.reflex-release.custom-build]] workflow",
        ),
    ],
)
def test_custom_build_type_errors_name_their_own_table(
    config: Config, repo: Path, body: str, expected: str
) -> None:
    """A key in a sub-table must not send the reader to the top-level one."""
    write_config(
        repo,
        'root-package = "mypkg"\n\n[[tool.reflex-release.custom-build]]\n' + body,
    )
    with pytest.raises(ReleaseError, match=re.escape(expected)):
        load_config(repo)


def test_lockstep_type_errors_name_their_own_table(config: Config, repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n\n'
        "[[tool.reflex-release.lockstep]]\nmembers = 1\n",
    )
    with pytest.raises(
        ReleaseError, match=re.escape("[[tool.reflex-release.lockstep]] members")
    ):
        load_config(repo)


def test_post_release_workflow_defaults_to_nothing(config: Config) -> None:
    assert config.post_release_workflow is None


def test_post_release_workflow_is_read_from_the_table(repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n'
        'post-release-workflow = "docs_publish.yml"\n',
    )
    assert load_config(repo).post_release_workflow == "docs_publish.yml"


def test_an_empty_post_release_workflow_dispatches_nothing(repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n'
        'post-release-workflow = ""\n',
    )
    assert load_config(repo).post_release_workflow is None


def test_post_release_workflow_must_be_a_string(repo: Path) -> None:
    write_config(
        repo,
        'root-package = "mypkg"\npackages-dir = "packages"\n'
        "post-release-workflow = true\n",
    )
    with pytest.raises(ReleaseError, match="must be a string"):
        load_config(repo)
