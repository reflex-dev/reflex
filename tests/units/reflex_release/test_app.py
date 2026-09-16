"""Application release tests using real repositories and pinned submodule commits."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml
from reflex_release import app
from reflex_release.actions import ReleaseError
from reflex_release.cli import main
from reflex_release.config import Config, load_config
from reflex_release.scaffold import managed_workflows, render, sync

from .conftest import commit_all, git


@pytest.fixture
def app_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    root = tmp_path / "app"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[tool.reflex-release]\n[tool.reflex-release.app]\n"
        'build-workflow = "build.yml"\ndeploy-workflow = "deploy.yml"\n'
        'dev-schedule = "*/30 * * * *"\n'
    )
    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True)
    for name, inputs in (
        ("build", ("ref", "version", "source-revision")),
        ("deploy", ("ref", "version", "environment")),
    ):
        (workflows / f"{name}.yml").write_text(
            "on:\n  workflow_call:\n    inputs:\n"
            + "".join(
                f"      {field}:\n        type: string\n        required: true\n"
                for field in inputs
            )
            + "jobs: {}\n"
        )
    git(root, "init", "-q", "-b", "main")
    commit_all(root)
    remote = tmp_path / "remote.git"
    git(root, "clone", "--bare", str(root), str(remote))
    git(root, "remote", "add", "origin", str(remote))

    class FrozenDateTime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 11, 12, tzinfo=tz)

    monkeypatch.setattr(app.dt, "datetime", FrozenDateTime)
    return load_config(root)


def test_materialize_reserves_versions_from_tags_and_open_pr_branches(app_repo: Config):
    root = app_repo.root
    git(root, "tag", "2026.37.2")
    git(root, "push", "origin", "HEAD:refs/heads/release/2026.37.3")
    version = app.materialize(app_repo, "", "Fix docs\n\n## 9999.1.0\nMore detail")
    assert version == "2026.37.4"
    assert [version for version, _ in app.sections(app_repo)] == [version]
    assert "  ## 9999.1.0" in (root / "CHANGELOG.md").read_text()
    assert not app.tag_exists(root, version)
    assert app.materialize(app_repo, "", "Again") == "2026.37.5"


@pytest.mark.parametrize(
    ("version", "date", "counter"),
    [
        ("2020.53.0", dt.date(2020, 12, 28), 0),
        ("2026.1.10", dt.date(2025, 12, 29), 10),
    ],
)
def test_iso_week_versions(version, date, counter):
    assert app.version_key(version) == (date, counter)


@pytest.mark.parametrize(
    "version",
    ["2021.53.0", "2026.0.0", "2026.37.01", "2026-W37-5", "-x", "2026.37.0\nany=true"],
)
def test_bad_versions(version):
    with pytest.raises(ReleaseError, match="invalid app version"):
        app.version_key(version)


def test_detect_untagged_published_and_wrong_branch(app_repo: Config, outputs):
    version = app.materialize(app_repo, "", "Release")
    app.detect(app_repo, "main")
    assert outputs()["any"] == "true"
    git(app_repo.root, "tag", version)
    app.detect(app_repo, "main")
    assert outputs()["any"] == "false"
    with pytest.raises(ReleaseError, match="only deploy from main"):
        app.detect(app_repo, "feature")


def test_detect_empty_and_stale(app_repo: Config, outputs):
    app.detect(app_repo, "main")
    assert outputs()["any"] == "false"
    app.materialize(app_repo, "", "Old version")
    git(app_repo.root, "tag", "2026.37.99")
    with pytest.raises(ReleaseError, match="newer published"):
        app.detect(app_repo, "main")


@pytest.mark.parametrize(
    "text", ["## 2026.37.0\n\n## 2026.37.1\n", "## 2026.37.0\n\n## 2026.37.0\n"]
)
def test_changelog_must_be_ordered_and_unique(app_repo: Config, text):
    (app_repo.root / "CHANGELOG.md").write_text(text)
    with pytest.raises(ReleaseError, match="unique and ordered"):
        app.sections(app_repo)


def test_source_resolves_branch_tag_sha_and_commits_only_the_pin(
    app_repo: Config, tmp_path: Path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    (source / "app.txt").write_text("old")
    commit_all(source)
    old = git(source, "rev-parse", "HEAD").strip()
    git(source, "tag", "v1")
    git(
        app_repo.root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(source),
        "source",
    )
    pyproject = app_repo.root / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + 'source-submodule = "source"\n')
    commit_all(app_repo.root)
    config = load_config(app_repo.root)
    (source / "app.txt").write_text("new")
    commit_all(source)
    new = git(source, "rev-parse", "HEAD").strip()
    assert app.resolve_source(config) == new
    assert app.resolve_source(config, "v1") == old
    assert app.resolve_source(config, new) == new
    version = app.materialize(config, "v1", "Pin the known good revision")
    assert old in app.sections(config)[0][1]
    assert git(app_repo.root / "source", "rev-parse", "HEAD").strip() == old
    # An unrelated staged change must not sneak into the release commit.
    (app_repo.root / "unrelated.txt").write_text("private work")
    git(app_repo.root, "add", "unrelated.txt")
    calls = []
    monkeypatch.setattr(app, "gh_run", lambda args, cwd: calls.append(args))
    app.open_pr(config, version)
    assert calls[0][:2] == ["pr", "create"]
    assert calls[0][calls[0].index("--base") + 1] == "main"
    assert "unrelated.txt" not in git(
        app_repo.root, "show", "--format=", "--name-only", "HEAD"
    )
    assert "160000" in git(app_repo.root, "ls-tree", "HEAD", "source")
    assert not app.tag_exists(app_repo.root, version)


def test_finalize_reuses_release_tools_and_rejects_wrong_commit(
    app_repo: Config, monkeypatch
):
    version = app.materialize(app_repo, "", "Deploy now")
    commit_all(app_repo.root)
    called = []
    monkeypatch.setattr(app, "cmd_push_tag", lambda *args: called.append("tag"))
    monkeypatch.setattr(
        app, "cmd_create_release", lambda *args: called.append("release")
    )
    app.finalize(app_repo, version)
    assert called == ["tag", "release"]
    git(app_repo.root, "tag", version, "HEAD~1")
    with pytest.raises(ReleaseError, match="different commit"):
        app.finalize(app_repo, version)
    assert called == ["tag", "release"]


def test_dev_never_changes_changelog_or_tags(app_repo: Config, outputs):
    app.dev(app_repo)
    assert outputs()["version"].startswith("dev-")
    assert not (app_repo.root / "CHANGELOG.md").exists()
    assert not git(app_repo.root, "tag", "--list").strip()
    with pytest.raises(ReleaseError, match="requires app source-submodule"):
        app.resolve_source(app_repo, "main")


@pytest.mark.parametrize(
    "extra",
    [
        'source-submodule = "../outside"',
        'source-submodule = ".git"',
        'source-ref = "--upload-pack=bad"',
        'production-environment = "${{ inputs.bad }}"',
        'staging-environment = "production"',
        'dev-schedule = "* * * * *\\nfoo"',
        'typo = "value"',
    ],
)
def test_reject_unsafe_app_configuration(app_repo: Config, extra):
    path = app_repo.root / "pyproject.toml"
    # Replace the default cron when testing that setting.
    text = path.read_text()
    if extra.startswith("dev-schedule"):
        text = re.sub(r"dev-schedule = .*\n", "", text)
    path.write_text(text + extra + "\n")
    with pytest.raises(ReleaseError):
        load_config(app_repo.root)


def test_app_workflow_contracts_and_dependency_graph(app_repo: Config):
    sync(app_repo)
    sync(app_repo, check=True)
    workflows = {
        name: yaml.safe_load(render(name, app_repo))
        for name in managed_workflows(app_repo)
    }
    release = workflows["release_from_changelog.yml"]
    assert release["concurrency"]["queue"] == "max"
    assert release["concurrency"]["cancel-in-progress"] is False
    assert "tags" not in release[True]["push"]
    jobs = workflows["publish.yml"]["jobs"]
    assert jobs["production"]["needs"] == ["detect", "approval"]
    assert jobs["release"]["needs"] == ["detect", "production"]
    assert jobs["approval"]["environment"] == "production"
    assert jobs["build"]["with"]["source-revision"] == ""
    assert "workflow_dispatch" not in workflows["publish.yml"][True]
    assert "submodules" not in jobs["release"]["steps"][0]["with"]
    (app_repo.root / ".github/workflows/build.yml").write_text(
        "on:\n  workflow_call:\n"
    )
    with pytest.raises(ReleaseError, match="workflow_call inputs"):
        sync(app_repo, check=True)


@pytest.mark.parametrize(
    "setting",
    [
        "changelog-exempt-packages = []",
        'root-source-dirs = ["src"]',
        'package-source-subdirs = ["src"]',
        'dispatch-package-inputs = "text"',
        'prerelease-branch-prefix = "pre/"',
        'hotfix-branch-prefix = "hotfix/"',
    ],
)
def test_app_rejects_package_only_settings(app_repo: Config, setting):
    """App mode rejects settings that only affect package publishing."""
    path = app_repo.root / "pyproject.toml"
    path.write_text(
        path.read_text().replace(
            "[tool.reflex-release.app]", setting + "\n[tool.reflex-release.app]"
        )
    )
    with pytest.raises(ReleaseError, match="package"):
        load_config(app_repo.root)


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "", "/etc/passwd"])
def test_app_rejects_invalid_timezone_at_load(app_repo: Config, timezone):
    """Invalid timezones produce a configuration error before release allocation."""
    path = app_repo.root / "pyproject.toml"
    path.write_text(
        path.read_text().replace(
            "[tool.reflex-release.app]",
            f'release-timezone = "{timezone}"\n[tool.reflex-release.app]',
        )
    )
    with pytest.raises(ReleaseError, match="release-timezone"):
        load_config(app_repo.root)


@pytest.mark.parametrize(
    "field",
    [
        "type: boolean",
        "type: number",
        "description: missing type",
        "type: string\n        required: false",
        "type: boolean\n        required: true\n        description: |\n          type: string",
    ],
)
def test_app_rejects_invalid_hook_contract(app_repo: Config, field):
    """Hooks must declare the required string inputs the generated caller sends."""
    path = app_repo.root / ".github/workflows/build.yml"
    text = path.read_text().replace("type: string\n        required: true", field, 1)
    path.write_text(text)
    with pytest.raises(ReleaseError, match="required string"):
        sync(app_repo)


def test_app_checks_manual_changelog_headings(app_repo: Config):
    """Ordinary PRs cannot introduce a heading that triggers a deployment."""
    args = ["--root", str(app_repo.root), "check-headings", "--base-ref", "HEAD"]
    assert main(args) == 0
    path = app_repo.root / "CHANGELOG.md"
    path.write_text("## 2026.37.0\n\nRelease notes.\n")
    assert main(args) == 1
    commit_all(app_repo.root)
    path.write_text(path.read_text() + "Additional notes.\n")
    assert main(args) == 0


def test_app_changelog_workflow_guards_release_headings(app_repo: Config):
    """Generated PR checks enforce heading provenance with the bot exemption."""
    workflow = yaml.safe_load(render("changelog.yml", app_repo))
    steps = workflow["jobs"]["check"]["steps"]
    guard = next(
        step for step in steps if step.get("run", "").endswith(" check-headings")
    )
    assert "github-actions[bot]" in guard["if"]
    assert "startsWith(github.head_ref, 'release/')" in guard["if"]
    assert "version_edit" in guard["if"]
    assert workflow["permissions"]["pull-requests"] == "read"


def test_app_cli_materialize_and_detect(app_repo: Config, outputs):
    assert (
        main([
            "--root",
            str(app_repo.root),
            "app-materialize",
            "--reason",
            "CLI deploy",
        ])
        == 0
    )
    assert main(["--root", str(app_repo.root), "app-detect", "--ref-name", "main"]) == 0
    assert outputs()["any"] == "true"


def test_app_init_does_not_add_towncrier(app_repo: Config):
    assert main(["--root", str(app_repo.root), "init"]) == 0
    assert "towncrier" not in (app_repo.root / "pyproject.toml").read_text()
    assert not (app_repo.root / "news").exists()


def test_removing_dev_schedule_removes_only_generated_dev_workflow(app_repo: Config):
    sync(app_repo)
    path = app_repo.root / "pyproject.toml"
    path.write_text(re.sub(r"dev-schedule = .*\n", "", path.read_text()))
    config = load_config(app_repo.root)
    sync(config)
    assert not (app_repo.root / ".github/workflows/deploy_dev.yml").exists()
    assert (app_repo.root / ".github/workflows/build.yml").exists()
    assert (app_repo.root / ".github/workflows/deploy.yml").exists()
