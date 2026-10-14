"""Changelog-driven application deployments, independent of build infrastructure."""

from __future__ import annotations

import datetime as dt
import re
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from .actions import ReleaseError, fail, write_outputs, write_summary
from .commands import cmd_create_release, cmd_push_tag
from .config import AppConfig, Config
from .gitutil import (
    authenticated_git,
    commit_exists,
    configure_bot_identity,
    gh_run,
    git,
    git_push,
    git_run,
    git_show,
    tag_exists,
)

VERSION_RE = re.compile(
    r"(?P<year>[0-9]{4})\.(?P<week>[1-9]|[1-4][0-9]|5[0-3])\.(?P<serial>0|[1-9][0-9]*)"
)
HEADING_RE = re.compile(r"^## (?P<version>\S+)\s*$", re.MULTILINE)


def settings(config: Config) -> AppConfig:
    """Require application mode.

    Args:
        config: Repository configuration.

    Returns:
        Application settings.
    """
    if config.app is None:
        fail("this command requires [tool.reflex-release.app]")
    return config.app


def version_key(version: str) -> tuple[dt.date, int]:
    """Validate and order ISO-year.week.sequence release identifiers.

    Args:
        version: ISO week year and number with a release counter.

    Returns:
        The ISO week's Monday and release counter.
    """
    match = VERSION_RE.fullmatch(version)
    if match:
        try:
            return dt.date.fromisocalendar(
                int(match["year"]), int(match["week"]), 1
            ), int(match["serial"])
        except ValueError:
            pass
    message = f"invalid app version {version!r}; expected ISO-year.week.sequence, e.g. 2026.37.0"
    raise ReleaseError(message)


def sections(config: Config) -> list[tuple[str, str]]:
    """Read validated application release sections in file order.

    Args:
        config: Repository configuration.

    Returns:
        Version and notes pairs, newest first.
    """
    path = config.root / config.changelog_filename
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    headings = list(HEADING_RE.finditer(text))
    result = []
    previous = None
    for index, heading in enumerate(headings):
        version = heading["version"]
        key = version_key(version)
        if previous is not None and key >= previous:
            fail("app changelog versions must be unique and ordered newest first")
        previous = key
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        result.append((version, text[heading.end() : end].strip()))
    return result


def check_headings(config: Config, base_ref: str) -> None:
    """Reject newly added application release headings in ordinary pull requests.

    Args:
        config: Repository configuration.
        base_ref: The revision to compare the changelog against.
    """
    base_text = git_show(config.root, base_ref, config.changelog_filename) or ""
    known = {heading["version"] for heading in HEADING_RE.finditer(base_text)}
    added = [version for version, _ in sections(config) if version not in known]
    if added:
        fail(
            "new CHANGELOG.md version headings are deployment triggers and must be "
            "materialized by the Dispatch release workflow: " + ", ".join(added)
        )


def resolve_source(config: Config, revision: str = "") -> str:
    """Resolve and check out the requested upstream revision in the source submodule.

    Args:
        config: Repository configuration.
        revision: Branch, tag or SHA; empty uses the configured default.

    Returns:
        The resolved commit SHA, or empty for an app without a submodule.
    """
    app = settings(config)
    if not app.source_submodule:
        if revision:
            fail("a target revision requires app source-submodule")
        return ""
    entry = git(["ls-files", "--stage", "--", app.source_submodule], config.root)
    if not entry.startswith("160000 "):
        fail(f"{app.source_submodule} is not a tracked git submodule")
    revision = revision or app.source_ref
    if revision.startswith("-") or any(c.isspace() for c in revision):
        fail("target revision must be a git branch, tag or SHA")
    authenticated_git(
        ["submodule", "update", "--init", "--", app.source_submodule], config.root
    )
    source = config.root / app.source_submodule
    fetch = ["fetch", "--tags", "--prune"]
    if git(["rev-parse", "--is-shallow-repository"], source).strip() == "true":
        fetch.append("--unshallow")
    authenticated_git([*fetch, "origin", "+refs/heads/*:refs/remotes/origin/*"], source)
    branch = revision.removeprefix("origin/").removeprefix("refs/heads/")
    candidates = [f"refs/remotes/origin/{branch}", f"refs/tags/{revision}", revision]
    resolved = next(
        (candidate for candidate in candidates if commit_exists(source, candidate)),
        None,
    )
    if resolved is None:
        # A full SHA need not be reachable from any advertised branch or tag.
        authenticated_git(["fetch", "origin", revision], source)
        resolved = "FETCH_HEAD"
    sha = git(["rev-parse", "--verify", f"{resolved}^{{commit}}"], source).strip()
    git_run(["checkout", "--detach", sha], source)
    authenticated_git(["submodule", "update", "--init", "--recursive"], source)
    return sha


def materialize(config: Config, revision: str, reason: str) -> str:
    """Pin source and prepend the next deployment's changelog section.

    Args:
        config: Repository configuration.
        revision: Requested source revision, or empty for the configured default.
        reason: Operator's deployment reason.

    Returns:
        The allocated version.
    """
    app = settings(config)
    existing = sections(config)
    today = dt.datetime.now(ZoneInfo(config.release_timezone)).date()
    # Read remote reservations as well as tags: two PRs dispatched before either
    # merges must not allocate the same version. The dispatch workflow queues.
    branches = authenticated_git(
        [
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{config.release_branch_prefix}*",
        ],
        config.root,
    )
    reserved = {
        line.split()[1].removeprefix(f"refs/heads/{config.release_branch_prefix}")
        for line in branches.splitlines()
    }
    reserved.update(version for version, _ in existing)
    reserved.update(git(["tag", "--list"], config.root).splitlines())
    keys = [version_key(value) for value in reserved if VERSION_RE.fullmatch(value)]
    monday = today - dt.timedelta(days=today.weekday())
    date = max([monday, *(key[0] for key in keys)])
    count = max((key[1] for key in keys if key[0] == date), default=-1) + 1
    year, week, _ = date.isocalendar()
    version = f"{year}.{week}.{count}"
    # Indent continuation lines so a reason cannot create another version heading.
    reason = reason.strip() or "Deploy the current application source."
    notes = "- " + reason.replace("\n", "\n  ")
    source_sha = resolve_source(config, revision)
    if source_sha:
        notes += f"\n- Source `{app.source_submodule}`: `{source_sha}`."
    path = config.root / config.changelog_filename
    text = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n"
    first = HEADING_RE.search(text)
    split = first.start() if first else len(text)
    path.write_text(
        text[:split].rstrip() + f"\n\n## {version}\n\n{notes}\n\n" + text[split:],
        encoding="utf-8",
    )
    write_outputs(version=version, source_revision=source_sha)
    return version


def open_pr(config: Config, version: str) -> None:
    """Commit the materialized source pin and open a release PR against main.

    Args:
        config: Repository configuration.
        version: The newly materialized release identifier.
    """
    app = settings(config)
    releases = sections(config)
    if not releases or releases[0][0] != version:
        fail("the requested version must be the top changelog section")
    branch = f"{config.release_branch_prefix}{version}"
    configure_bot_identity(config.root)
    git_run(["checkout", "-b", branch], config.root)
    paths = [config.changelog_filename]
    if app.source_submodule:
        paths.append(app.source_submodule)
    git_run(["add", "--", *paths], config.root)
    git_run(["commit", "-m", f"Release {version}", "--", *paths], config.root)
    git_push(f"HEAD:refs/heads/{branch}", config.root)
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / "release.md"
        body.write_text(
            f"Release {version}\n\n{releases[0][1]}\n\n"
            "Merging builds this commit and deploys to staging. Production requires "
            "environment approval; the tag and GitHub release follow a successful production deploy.\n",
            encoding="utf-8",
        )
        gh_run(
            [
                "pr",
                "create",
                "--base",
                config.main_branch,
                "--head",
                branch,
                "--title",
                f"Release {version}",
                "--body-file",
                str(body),
            ],
            config.root,
        )
    # GITHUB_TOKEN-created PRs do not trigger pull_request workflows.
    gh_run(["workflow", "run", "changelog.yml", "--ref", branch], config.root)
    write_summary([
        f"Opened release PR for **{version}** against `{config.main_branch}`."
    ])


def detect(config: Config, ref_name: str) -> None:
    """Emit the top untagged version, refusing stale or unauthorized deployments.

    Args:
        config: Repository configuration.
        ref_name: Branch on which the workflow is running.
    """
    settings(config)
    if ref_name != config.main_branch:
        fail(f"app releases may only deploy from {config.main_branch}")
    releases = sections(config)
    version = releases[0][0] if releases else ""
    skip = not version or tag_exists(config.root, version)
    if not skip:
        published = [
            value
            for value in git(["tag", "--list"], config.root).splitlines()
            if VERSION_RE.fullmatch(value)
        ]
        if any(version_key(value) > version_key(version) for value in published):
            fail(f"refusing to deploy {version} over a newer published app version")
    write_outputs(
        version=version,
        any="false" if skip else "true",
        ref=git(["rev-parse", "HEAD"], config.root).strip(),
    )


def dev(config: Config) -> None:
    """Resolve speculative source without committing or allocating a release.

    Args:
        config: Repository configuration.
    """
    sha = resolve_source(config)
    ref = git(["rev-parse", "HEAD"], config.root).strip()
    write_outputs(
        ref=ref,
        source_revision=sha,
        version=f"dev-{ref[:12]}" + (f"-{sha[:12]}" if sha else ""),
    )


def finalize(config: Config, version: str) -> None:
    """Tag a successfully deployed checkout and reuse GitHub release creation.

    Args:
        config: Repository configuration.
        version: The version that the production hook successfully deployed.
    """
    settings(config)
    releases = sections(config)
    if not releases or releases[0][0] != version:
        fail("deployed version must match the checkout's top changelog section")
    if tag_exists(config.root, version) and git(
        ["rev-parse", f"refs/tags/{version}^{{commit}}"], config.root
    ) != git(["rev-parse", "HEAD"], config.root):
        fail(f"{version} already tags a different commit")
    cmd_push_tag(config, version)
    with tempfile.TemporaryDirectory() as directory:
        notes = Path(directory) / "notes.md"
        notes.write_text(releases[0][1] + "\n", encoding="utf-8")
        cmd_create_release(
            config,
            version,
            "",
            version,
            False,
            True,
            notes,
            Path(directory) / "checksums",
        )
