"""Unit tests for scripts/release.py (the changelog-driven release helper)."""

import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version

# The script relies on ``tomllib`` (stdlib only on 3.11+); on 3.10 it falls back to the
# ``tomli`` backport. Skip the whole module when neither is available, so the tests still
# run on 3.10 whenever ``tomli`` happens to be installed.
if sys.version_info < (3, 11):
    pytest.importorskip("tomli", reason="release.py requires tomli on Python < 3.11")

from scripts import release

CHANGELOG = """## v0.9.7 (2026-07-15)

### Features

- New thing. ([#1](https://example.com/1))

### Bug Fixes

- Fixed thing. ([#2](https://example.com/2))


## v0.9.6 (2026-06-25)

### Features

- Old thing. ([#3](https://example.com/3))
"""

PYPROJECT = """[project]
name = "{name}"
version = "0.0.0"
{extra}
[tool.towncrier]
package = ""
name = ""
directory = "news"
filename = "CHANGELOG.md"
title_format = "## {{version}} ({{project_date}})"
issue_format = "[#{{issue}}](https://example.com/{{issue}})"
start_string = "<!-- towncrier release notes start -->\\n"

[[tool.towncrier.type]]
directory = "feature"
name = "Features"
showcontent = true

[[tool.towncrier.type]]
directory = "bugfix"
name = "Bug Fixes"
showcontent = true
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@e.st", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _bump(repo: Path, package: str, heading: str) -> None:
    """Prepend a new version section to a package's changelog."""
    path = release.changelog_path(repo, package)
    path.write_text(f"{heading}\n\n- bumped\n\n\n{path.read_text()}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal monorepo with a root package, sub-packages, and git tags.

    Contains the ``reflex``/``reflex-base`` lockstep pair, an independent
    ``other-pkg`` with a changelog, and a changelog-less ``bare-pkg``.

    Returns:
        The repo root path.
    """
    (tmp_path / "pyproject.toml").write_text(
        PYPROJECT.format(
            name="reflex", extra='dependencies = ["reflex-base >= 0.9.7"]\n'
        )
    )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    (tmp_path / "news").mkdir()
    for pkg in ("reflex-base", "other-pkg"):
        pkg_dir = tmp_path / "packages" / pkg
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "pyproject.toml").write_text(PYPROJECT.format(name=pkg, extra=""))
        (pkg_dir / "CHANGELOG.md").write_text(CHANGELOG)
        (pkg_dir / "news").mkdir()
    bare = tmp_path / "packages" / "bare-pkg"
    bare.mkdir()
    (bare / "pyproject.toml").write_text(PYPROJECT.format(name="bare-pkg", extra=""))
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    for tag in ("v0.9.7", "reflex-base-v0.9.7", "other-pkg-v0.9.7", "bare-pkg-v0.1.5"):
        _git(tmp_path, "tag", tag)
    return tmp_path


@pytest.fixture
def gh_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point GITHUB_OUTPUT/GITHUB_STEP_SUMMARY at temp files.

    Returns:
        The output file path.
    """
    output = tmp_path / "github_output.txt"
    summary = tmp_path / "github_summary.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    return output


def _outputs(output: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in output.read_text().splitlines() if "=" in line
    )


def test_latest_version_returns_first_versioned_heading():
    assert release.latest_version(CHANGELOG) == Version("0.9.7")


@pytest.mark.parametrize(
    "heading",
    ["## Unreleased", "## unreleased", "## v0.9.8 (Unreleased)", "## Not A Version"],
)
def test_latest_version_skips_unreleased_and_invalid(heading: str):
    assert release.latest_version(f"{heading}\n\n- stuff\n\n{CHANGELOG}") == Version(
        "0.9.7"
    )


def test_latest_version_none_for_empty():
    assert release.latest_version("") is None
    assert release.latest_version("# Title\n\nprose only\n") is None


def test_extract_notes():
    notes = release.extract_notes(CHANGELOG, Version("0.9.6"))
    assert notes == "### Features\n\n- Old thing. ([#3](https://example.com/3))"
    assert release.extract_notes(CHANGELOG, Version("0.1.0")) is None


def test_tag_naming():
    assert release.tag_for("reflex", "1.2.3") == "v1.2.3"
    assert release.tag_for("reflex-base", "1.2.3a1") == "reflex-base-v1.2.3a1"
    assert release.package_dir("reflex") == "."
    assert release.package_dir("reflex-base") == "packages/reflex-base"


def test_lockstep_partner():
    assert release.lockstep_partner("reflex") == "reflex-base"
    assert release.lockstep_partner("reflex-base") == "reflex"
    assert release.lockstep_partner("other-pkg") is None


@pytest.mark.parametrize(
    ("version", "ref", "allowed"),
    [
        ("1.2.3", "main", True),
        ("1.2.3", "r/hotfix/0.9", True),
        ("1.2.3", "r/hotfix/0.9/fix", True),
        ("1.2.3.post1", "main", True),
        ("1.2.3", "r/pre-2026.07.29", False),
        ("1.2.3", "feature-branch", False),
        ("1.2.3", "r/hotfixes", False),
        ("1.2.3a1", "r/pre-2026.07.29", True),
        ("1.2.3a1", "r/hotfix/0.9", True),
        ("1.2.3a1", "main", False),
        ("1.2.3a1", "feature-branch", False),
        ("1.2.3a1", "r/prerelease", False),
    ],
)
def test_branch_allows_publish(version: str, ref: str, allowed: bool):
    assert release.branch_allows_publish(Version(version), ref) is allowed


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        ("0.9.7", "new-prerelease-patch", "0.9.8a1"),
        ("0.9.7", "new-prerelease-minor", "0.10.0a1"),
        ("0.9.7", "new-prerelease-major", "1.0.0a1"),
        ("0.10.0a1", "continued-prerelease", "0.10.0a2"),
        ("0.10.0a2", "release-from-prerelease", "0.10.0"),
        ("0.9.7", "release-post", "0.9.7.post1"),
        ("0.9.7.post1", "release-post", "0.9.7.post2"),
        ("0.9.7", "release-patch", "0.9.8"),
        ("0.9.7", "release-minor", "0.10.0"),
        ("0.9.7", "release-major", "1.0.0"),
        (None, "new-prerelease-minor", "0.1.0a1"),
        (None, "release-patch", "0.0.1"),
    ],
)
def test_next_version(current: str | None, action: str, expected: str):
    parsed = Version(current) if current is not None else None
    assert release.next_version(parsed, action, "pkg") == expected


@pytest.mark.parametrize(
    ("current", "action"),
    [
        ("0.9.7", "continued-prerelease"),
        (None, "continued-prerelease"),
        ("0.9.7", "release-from-prerelease"),
        ("0.10.0a1", "release-post"),
        (None, "release-post"),
        # new-prerelease-* must not silently abandon an in-progress train.
        ("1.2.3a5", "new-prerelease-patch"),
        ("1.2.3a5", "new-prerelease-minor"),
        ("1.2.3a5", "new-prerelease-major"),
        # Only aN prereleases are supported.
        ("1.2.3rc1", "continued-prerelease"),
        ("1.2.3b1", "release-from-prerelease"),
    ],
)
def test_next_version_rejects_invalid_baselines(current: str | None, action: str):
    parsed = Version(current) if current is not None else None
    with pytest.raises(SystemExit):
        release.next_version(parsed, action, "pkg")


def test_next_version_names_unsupported_prerelease_form(
    capsys: pytest.CaptureFixture,
):
    with pytest.raises(SystemExit):
        release.next_version(Version("1.2.3rc1"), "continued-prerelease", "pkg")
    assert "only alpha aN prereleases are supported" in capsys.readouterr().err


def test_collapse_prereleases_merges_categories_in_order():
    text = (
        "## v0.10.0 (2026-07-29)\n\nNo significant changes.\n\n\n"
        "## v0.10.0a2 (2026-07-20)\n\n### Bug Fixes\n\n- Fix from a2. ([#5](x))\n\n\n"
        "## v0.10.0a1 (2026-07-10)\n\n### Features\n\n- Feat from a1. ([#4](x))\n\n"
        "### Bug Fixes\n\n- Fix from a1. ([#3](x))\n\n\n"
        "## v0.9.7 (2026-07-15)\n\n### Features\n\n- Old. ([#1](x))\n"
    )
    result = release.collapse_prereleases(
        text, Version("0.10.0"), "2026-07-29", ["Features", "Bug Fixes"]
    )
    assert result == (
        "## v0.10.0 (2026-07-29)\n\n"
        "### Features\n\n- Feat from a1. ([#4](x))\n\n"
        "### Bug Fixes\n\n- Fix from a1. ([#3](x))\n- Fix from a2. ([#5](x))\n"
        "\n\n"
        "## v0.9.7 (2026-07-15)\n\n### Features\n\n- Old. ([#1](x))\n"
    )


def test_collapse_prereleases_no_content_keeps_placeholder():
    text = "## v0.10.0 (2026-07-29)\n\nNo significant changes.\n\n\n## v0.10.0a1 (2026-07-10)\n\nNo significant changes.\n"
    result = release.collapse_prereleases(text, Version("0.10.0"), "2026-07-29", [])
    assert result == "## v0.10.0 (2026-07-29)\n\nNo significant changes.\n"


def test_collapse_prereleases_warns_on_stray_alpha(capsys: pytest.CaptureFixture):
    text = (
        "## v0.10.0 (2026-07-29)\n\n### Features\n\n- New. ([#9](x))\n\n\n"
        "## v0.9.7 (2026-07-15)\n\n### Features\n\n- Old. ([#1](x))\n\n\n"
        "## v0.9.7a1 (2026-07-01)\n\n### Features\n\n- Stray. ([#2](x))\n"
    )
    result = release.collapse_prereleases(
        text, Version("0.10.0"), "2026-07-29", ["Features"]
    )
    assert "Stray." in result
    assert "## v0.9.7a1 (2026-07-01)" in result
    assert "not contiguous" in capsys.readouterr().err


def test_collapse_prereleases_fails_without_top_run():
    with pytest.raises(SystemExit):
        release.collapse_prereleases(CHANGELOG, Version("0.10.0"), "2026-07-29", [])


def test_git_tag_helpers(repo: Path):
    assert release.latest_tag_version(repo, "reflex-base") == Version("0.9.7")
    assert release.latest_tag_version(repo, "missing-pkg") is None
    assert release.tag_exists(repo, "reflex-base-v0.9.7")
    assert not release.tag_exists(repo, "reflex-base-v0.9.8")


def test_latest_final_tag_version_ignores_prereleases(repo: Path):
    _git(repo, "tag", "v0.10.0a1")
    assert release.latest_tag_version(repo, "reflex") == Version("0.10.0a1")
    assert release.latest_final_tag_version(repo, "reflex") == Version("0.9.7")


def test_current_version_prefers_changelog_over_tags(repo: Path):
    _bump(repo, "reflex-base", "## v0.10.0a1 (2026-07-29)")
    assert release.current_version(repo, "reflex-base") == Version("0.10.0a1")
    # bare-pkg has no changelog: falls back to its newest tag.
    assert release.current_version(repo, "bare-pkg") == Version("0.1.5")


def test_discover_changelog_packages(repo: Path):
    assert release.discover_changelog_packages(repo) == [
        "reflex",
        "other-pkg",
        "reflex-base",
    ]


def test_load_category_order(repo: Path):
    assert release.load_category_order(repo) == ["Features", "Bug Fixes"]


def test_cmd_detect_finds_untagged_versions(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("REF_NAME", "main")
    _bump(repo, "reflex", "## v0.9.8 (2026-07-29)")
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    release.cmd_detect()
    outputs = _outputs(gh_env)
    assert outputs["any"] == "true"
    # reflex is emitted separately so it publishes after its dependencies.
    assert outputs["reflex_version"] == "0.9.8"
    assert json.loads(outputs["packages"]) == [
        {
            "package": "reflex-base",
            "version": "0.9.8",
            "tag": "reflex-base-v0.9.8",
        }
    ]


def test_cmd_detect_branch_policy(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    # A final on a prerelease branch and an alpha on main both get skipped.
    _bump(repo, "other-pkg", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("REF_NAME", "r/pre-2026.07.29")
    release.cmd_detect()
    assert json.loads(_outputs(gh_env)["packages"]) == []

    gh_env.unlink()
    monkeypatch.setenv("REF_NAME", "main")
    _bump(repo, "other-pkg", "## v0.10.0a1 (2026-07-29)")
    release.cmd_detect()
    assert json.loads(_outputs(gh_env)["packages"]) == []

    # The alpha publishes from the r/pre-* branch it belongs on.
    gh_env.unlink()
    monkeypatch.setenv("REF_NAME", "r/pre-2026.07.29")
    release.cmd_detect()
    outputs = _outputs(gh_env)
    assert outputs["reflex_version"] == ""
    assert json.loads(outputs["packages"]) == [
        {
            "package": "other-pkg",
            "version": "0.10.0a1",
            "tag": "other-pkg-v0.10.0a1",
        }
    ]


def test_cmd_detect_all_tagged(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("REF_NAME", "main")
    release.cmd_detect()
    outputs = _outputs(gh_env)
    assert outputs["any"] == "false"
    assert outputs["reflex_version"] == ""
    assert json.loads(outputs["packages"]) == []


def test_cmd_detect_fails_closed_on_lockstep_violation(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("REF_NAME", "main")
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    with pytest.raises(SystemExit):
        release.cmd_detect()


def test_cmd_detect_lockstep_satisfied_by_existing_tag(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("REF_NAME", "main")
    # reflex is due alone, but reflex-base already published 0.9.8 (retry case).
    _bump(repo, "reflex", "## v0.9.8 (2026-07-29)")
    _git(repo, "tag", "reflex-base-v0.9.8")
    release.cmd_detect()
    outputs = _outputs(gh_env)
    assert outputs["reflex_version"] == "0.9.8"
    assert json.loads(outputs["packages"]) == []
    assert outputs["any"] == "false"


def test_cmd_plan_pairs_reflex_with_reflex_base(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("ACTION", "release-minor")
    monkeypatch.setenv("PACKAGES_JSON", '["reflex-base"]')
    release.cmd_plan()
    releases = json.loads(_outputs(gh_env)["releases"])
    assert releases == [
        {
            "package": "reflex-base",
            "current": "0.9.7",
            "next": "0.10.0",
            "tag": "reflex-base-v0.10.0",
        },
        {"package": "reflex", "current": "0.9.7", "next": "0.10.0", "tag": "v0.10.0"},
    ]


def test_cmd_plan_fails_on_existing_tag(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    _git(repo, "tag", "reflex-base-v0.10.0")
    monkeypatch.setenv("ACTION", "release-minor")
    monkeypatch.setenv("PACKAGES_JSON", '["reflex-base"]')
    with pytest.raises(SystemExit):
        release.cmd_plan()


def test_cmd_materialize_builds_and_collapses(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    pkg = repo / "packages" / "reflex-base"
    (pkg / "CHANGELOG.md").write_text(
        f"## v0.10.0a1 (2026-07-10)\n\n### Features\n\n- From alpha. ([#7](https://example.com/7))\n\n\n{CHANGELOG}"
    )
    (pkg / "news" / "8.bugfix.md").write_text("Late fix.")
    monkeypatch.setenv("ACTION", "release-from-prerelease")
    monkeypatch.setenv(
        "RELEASES_JSON", json.dumps([{"package": "reflex-base", "next": "0.10.0"}])
    )
    release.cmd_materialize()
    text = (pkg / "CHANGELOG.md").read_text()
    assert "a1" not in text.split("## v0.9.7")[0]
    assert text.index("## v0.10.0 (") < text.index("### Features")
    assert "- From alpha. ([#7](https://example.com/7))" in text
    assert "Late fix." in text
    assert text.index("### Features") < text.index("### Bug Fixes")
    assert not (pkg / "news" / "8.bugfix.md").exists()
    # The old sections are preserved verbatim.
    assert CHANGELOG in text


def test_cmd_prepare_publish_happy_path(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    _bump(repo, "reflex", "## v0.9.8 (2026-07-29)")
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("PACKAGE", "reflex-base")
    monkeypatch.setenv("VERSION", "0.9.8")
    monkeypatch.setenv("REF_NAME", "main")
    release.cmd_prepare_publish()
    outputs = _outputs(gh_env)
    assert outputs["tag"] == "reflex-base-v0.9.8"
    assert outputs["build_dir"] == "packages/reflex-base"
    assert outputs["prerelease"] == "false"
    assert outputs["mark_latest"] == "false"
    assert outputs["skipped"] == "false"


def test_cmd_prepare_publish_marks_reflex_final_latest(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    _bump(repo, "reflex", "## v0.9.8 (2026-07-29)")
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("PACKAGE", "reflex")
    monkeypatch.setenv("VERSION", "v0.9.8")
    monkeypatch.setenv("REF_NAME", "main")
    release.cmd_prepare_publish()
    outputs = _outputs(gh_env)
    assert outputs["tag"] == "v0.9.8"
    assert outputs["build_dir"] == "."
    assert outputs["mark_latest"] == "true"


def test_cmd_prepare_publish_hotfix_of_old_line_is_not_latest(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    # A newer final release exists: the hotfix must not steal the badge.
    _git(repo, "tag", "v0.10.0")
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    _bump(repo, "reflex", "## v0.9.8 (2026-07-29)")
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("PACKAGE", "reflex")
    monkeypatch.setenv("VERSION", "0.9.8")
    monkeypatch.setenv("REF_NAME", "r/hotfix/0.9")
    release.cmd_prepare_publish()
    assert _outputs(gh_env)["mark_latest"] == "false"


def test_cmd_prepare_publish_skips_existing_tag(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("PACKAGE", "reflex-base")
    monkeypatch.setenv("VERSION", "0.9.7")
    monkeypatch.setenv("REF_NAME", "main")
    release.cmd_prepare_publish()
    assert _outputs(gh_env)["skipped"] == "true"


def test_cmd_prepare_publish_enforces_lockstep(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    # reflex-base is materialized at 0.9.8 but reflex is not (and no v0.9.8 tag).
    _bump(repo, "reflex-base", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("PACKAGE", "reflex-base")
    monkeypatch.setenv("VERSION", "0.9.8")
    monkeypatch.setenv("REF_NAME", "main")
    with pytest.raises(SystemExit):
        release.cmd_prepare_publish()
    # The partner being already tagged satisfies the invariant (retry case).
    _git(repo, "tag", "v0.9.8")
    release.cmd_prepare_publish()
    assert _outputs(gh_env)["skipped"] == "false"


@pytest.mark.parametrize(
    ("package", "version", "ref"),
    [
        # Final version from a non-release branch.
        ("other-pkg", "0.9.8", "r/pre-2026.07.29"),
        # Prerelease version from main.
        ("other-pkg", "0.10.0a1", "main"),
        # Version does not match the newest changelog version.
        ("other-pkg", "0.9.9", "main"),
        # Empty version is only allowed without a changelog.
        ("other-pkg", "", "main"),
        # Dev/local/epoch versions never publish.
        ("other-pkg", "0.9.8.dev1", "main"),
        ("other-pkg", "0.9.8+local", "main"),
        ("bad/../name", "0.9.8", "main"),
        ("no-such-pkg", "0.9.8", "main"),
        ("other-pkg", "not-a-version", "main"),
    ],
)
def test_cmd_prepare_publish_rejects(
    repo: Path,
    gh_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    package: str,
    version: str,
    ref: str,
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    _bump(repo, "other-pkg", "## v0.9.8 (2026-07-29)")
    monkeypatch.setenv("PACKAGE", package)
    monkeypatch.setenv("VERSION", version)
    monkeypatch.setenv("REF_NAME", ref)
    with pytest.raises(SystemExit):
        release.cmd_prepare_publish()


def test_cmd_prepare_publish_auto_version_for_changelogless(
    repo: Path, gh_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("PACKAGE", "bare-pkg")
    monkeypatch.setenv("VERSION", "")
    monkeypatch.setenv("REF_NAME", "main")
    release.cmd_prepare_publish()
    outputs = _outputs(gh_env)
    assert outputs["version"] == "0.1.6"
    assert outputs["tag"] == "bare-pkg-v0.1.6"
    assert outputs["skipped"] == "false"


def test_cmd_pin_reflex_base(repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("VERSION", "0.9.8")
    release.cmd_pin_reflex_base()
    text = (repo / "pyproject.toml").read_text()
    assert '"reflex-base == 0.9.8"' in text
    assert '"reflex-base >= ' not in text
    # A second run finds no range requirement left to rewrite.
    with pytest.raises(SystemExit):
        release.cmd_pin_reflex_base()


def _write_wheel(path: Path, name: str, version: str) -> None:
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n\nVersion: 9.9.9 in the description is ignored.\n",
        )


def _write_sdist(path: Path, name: str, version: str) -> None:
    with tarfile.open(path, "w:gz") as sdist:
        payload = f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n".encode()
        info = tarfile.TarInfo(f"{name}-{version}/PKG-INFO")
        info.size = len(payload)
        sdist.addfile(info, io.BytesIO(payload))


def test_cmd_verify_dist(repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    dist = repo / "dist"
    dist.mkdir()
    _write_wheel(dist / "demo-0.9.8-py3-none-any.whl", "demo", "0.9.8")
    _write_sdist(dist / "demo-0.9.8.tar.gz", "demo", "0.9.8")
    monkeypatch.setenv("VERSION", "0.9.8")
    release.cmd_verify_dist()

    # A wrong-version artifact fails the check.
    _write_wheel(dist / "demo-0.9.9-py3-none-any.whl", "demo", "0.9.9")
    with pytest.raises(SystemExit):
        release.cmd_verify_dist()


def test_cmd_verify_dist_empty(repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    (repo / "dist").mkdir()
    monkeypatch.setenv("VERSION", "0.9.8")
    with pytest.raises(SystemExit):
        release.cmd_verify_dist()


def test_cmd_check_headings_passes_without_new_headings(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("BASE_REF", "HEAD")
    release.cmd_check_headings()
    # Editing an existing section's content is fine too.
    path = release.changelog_path(repo, "reflex-base")
    path.write_text(path.read_text().replace("New thing.", "New thing, reworded."))
    release.cmd_check_headings()


@pytest.mark.parametrize(
    "heading",
    [
        "## v0.9.9 (2026-01-01)",
        # Whitespace/case variants the old grep-based guard missed but the
        # release parser (and therefore the publisher) accepts.
        "##  v0.9.9 (2026-01-01)",
        "## V0.9.9 (2026-01-01)",
        "##   0.9.9 (2026-01-01)",
        "## v0.9.9rc1 (2026-01-01)",
    ],
)
def test_cmd_check_headings_rejects_new_headings(
    repo: Path, monkeypatch: pytest.MonkeyPatch, heading: str
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("BASE_REF", "HEAD")
    _bump(repo, "other-pkg", heading)
    with pytest.raises(SystemExit):
        release.cmd_check_headings()


def test_cmd_check_headings_rejects_new_changelog_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    monkeypatch.setenv("BASE_REF", "HEAD")
    (repo / "packages" / "bare-pkg" / "CHANGELOG.md").write_text(
        "## v0.1.6 (2026-01-01)\n\n- new\n"
    )
    with pytest.raises(SystemExit):
        release.cmd_check_headings()


def test_cmd_extract_notes(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(release, "REPO_ROOT", repo)
    notes_path = tmp_path / "notes.md"
    monkeypatch.setenv("PACKAGE", "reflex-base")
    monkeypatch.setenv("VERSION", "0.9.6")
    monkeypatch.setenv("NOTES_PATH", str(notes_path))
    release.cmd_extract_notes()
    assert notes_path.read_text() == (
        "### Features\n\n- Old thing. ([#3](https://example.com/3))\n"
    )
    # Fallback for a package without a changelog section.
    monkeypatch.setenv("PACKAGE", "bare-pkg")
    monkeypatch.setenv("VERSION", "0.1.6")
    release.cmd_extract_notes()
    assert notes_path.read_text() == "Release of bare-pkg 0.1.6.\n"
