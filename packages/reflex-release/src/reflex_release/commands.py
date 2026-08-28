"""Implementations of the ``reflex-release`` subcommands.

Every command is a plain function over a :class:`~reflex_release.config.Config`
and its explicit inputs, so the whole pipeline is exercisable outside GitHub
Actions. Failures raise :class:`~reflex_release.actions.ReleaseError`, which the
CLI turns into a non-zero exit.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from packaging.version import InvalidVersion, Version

from .actions import (
    echo,
    error,
    fail,
    link,
    notice,
    repo_url,
    write_outputs,
    write_summary,
)
from .changelog import (
    collapse_prereleases,
    extract_notes,
    latest_version,
    parse_sections,
)
from .config import POST_RELEASE_INPUTS, POST_RELEASE_WORKFLOW_KEY, Config, is_final
from .devpins import (
    LOCK_FILE,
    blocker_advice,
    blocking_pins,
    describe_blockers,
    upgrade_dev_pins,
)
from .discovery import (
    alpha_train_packages,
    associate_orphan_fragments,
    build_changelog,
    category_order,
    changelog_packages,
    current_version,
    fragment_types,
    pending_fragment_packages,
    releasable_packages,
    run_towncrier,
    title_format,
)
from .dist import pin_exact, verify_dist
from .gitutil import (
    changed_files,
    commit_exists,
    configure_bot_identity,
    gh_capture,
    gh_output,
    gh_run,
    git,
    git_push,
    git_run,
    git_show,
    latest_final_tag_version,
    latest_tag_version,
    remote_branch_exists,
    tag_exists,
)
from .versions import ACTIONS, FINAL_ACTIONS, next_version, release_date_today

#: Filename of the scaffolded workflow that publishes untagged changelog versions.
RELEASE_WORKFLOW = "release_from_changelog.yml"

#: Label applied to release pull requests so the fragment check skips them.
SKIP_CHANGELOG_LABEL = "skip-changelog"

_PACKAGE_SELECTION_SPLIT = re.compile(r"[\s,]+")

#: The release fields read back after a release is created (or found already
#: created), to prove the thing ``post-release`` is about to be pointed at is
#: the release this run published. Asked for and read from one place, so a
#: field can never be verified without having been requested.
_RELEASE_FIELDS = ("tagName", "name", "isDraft", "isPrerelease", "assets")

#: Markers in gh's stderr for a release that is not there. Matched widely — a
#: bare 404 counts — because a phrasing this list misses would stop every
#: ordinary release; what makes the wide match safe is that a not-found is
#: only believed once the repository itself has been read (see
#: :func:`_reads_as_absent`).
_NO_RELEASE_STDERR = ("release not found", "404")


def _is_null_sha(sha: str) -> bool:
    """Return whether a git sha is the all-zero "no such commit" placeholder.

    Args:
        sha: The sha to inspect.

    Returns:
        True for the value a push event reports as ``before`` when it created
        the branch.
    """
    return bool(sha) and set(sha) == {"0"}


def _split_selection(raw: str) -> list[str]:
    """Split a free-form package selection into package names.

    Args:
        raw: A comma- or whitespace-separated list of package names.

    Returns:
        The names, deduplicated, in the order given.
    """
    names = [name for name in _PACKAGE_SELECTION_SPLIT.split(raw.strip()) if name]
    return list(dict.fromkeys(names))


def _summary_table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Render a markdown table.

    Args:
        header: The column titles.
        rows: The cell values per row.

    Returns:
        The markdown lines.
    """
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _branch_url(branch: str) -> str:
    """Return the web URL of a branch in the current repository.

    Args:
        branch: The branch name.

    Returns:
        The URL, or an empty string outside GitHub Actions.
    """
    base = repo_url()
    return f"{base}/tree/{quote(branch)}" if base else ""


def _workflow_runs_url(workflow: str, branch: str) -> str:
    """Return the URL listing a workflow's runs on one branch.

    Args:
        workflow: The workflow filename.
        branch: The branch to filter the runs by.

    Returns:
        The URL, or an empty string outside GitHub Actions.
    """
    base = repo_url()
    if not base:
        return ""
    query = quote(f"branch:{branch}", safe="")
    return f"{base}/actions/workflows/{workflow}?query={query}"


def _lockstep_errors(config: Config, due: dict[str, str]) -> list[str]:
    """Verify the lockstep invariant for a release batch.

    Every lockstep partner of a due package must either be due at the identical
    version in the same batch or already carry the tag for that version (the
    retry case where one half published earlier).

    Args:
        config: The repository configuration.
        due: Mapping of due package name to version string.

    Returns:
        A list of human-readable violations (empty when the batch is sound).
    """
    errors: list[str] = []
    for package, version in due.items():
        for partner in config.lockstep_partners(package):
            partner_tag = config.tag_for(partner, version)
            if due.get(partner) != version and not tag_exists(config.root, partner_tag):
                errors.append(
                    f"{package} v{version} is due but its lockstep partner {partner} "
                    f"is neither due at v{version} nor already tagged {partner_tag}; "
                    "publishing would break their exact pin. Re-run the Dispatch "
                    "release workflow: selecting either member materializes the "
                    "whole group, writing an empty changelog entry for members "
                    "that have no news fragments."
                )
    return errors


def cmd_detect(config: Config, ref_name: str) -> None:
    """Detect packages whose newest changelog version has no git tag.

    Writes to ``$GITHUB_OUTPUT``: ``packages`` (JSON array of
    ``{package, version, tag}``), ``any``, and the same pair as
    ``last_packages`` / ``any_last`` for packages that must publish after their
    lockstep siblings.

    Args:
        config: The repository configuration.
        ref_name: The branch being checked (``github.ref_name``).
    """
    releases: list[dict[str, str]] = []
    rows: list[list[str]] = []
    for package in changelog_packages(config):
        version = latest_version(
            config.changelog_path(package).read_text(encoding="utf-8")
        )
        if version is None:
            rows.append([f"`{package}`", "`<none>`", "no versioned section"])
            continue
        tag = config.tag_for(package, str(version))
        if tag_exists(config.root, tag):
            rows.append([f"`{package}`", f"`{version}`", f"already tagged `{tag}`"])
            continue
        if not config.branch_allows_publish(version, ref_name):
            kind = "final" if is_final(version) else "prerelease"
            notice(
                f"{package} v{version} is a {kind} version but branch "
                f"'{ref_name}' cannot publish {kind}s (only "
                f"{config.allowed_branches(version)} can); skipping."
            )
            rows.append([f"`{package}`", f"`{version}`", "skipped: branch rule"])
            continue
        releases.append({"package": package, "version": str(version), "tag": tag})
        rows.append([f"`{package}`", f"`{version}`", f"**will publish** `{tag}`"])

    due = {release["package"]: release["version"] for release in releases}
    errors = _lockstep_errors(config, due)

    first = [r for r in releases if not config.publishes_last(r["package"])]
    last = [r for r in releases if config.publishes_last(r["package"])]

    write_summary([
        "## Changelog release check",
        "",
        f"Branch: `{ref_name}`",
        "",
        *_summary_table(["Package", "Newest changelog version", "Status"], rows),
    ])
    write_outputs(
        packages=json.dumps(first),
        any="true" if first else "false",
        last_packages=json.dumps(last),
        any_last="true" if last else "false",
    )
    if errors:
        for message in errors:
            error(message)
        fail("lockstep invariant violated; no package was published")


def _drop_unpublishable_pins(
    config: Config, packages: list[str], action: str, explicit: bool
) -> tuple[list[str], list[str]]:
    """Hold back packages whose dependency pins no published version satisfies.

    Materialization lifts a ``*.dev`` (and, for a final version, a prerelease)
    dependency floor to the earliest published version that satisfies it. A
    floor nothing published satisfies has nowhere to go, so the package is not
    releasable yet — releasing it would either publish an uninstallable pin or
    stop at the publish-time gate with the changelog already bumped.

    A lockstep group is held back whole: its members only ever release together.

    Args:
        config: The repository configuration.
        packages: The selected packages, lockstep groups already expanded.
        action: The release action being planned.
        explicit: Whether the selection was made by hand. An explicit selection
            that cannot be released is an error; an auto-selected package is
            simply left out of the batch.

    Returns:
        The releasable packages and the human-readable reasons the others were
        held back.
    """
    blocked = blocking_pins(
        config, packages, allow_prereleases=action not in FINAL_ACTIONS
    )
    if not blocked:
        return packages, []

    reasons = describe_blockers(blocked)
    if explicit:
        listing = "\n".join(f"  {line}" for line in reasons)
        fail(
            "the selected package(s) declare dependency pins that no published "
            f"version satisfies:\n{listing}\n\n{blocker_advice(blocked)}"
        )

    held = {
        member
        for package in blocked
        for member in (package, *config.lockstep_partners(package))
    }
    for line in reasons:
        notice(f"held back from this release — {line}")
    remaining = [package for package in packages if package not in held]
    if not remaining:
        fail(
            "every auto-selected package declares a dependency pin that no "
            "published version satisfies:\n"
            + "\n".join(f"  {line}" for line in reasons)
        )
    return remaining, reasons


def cmd_plan(config: Config, action: str, selection: str) -> None:
    """Plan the next version for each selected package.

    Writes ``releases`` (JSON array of ``{package, current, next, tag}``) to
    ``$GITHUB_OUTPUT``. An empty selection auto-detects the packages to release:
    those with pending news fragments — or, for ``release-from-prerelease``,
    those whose changelog is topped by an alpha (their fragments are already
    consumed). A package whose dependency pins no published version satisfies is
    not eligible either way (see :func:`_drop_unpublishable_pins`).

    Args:
        config: The repository configuration.
        action: One of the keys in :data:`~reflex_release.versions.ACTIONS`.
        selection: Free-form package selection; empty auto-detects.
    """
    if action not in ACTIONS:
        fail(f"unknown action {action!r}; choose from {', '.join(ACTIONS)}")

    packages = _split_selection(selection)
    for package in packages:
        config.require_known(package)
        if config.is_internal(package):
            fail(
                f"{package} is an internal package: it releases by patch-bumping "
                "its newest tag, not from a changelog"
            )
        if config.is_never_published(package):
            fail(
                f"{package} is listed in never-publish-packages: this repository "
                "builds it but does not release it"
            )

    how = "explicit"
    if not packages:
        if action == "release-from-prerelease":
            packages = alpha_train_packages(config)
            how, source = "auto: alpha-topped changelogs", "an alpha-topped changelog"
        else:
            packages = pending_fragment_packages(config)
            how, source = "auto: pending news fragments", "pending news fragments"
        if not packages:
            fail(f"no packages selected and no package has {source}")
        notice(f"no packages selected; auto-detected {', '.join(packages)}")

    # Lockstep members always release together at the same version, so selecting
    # one selects the whole group and the group shares a single baseline.
    for package in list(packages):
        packages.extend(
            partner
            for partner in config.lockstep_partners(package)
            if partner not in packages
        )

    packages, disqualified = _drop_unpublishable_pins(
        config, packages, action, explicit=how == "explicit"
    )

    releases: list[dict[str, str]] = []
    for package in packages:
        group = config.lockstep_group(package)
        members = group.members if group is not None else (package,)
        baselines = [current_version(config, member) for member in members]
        known = [version for version in baselines if version is not None]
        current = max(known) if known else None
        planned = next_version(current, action, package)
        tag = config.tag_for(package, planned)
        if tag_exists(config.root, tag):
            fail(f"tag {tag} already exists")
        own = current_version(config, package)
        releases.append({
            "package": package,
            "current": str(own) if own is not None else "",
            "next": planned,
            "tag": tag,
        })

    write_summary([
        "## Release plan",
        "",
        f"Action: `{action}`  ",
        f"Selection: `{how}`",
        "",
        *_summary_table(
            ["Package", "Current", "Next", "Tag"],
            [
                [
                    f"`{r['package']}`",
                    f"`{r['current'] or '<none>'}`",
                    f"`{r['next']}`",
                    f"`{r['tag']}`",
                ]
                for r in releases
            ],
        ),
        *(
            [
                "",
                "### Held back",
                "",
                *(f"- {line}" for line in disqualified),
            ]
            if disqualified
            else []
        ),
    ])
    write_outputs(releases=json.dumps(releases))


def cmd_materialize(config: Config, action: str, releases_json: str) -> None:
    """Write the planned versions into the changelogs via towncrier.

    Also lifts every dependency pin the release cannot ship — a ``*.dev`` floor,
    or a prerelease floor when the release is final — to the earliest published
    version that satisfies it, and re-locks the repository, so the release
    carries pins that resolve instead of failing the publish-time gate.

    Orphan fragments are first named after the pull request that added them, so
    the entries towncrier writes carry a link. For ``release-from-prerelease``,
    collapses the alpha sections of each changelog into the single final-version
    section after building it.

    Writes ``repinned`` (a JSON array of the paths the pin upgrade rewrote) to
    ``$GITHUB_OUTPUT``, which is what the delivery step stages beside the
    changelogs — it runs as a separate process and cannot otherwise know.

    Args:
        config: The repository configuration.
        action: The release action the plan was made for.
        releases_json: The ``releases`` JSON emitted by :func:`cmd_plan`.
    """
    releases: list[dict[str, str]] = json.loads(releases_json)
    if not releases:
        fail("nothing to materialize: the release plan is empty")

    # Before towncrier: a pin that cannot be lifted stops the release while the
    # news fragments it would have consumed are still on disk.
    repinned = upgrade_dev_pins(
        config,
        [release["package"] for release in releases],
        allow_prereleases=action not in FINAL_ACTIONS,
    )
    write_outputs(repinned=json.dumps(repinned))
    if repinned:
        write_summary([
            "## Dependency pins lifted",
            "",
            *(f"- `{path}`" for path in repinned),
        ])

    collapse = action == "release-from-prerelease"
    categories = category_order(config) if collapse else []
    heading_format = title_format(config)
    today = release_date_today(config.release_timezone)

    for release in releases:
        package, version = release["package"], release["next"]
        for old_name, new_name in associate_orphan_fragments(config, package):
            echo(f"{package}: renamed news fragment {old_name} -> {new_name}")
        build_changelog(config, package, version, today)
        if collapse:
            path = config.changelog_path(package)
            path.write_text(
                collapse_prereleases(
                    path.read_text(encoding="utf-8"),
                    Version(version),
                    today,
                    categories,
                    heading_format,
                ),
                encoding="utf-8",
            )


def cmd_prepare_publish(
    config: Config, package: str, raw_version: str, ref_name: str
) -> None:
    """Validate a (package, version) pair for publishing and emit build metadata.

    Enforces the changelog as source of truth (the version must be the newest
    changelog version when the package has a changelog), the branch rules, the
    lockstep invariant, and detects already-published (tagged) versions. An
    empty version is only valid for internal packages and patch-bumps the newest
    tag; it is computed here, inside the per-package publish concurrency group,
    so back-to-back publishes cannot compute the same version.

    Args:
        config: The repository configuration.
        package: The package to publish.
        raw_version: The requested version, or empty to auto patch-bump.
        ref_name: The branch being published from.
    """
    config.require_known(package)
    # Checked before anything else: this is the last gate a manual dispatch of
    # the publish workflow passes through, and the only one for a package no
    # release selection would ever have offered.
    if config.is_never_published(package):
        fail(
            f"{package} is listed in never-publish-packages: this repository "
            "builds it but does not release it"
        )
    raw_version = raw_version.strip().removeprefix("v")
    path = config.changelog_path(package)

    if raw_version:
        try:
            version = Version(raw_version)
        except InvalidVersion:
            fail(f"invalid version {raw_version!r}")
        if version.epoch or version.local or version.is_devrelease:
            fail(f"refusing to publish epoch/local/dev version {version}")
    elif not config.is_internal(package):
        fail(
            f"a target version is required for {package}: its changelog is the "
            "source of truth (materialize it via the Dispatch release workflow). "
            "Only packages listed in internal-packages auto patch-bump."
        )
    else:
        newest_tag = latest_tag_version(config, package)
        version = (
            Version(f"{newest_tag.major}.{newest_tag.minor}.{newest_tag.micro + 1}")
            if newest_tag is not None
            else Version("0.0.1")
        )
        notice(f"no version given; auto patch-bump for {package}: {version}")

    if not config.branch_allows_publish(version, ref_name):
        fail(
            f"version {version} can only be published from "
            f"{config.allowed_branches(version)}, not {ref_name!r}"
        )

    if path.is_file():
        newest = latest_version(path.read_text(encoding="utf-8"))
        if newest != version:
            fail(
                "changelog is the source of truth: newest version in "
                f"{path.relative_to(config.root)} is "
                f"{newest if newest is not None else '<none>'}, not {version}. "
                "Materialize the changelog first (Dispatch release workflow)."
            )
    else:
        notice(f"{package} has no CHANGELOG.md; skipping changelog check.")

    for partner in config.lockstep_partners(package):
        if tag_exists(config.root, config.tag_for(partner, str(version))):
            continue
        partner_path = config.changelog_path(partner)
        partner_newest = (
            latest_version(partner_path.read_text(encoding="utf-8"))
            if partner_path.is_file()
            else None
        )
        if partner_newest != version:
            fail(
                f"{package} v{version} releases in lockstep with {partner}, but "
                f"{partner} is neither tagged at v{version} nor materialized at it "
                f"(its newest changelog version is "
                f"{partner_newest if partner_newest is not None else '<none>'})."
            )

    tag = config.tag_for(package, str(version))
    skipped = tag_exists(config.root, tag)
    if skipped:
        notice(f"tag {tag} already exists; nothing to publish.")

    # Only mark the GitHub release "Latest" when this is genuinely the newest
    # final version of the flagship package — a hotfix of an older line must not
    # steal the badge from a newer release.
    latest_package = config.latest_release_package
    newest_final = (
        latest_final_tag_version(config, latest_package)
        if latest_package is not None
        else None
    )
    mark_latest = (
        package == latest_package
        and is_final(version)
        and (newest_final is None or version >= newest_final)
    )

    write_summary([
        "## Publish",
        "",
        f"Package: `{package}`  ",
        f"Version: `{version}`  ",
        f"Tag: `{tag}`  ",
        f"Status: {'skipped (already tagged)' if skipped else 'publishing'}",
    ])
    write_outputs(
        package=package,
        version=str(version),
        tag=tag,
        build_dir=config.package_dir(package),
        prerelease="true" if version.is_prerelease else "false",
        mark_latest="true" if mark_latest else "false",
        skipped="true" if skipped else "false",
    )


def cmd_pin_lockstep(config: Config, package: str, version: str) -> None:
    """Pin a package's lockstep siblings to the exact release version.

    Lockstep packages release together at one version, so the sibling that
    publishes last must ship metadata depending on exactly the versions
    published alongside it rather than on a floor.

    Args:
        config: The repository configuration.
        package: The package being built.
        version: The version being released.
    """
    config.require_known(package)
    targets = config.exact_pin_targets(package)
    if not targets:
        echo(f"{package} has no exact-pin lockstep siblings; nothing to do.")
        return
    pyproject = config.package_path(package) / "pyproject.toml"
    for target in targets:
        pin_exact(pyproject, config.distribution_name(target), Version(version))


def cmd_verify_dist(config: Config, package: str, version: str, dist_dir: str) -> None:
    """Verify every built artifact is this package at exactly the target version.

    Args:
        config: The repository configuration.
        package: The package being released.
        version: The version being released.
        dist_dir: The artifact directory, relative to the repository root.
    """
    config.require_known(package)
    distribution = config.distribution_name(package)
    count = verify_dist(
        config.root / dist_dir,
        distribution,
        Version(version),
        config.expect_artifacts(package),
    )
    echo(f"{count} artifact(s) of {distribution} at version {version}")


def cmd_extract_notes(
    config: Config, package: str, version: str, notes_path: Path
) -> None:
    """Write the changelog section for a version to a file.

    Falls back to a generic one-liner when the package has no changelog section
    for the version.

    Args:
        config: The repository configuration.
        package: The package being released.
        version: The version being released.
        notes_path: Where to write the release notes.
    """
    config.require_known(package)
    parsed = Version(version.removeprefix("v"))
    notes: str | None = None
    path = config.changelog_path(package)
    if path.is_file():
        notes = extract_notes(path.read_text(encoding="utf-8"), parsed)
    notes_path.write_text(
        (notes or f"Release of {package} {parsed}.") + "\n", encoding="utf-8"
    )


def cmd_check_headings(config: Config, base_ref: str) -> None:
    """Fail when the working tree adds changelog version headings vs a base ref.

    A merged version heading without a git tag is a real publish trigger, so new
    headings must come from the Dispatch release workflow. The guard uses the
    same parser the release pipeline publishes from, so the two cannot disagree.

    Args:
        config: The repository configuration.
        base_ref: The ref to compare against (e.g. ``origin/main``).
    """
    errors: list[str] = []
    for package in changelog_packages(config):
        path = config.changelog_path(package)
        rel_path = path.relative_to(config.root).as_posix()
        base_text = git_show(config.root, base_ref, rel_path) or ""
        known = {
            section.version
            for section in parse_sections(base_text)[1]
            if section.version is not None
        }
        errors.extend(
            f"{rel_path}: adds version heading '## {section.label}' (v{section.version})"
            for section in parse_sections(path.read_text(encoding="utf-8"))[1]
            if section.version is not None and section.version not in known
        )
    if errors:
        for message in errors:
            error(message)
        fail(
            "new CHANGELOG.md version headings are publish triggers and must be "
            "materialized by the Dispatch release workflow. If this is deliberate "
            "restructuring of already-published sections, apply the "
            "'changelog-version-edit' label."
        )
    echo("No new changelog version headings.")


def affected_packages(config: Config, paths: list[str]) -> list[str]:
    """List the packages whose source is touched by a set of changed paths.

    Args:
        config: The repository configuration.
        paths: Repo-relative changed paths.

    Returns:
        The affected packages that require news fragments.
    """
    return [
        package
        for package in config.all_packages()
        if config.requires_fragments(package)
        and any(config.is_package_source(package, path) for path in paths)
    ]


def cmd_changelog_check(config: Config, base_ref: str) -> None:
    """Require a news fragment for every package whose source a branch changes.

    Args:
        config: The repository configuration.
        base_ref: The ref the branch is compared against (e.g. ``origin/main``).
    """
    affected = affected_packages(config, changed_files(config.root, base_ref))
    if not affected:
        echo("No packaged source changes; no changelog fragments required.")
        return

    missing: list[str] = []
    for package in affected:
        echo(f"::group::towncrier check ({package})")
        failed = run_towncrier(
            config,
            [
                "check",
                "--config",
                "pyproject.toml",
                "--dir",
                config.package_dir(package),
                "--compare-with",
                base_ref,
            ],
            check=False,
        )
        echo("::endgroup::")
        if failed:
            missing.append(package)

    if missing:
        news_dir = config.news_dir(missing[0]).relative_to(config.root).as_posix()
        fail(
            f"no news fragment for: {', '.join(missing)}\n"
            f"Add {news_dir}/<pr-number>.<type>.md, where <type> is one of: "
            f"{', '.join(sorted(fragment_types(config)))}\n"
            f"Or apply the '{SKIP_CHANGELOG_LABEL}' label if the change is genuinely "
            "not user-facing."
        )
    echo(f"News fragments present for: {', '.join(affected)}")


def cmd_detect_internal(config: Config, base: str, head: str, package: str) -> None:
    """Detect internal packages to auto-release, or echo an explicit selection.

    Writes ``packages`` (a JSON array) to ``$GITHUB_OUTPUT``.

    Args:
        config: The repository configuration.
        base: The commit to diff from. The push event's ``before`` sha covers
            the whole push; it is unusable for a branch's first push (all
            zeros) or when the commit is not reachable, and falls back to the
            previous commit.
        head: The commit to diff to.
        package: An explicitly dispatched package, or empty to diff.
    """
    if package:
        config.require_known(package)
        if not config.is_internal(package):
            fail(f"{package} is not listed in internal-packages")
        write_outputs(packages=json.dumps([package]))
        return

    if _is_null_sha(base):
        # A branch's first push reports an all-zero base: every file in it is
        # new, and the paths filter matched against exactly that.
        notice("push created the branch; treating every tracked file as changed")
        changed = git(["ls-tree", "-r", "--name-only", head], config.root).splitlines()
    else:
        if not commit_exists(config.root, base):
            notice(
                f"push base {base!r} is unavailable; diffing the last commit instead"
            )
            base = f"{head}~1"
        changed = git(["diff", "--name-only", base, head], config.root).splitlines()

    # Source paths, not the package directory: the root package's prefix is
    # empty, so a bare startswith would match a push that only touched a
    # sibling. This is the same rule the generated paths filter triggers on.
    selected = [
        name
        for name in config.internal_packages
        if any(config.is_package_source(name, path) for path in changed)
    ]
    write_outputs(packages=json.dumps(selected))


def cmd_create(config: Config, package: str, name: str) -> None:
    """Create a news fragment for a package.

    Args:
        config: The repository configuration.
        package: The package the fragment belongs to.
        name: The fragment filename (``1234.feature.md``).
    """
    config.require_known(package)
    config.news_dir(package).mkdir(parents=True, exist_ok=True)
    run_towncrier(
        config,
        [
            "create",
            "--config",
            "pyproject.toml",
            "--dir",
            config.package_dir(package),
            name,
        ],
    )


def _release_summary(releases: list[dict[str, str]]) -> str:
    """Render a one-line ``pkg@version`` summary of a release plan.

    Args:
        releases: The planned releases.

    Returns:
        The comma-separated summary.
    """
    return ", ".join(f"{r['package']}@{r['next']}" for r in releases)


def _repinned_paths(repinned_json: str) -> list[str]:
    """Parse the ``repinned`` output of :func:`cmd_materialize`.

    Args:
        repinned_json: The JSON array of rewritten paths, or an empty string
            when the pin upgrade rewrote nothing.

    Returns:
        The repo-relative paths.
    """
    return json.loads(repinned_json) if repinned_json.strip() else []


def _commit_materialized(
    config: Config,
    releases: list[dict[str, str]],
    repinned: list[str],
    message: str,
) -> None:
    """Stage and commit everything materialization wrote for a release.

    Args:
        config: The repository configuration.
        releases: The releases that were materialized.
        repinned: The paths the pin upgrade rewrote, from :func:`cmd_materialize`.
        message: The commit message.
    """
    configure_bot_identity(config.root)
    # Exactly what materialization wrote: the changelogs of the packages being
    # released, and the files the pin upgrade reported rewriting. Nothing else
    # in the worktree can ride along in the release commit — a package's
    # pyproject.toml is staged only when a pin in it actually moved. towncrier
    # has already staged the deletion of every fragment it consumed.
    changelogs = [
        path.relative_to(config.root).as_posix()
        for path in (config.changelog_path(r["package"]) for r in releases)
        if path.is_file()
    ]
    if not changelogs:
        fail("materialization produced no changelog; nothing to release")
    git_run(["add", "--", *changelogs, *repinned], config.root)
    if not git(["diff", "--cached", "--name-only"], config.root).strip():
        fail("materialization produced no changes; nothing to release")

    # A lifted pin that does not reach the commit is the failure this whole
    # feature exists to remove, arriving later and with more to unwind: the
    # branch would go out with the old pin and die at the publish-time gate. It
    # happens when the workflow predates the `repinned` output, so name that.
    owned = {
        LOCK_FILE,
        *(f"{config.path_prefix(r['package'])}pyproject.toml" for r in releases),
    }
    if stranded := sorted(
        owned.intersection(git(["diff", "--name-only"], config.root).split())
    ):
        fail(
            f"materialization left {', '.join(stranded)} modified but unstaged. "
            "If the scaffolded workflow predates the `repinned` output of "
            "`materialize`, re-run `reflex-release sync` and dispatch again; "
            "otherwise the working tree holds changes materialization did not "
            "make, and a release must not carry them."
        )
    git_run(["commit", "-m", message], config.root)


def cmd_open_release_pr(
    config: Config,
    action: str,
    ref_name: str,
    releases_json: str,
    repinned_json: str,
) -> None:
    """Commit the materialized changelogs and open the release pull request.

    Args:
        config: The repository configuration.
        action: The release action that was materialized.
        ref_name: The branch the workflow was dispatched on.
        releases_json: The ``releases`` JSON emitted by :func:`cmd_plan`.
        repinned_json: The ``repinned`` JSON emitted by :func:`cmd_materialize`.
    """
    releases: list[dict[str, str]] = json.loads(releases_json)
    repinned = _repinned_paths(repinned_json)
    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    # Final versions publish from the main branch — except hotfix trains, which
    # publish directly from their own branch, so the PR targets it instead.
    base = (
        ref_name
        if ref_name.startswith(config.hotfix_branch_prefix)
        else config.main_branch
    )
    branch = f"{config.release_branch_prefix}{action}-{run_id}"
    summary = _release_summary(releases)

    body = "\n".join([
        (
            f"Materialized changelogs for release action `{action}` "
            f"(dispatched on `{ref_name}`)."
        ),
        "",
        *_summary_table(
            ["Package", "Current", "Next", "Tag"],
            [
                [
                    f"`{r['package']}`",
                    f"`{r['current'] or '<none>'}`",
                    f"`{r['next']}`",
                    f"`{r['tag']}`",
                ]
                for r in releases
            ],
        ),
        "",
        f"Merging this PR lands the versions above for release: the push to `{base}`",
        f"triggers the `{RELEASE_WORKFLOW}` workflow, which builds each package and",
        "then waits for `pypi` environment approval before uploading; the tag and",
        "GitHub release are created only after a successful upload. If a publish",
        "fails, fix the problem on top of the changelog bump — the next push retries",
        "automatically.",
        "",
    ])
    body_file = Path(os.environ.get("RUNNER_TEMP", ".")) / "release_pr_body.md"
    body_file.write_text(body, encoding="utf-8")

    _commit_materialized(
        config, releases, repinned, f"Materialize changelogs for {summary} ({action})"
    )
    git_push(f"HEAD:refs/heads/{branch}", config.root)

    url = gh_output(
        [
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            f"Release {summary}",
            "--body-file",
            str(body_file),
        ],
        config.root,
    )
    # An annotation as well as the summary: annotations surface on the run page
    # itself, so the pull request is one click away from wherever the dispatch
    # was watched from.
    notice(f"release pull request opened: {url}")

    # The PR only rewrites changelogs and deletes consumed news fragments, so
    # the fragment check does not apply. Label failure is not fatal.
    if gh_run(
        ["pr", "edit", url, "--add-label", SKIP_CHANGELOG_LABEL],
        config.root,
        check=False,
    ):
        notice(f"could not add the {SKIP_CHANGELOG_LABEL} label to {url}")

    number = url.rsplit("/", 1)[-1]
    write_summary([
        "## Release PR opened",
        "",
        f"Pull request: {link(f'#{number}' if number.isdigit() else url, url)}",
        "",
        f"Branch: {link(f'`{branch}`', _branch_url(branch))} → `{base}`",
        "",
        f"Releases: {summary}",
        "",
        "Merging it publishes them: review and merge the pull request, then",
        "approve the `pypi` environment deployments.",
    ])


def cmd_push_prerelease(
    config: Config,
    action: str,
    ref_name: str,
    releases_json: str,
    repinned_json: str,
) -> None:
    """Commit the materialized changelogs and push the prerelease branch.

    Args:
        config: The repository configuration.
        action: The release action that was materialized.
        ref_name: The branch the workflow was dispatched on.
        releases_json: The ``releases`` JSON emitted by :func:`cmd_plan`.
        repinned_json: The ``repinned`` JSON emitted by :func:`cmd_materialize`.
    """
    releases: list[dict[str, str]] = json.loads(releases_json)
    repinned = _repinned_paths(repinned_json)
    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    summary = _release_summary(releases)

    if action == "continued-prerelease":
        if not ref_name.startswith(config.prerelease_branch_prefix):
            fail(
                "continued-prerelease must be dispatched on the "
                f"{config.prerelease_branch_prefix}* branch of an existing "
                f"prerelease train (got {ref_name!r})"
            )
        branch = ref_name
    else:
        # Same release timezone as the changelog heading dates, so the branch
        # name and the headings never disagree.
        date_str = release_date_today(config.release_timezone).replace("-", ".")
        branch = f"{config.prerelease_branch_prefix}{date_str}"
        if remote_branch_exists(config.root, branch):
            branch = f"{branch}-{run_id}"

    _commit_materialized(
        config, releases, repinned, f"Materialize changelogs for {summary} ({action})"
    )
    git_push(f"HEAD:refs/heads/{branch}", config.root)

    # Pushes made with GITHUB_TOKEN do not fire on-push workflows, so dispatch
    # the changelog check explicitly. Building is automatic; the upload itself
    # still waits for pypi environment approval.
    gh_run(["workflow", "run", RELEASE_WORKFLOW, "--ref", branch], config.root)

    branch_url = _branch_url(branch)
    workflow_link = link(
        f"`{RELEASE_WORKFLOW}`", _workflow_runs_url(RELEASE_WORKFLOW, branch)
    )
    # An annotation as well as the summary: annotations surface on the run page
    # itself, so the branch is one click away from wherever the dispatch was
    # watched from.
    notice(f"prerelease branch pushed: {branch_url or branch}")
    write_summary([
        "## Prerelease pushed",
        "",
        f"Branch: {link(f'`{branch}`', branch_url)}",
        "",
        f"Releases: {summary}",
        "",
        f"Dispatched the {workflow_link} workflow on the branch; approve the",
        "`pypi` environment deployments to upload the alphas.",
    ])


def cmd_push_tag(config: Config, tag: str) -> None:
    """Tag the published commit and push the tag.

    Runs only after a successful upload — the tag's existence is what marks a
    version as published. Pushing an identical existing tag is a no-op (safe
    re-runs); a same-name tag on a different commit is rejected by git, which
    means another run already published this version from a different commit —
    investigate, do not force.

    Args:
        config: The repository configuration.
        tag: The tag to create and push.
    """
    git_run(["tag", "--force", tag], config.root)
    git_push(f"refs/tags/{tag}", config.root)


def _reads_as_absent(config: Config, stderr: str) -> bool:
    """Decide whether a failed release read means the tag has no release.

    gh answers "there is no such release" and "GitHub could not be asked" the
    same way: a non-zero exit and a message. A not-found is only evidence that
    the release is absent if GitHub could be reached and this repository read
    at all, so that is established rather than inferred from the wording — a
    404 for a repository that is missing, renamed or beyond the token's reach
    says nothing about the release.

    Args:
        config: The repository configuration.
        stderr: What gh wrote to stderr.

    Returns:
        Whether the tag can be treated as having no release.
    """
    lowered = stderr.lower()
    if not any(marker in lowered for marker in _NO_RELEASE_STDERR):
        return False
    # One extra call, and only on the path where a release is about to be
    # created anyway: if the repository reads back, the not-found was about the
    # release rather than about reaching GitHub.
    returncode, _, _ = gh_capture(["repo", "view", "--json", "name"], config.root)
    return returncode == 0


def _release_view(config: Config, tag: str) -> dict[str, Any] | None:
    """Read a GitHub release's metadata and asset list.

    Args:
        config: The repository configuration.
        tag: The tag the release points at.

    Returns:
        The parsed ``gh release view`` payload, or None when the tag has no
        release.
    """
    # A probe, not an action: keep its output (and its "not found" stderr on the
    # normal path) out of the job log.
    returncode, payload, stderr = gh_capture(
        ["release", "view", tag, "--json", ",".join(_RELEASE_FIELDS)], config.root
    )
    if returncode != 0:
        # A tag with no release and a GitHub that could not be reached both
        # exit non-zero. Only the first means there is nothing there; reading
        # the second as "no release" would create a release over one that
        # exists, or report a release that was just made as missing.
        if _reads_as_absent(config, stderr):
            return None
        fail(
            f"could not read the GitHub release for {tag}: gh exited "
            f"{returncode} saying {stderr or '(nothing)'}. Nothing is known "
            "about the release either way, so re-run this job once gh can "
            "reach GitHub."
        )
    try:
        release = json.loads(payload)
    except json.JSONDecodeError:
        fail(f"gh reported release metadata for {tag} that is not JSON: {payload!r}")
    # The shape is established once, here, so everything downstream can read the
    # payload as the release it claims to be rather than re-checking it. Each
    # miss is a diagnostic failure: a TypeError traceback out of a job that has
    # already published a version says nothing about what went wrong.
    if not isinstance(release, dict):
        fail(
            f"gh reported release metadata for {tag} that is not an object: {payload!r}"
        )
    if missing := [field for field in _RELEASE_FIELDS if field not in release]:
        fail(
            f"the release metadata gh reported for {tag} carries no "
            f"{', '.join(missing)}, so the release cannot be verified"
        )
    assets = release["assets"]
    if not isinstance(assets, list) or not all(
        isinstance(asset, dict) for asset in assets
    ):
        fail(
            f"the release metadata gh reported for {tag} lists its assets as "
            f"{assets!r} rather than as a list of assets, so what the release "
            "carries cannot be verified"
        )
    return release


def _metadata_problems(
    release: dict[str, Any], tag: str, title: str, prerelease: bool
) -> list[str]:
    """List the ways a GitHub release disagrees with what was published.

    Args:
        release: A ``gh release view`` payload.
        tag: The tag the release has to point at.
        title: The title the release has to carry.
        prerelease: Whether the release has to be flagged as a prerelease.

    Returns:
        Human-readable problems, empty when the release matches.
    """
    # The "Latest" marker is deliberately not checked: it belongs to the
    # repository rather than to one release, so a release published since this
    # one legitimately holds it.
    problems = []
    if (tag_name := release["tagName"]) != tag:
        problems.append(f"it points at tag {tag_name!r} rather than {tag!r}")
    if release["isDraft"]:
        problems.append("it is still a draft, so the version is not released")
    if (is_prerelease := bool(release["isPrerelease"])) != prerelease:
        problems.append(
            f"it is marked prerelease={is_prerelease} rather than "
            f"prerelease={prerelease}"
        )
    if (name := release["name"]) != title:
        problems.append(f"it is titled {name!r} rather than {title!r}")
    return problems


def _checksum_asset_problem(
    release: dict[str, Any], checksums_path: Path
) -> str | None:
    """Return why a release does not carry this run's checksum manifest, if so.

    Args:
        release: A ``gh release view`` payload.
        checksums_path: The local manifest of everything that was uploaded.

    Returns:
        A human-readable problem, or None when the release carries exactly this
        manifest.
    """
    name = checksums_path.name
    asset = next(
        (asset for asset in release["assets"] if asset.get("name") == name), None
    )
    if asset is None:
        return f"the {name} manifest is not attached to it"
    if (state := asset.get("state")) != "uploaded":
        return f"its {name} asset is in state {state!r} rather than 'uploaded'"
    if (size := asset.get("size")) != (expected := checksums_path.stat().st_size):
        return f"its {name} asset is {size} bytes rather than {expected}"
    return None


def _accept_existing_release(
    config: Config,
    tag: str,
    title: str,
    prerelease: bool,
    checksums_path: Path,
    release: dict[str, Any],
) -> None:
    """Accept a release an earlier attempt left behind, or fail loudly.

    A re-run stands down for an existing release only once that release is the
    one this run would have created: on this tag, published rather than drafted,
    flagged the same way and carrying the manifest of exactly what was uploaded.
    The one partial state a re-run can finish by itself is a missing or stale
    manifest — an attempt that died during the asset upload — so that is
    uploaded again; anything else is a release nobody here made, and the tag is
    not handed on until a human has looked at it.

    Args:
        config: The repository configuration.
        tag: The tag the release points at.
        title: The title this run would have given the release.
        prerelease: Whether this run would have flagged it as a prerelease.
        checksums_path: The ``sha256sum`` manifest of everything that was
            uploaded.
        release: The existing release's ``gh release view`` payload.
    """
    if problems := _metadata_problems(release, tag, title, prerelease):
        fail(
            f"a GitHub release already exists for {tag}, but {'; '.join(problems)}. "
            "It is not the release this publish would have created, so it is not "
            "handed to the post-release workflow: inspect it, then either fix it "
            "or delete it and re-run this job."
        )
    if checksums_path.is_file() and (
        problem := _checksum_asset_problem(release, checksums_path)
    ):
        notice(f"release {tag} exists but {problem}; attaching it now")
        gh_run(
            ["release", "upload", tag, str(checksums_path), "--clobber"], config.root
        )
        reread = _release_view(config, tag)
        problem = (
            "there is no release on the tag"
            if reread is None
            else _checksum_asset_problem(reread, checksums_path)
        )
        if problem:
            fail(
                f"attached the checksum manifest to the release for {tag}, but "
                f"reading it back found that {problem}"
            )
    echo(f"Release {tag} already matches this publish; skipping (safe re-run).")


def cmd_create_release(
    config: Config,
    tag: str,
    package: str,
    version: str,
    prerelease: bool,
    mark_latest: bool,
    notes_path: Path,
    checksums_path: Path,
) -> None:
    """Create the GitHub release for a published version.

    The release is read back once it exists: the next step hands the tag to the
    post-release workflow, which publishes docs and images against a release it
    trusts to be complete, so a release that is a draft, flagged the wrong way
    or missing the checksum manifest stops the job here instead.

    Args:
        config: The repository configuration.
        tag: The tag the release points at.
        package: The published package.
        version: The published version.
        prerelease: Whether to mark the release as a prerelease.
        mark_latest: Whether to mark the release as "Latest".
        notes_path: File holding the release notes.
        checksums_path: The ``sha256sum`` manifest of everything that was
            uploaded, attached to the release so the record of what a version
            contains outlives the workflow artifact it was built as.
    """
    # The root package is the repository, so its tag already names the release
    # unambiguously; only a sub-package needs to say which package it is.
    title = tag if package == config.root_package else f"{package}@{version}"
    existing = _release_view(config, tag)
    if existing is not None:
        _accept_existing_release(
            config, tag, title, prerelease, checksums_path, existing
        )
        return
    args = [
        "release",
        "create",
        tag,
        "--title",
        title,
        "--notes-file",
        str(notes_path),
    ]
    if sha := os.environ.get("GITHUB_SHA"):
        args += ["--target", sha]
    if prerelease:
        args += ["--prerelease", "--latest=false"]
    else:
        args.append("--latest" if mark_latest else "--latest=false")
    if checksums_path.is_file():
        args.append(str(checksums_path))
    else:
        notice(f"no checksum manifest at {checksums_path}; releasing without one")
    gh_run(args, config.root)

    # gh's exit status covers the request it made, not the state GitHub was
    # left in — a release whose asset upload failed is still a release — so what
    # the next step hands on is proven from GitHub's own copy of it.
    release = _release_view(config, tag)
    if release is None:
        fail(
            f"gh created the release for {tag}, but reading it back found no "
            f"release on the tag; check {tag} on the releases page before the "
            "post-release workflow is pointed at it"
        )
    if problems := _metadata_problems(release, tag, title, prerelease):
        fail(
            f"the GitHub release created for {tag} is not the one that was "
            f"asked for: {'; '.join(problems)}"
        )
    if checksums_path.is_file() and (
        problem := _checksum_asset_problem(release, checksums_path)
    ):
        fail(f"the GitHub release created for {tag} is incomplete: {problem}")
    echo(f"Release {tag} created and verified as {title!r}.")


def cmd_post_release(config: Config, tag: str, package: str, version: str) -> None:
    """Dispatch the configured post-release workflow for a published tag.

    Runs once per published tag, after the upload, the tag and the GitHub
    release: the workflow is dispatched on the tag itself, so it sees exactly
    the tree that was published. A failure here is loud but harmless — the
    version is already released — so it names the tag it could not hand on.

    Args:
        config: The repository configuration.
        tag: The tag that was published.
        package: The published package.
        version: The published version.
    """
    workflow = config.post_release_workflow
    if workflow is None:
        echo(f"no {POST_RELEASE_WORKFLOW_KEY} is configured; nothing to dispatch.")
        return
    # An unset environment variable reaches here as an empty string, and GitHub
    # accepts a dispatch carrying empty inputs — the run would go green having
    # told the workflow nothing.
    values = {"tag": tag, "package": package, "version": version}
    if missing := [name for name in POST_RELEASE_INPUTS if not values[name]]:
        fail(
            f"the post-release dispatch has no {', '.join(missing)}; it is run "
            "from the publish workflow with TAG, PACKAGE and VERSION in the "
            "environment"
        )
    config.require_known(package)

    fields: list[str] = []
    for name in POST_RELEASE_INPUTS:
        fields += ["--field", f"{name}={values[name]}"]
    failed = gh_run(
        ["workflow", "run", workflow, "--ref", tag, *fields], config.root, check=False
    )
    if failed:
        fail(
            f"{package} {version} was published and tagged {tag}, but the "
            f"post-release workflow {workflow!r} could not be dispatched on it. "
            "Check that the workflow exists on the default branch and declares "
            f"workflow_dispatch inputs named {', '.join(POST_RELEASE_INPUTS)}, "
            "then dispatch it by hand."
        )
    notice(f"dispatched {workflow} for {tag}")


def cmd_packages(config: Config) -> None:
    """Print the repository's releasable packages, one per line.

    Args:
        config: The repository configuration.
    """
    for package in releasable_packages(config):
        echo(package)
