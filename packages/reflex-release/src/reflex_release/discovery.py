"""Discovery of releasable packages, news fragments and towncrier settings."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from packaging.version import Version

from .actions import fail, warning
from .changelog import DEFAULT_TITLE_FORMAT, latest_version
from .config import Config, load_pyproject
from .gitutil import adding_commit_messages, git_run, latest_tag_version

#: towncrier's default prefix for fragments written before the number is known.
DEFAULT_ORPHAN_PREFIX = "+"

#: The two shapes GitHub itself writes a pull request number in: the subject of
#: a merge commit, and the suffix a squash merge appends to the subject.
_PR_SUBJECT_PATTERNS = (
    re.compile(r"^Merge pull request #(\d+)\b"),
    re.compile(r"\(#(\d+)\)$"),
)


def towncrier_table(config: Config) -> dict:
    """Return the repository's ``[tool.towncrier]`` table.

    Args:
        config: The repository configuration.

    Returns:
        The parsed table.
    """
    table = (
        load_pyproject(config.root / "pyproject.toml").get("tool", {}).get("towncrier")
    )
    if table is None:
        fail(
            "no [tool.towncrier] table in pyproject.toml; run `reflex-release init` "
            "or add the configuration from the reflex-release README"
        )
    return table


def title_format(config: Config) -> str:
    """Return the towncrier heading format used for release sections.

    Args:
        config: The repository configuration.

    Returns:
        The configured ``title_format``, or towncrier's markdown default when
        it is unset or empty (which is how towncrier reads it too).
    """
    configured = towncrier_table(config).get("title_format")
    # towncrier accepts `title_format = false` to write no heading at all. The
    # changelog is what tells this pipeline a version is due, so a changelog
    # without version headings would silently never publish.
    if configured is False:
        fail(
            "[tool.towncrier] title_format is false, which writes changelog "
            "sections with no version heading. The release pipeline finds "
            "versions by reading those headings, so releases would never be "
            'detected. Set a format such as "## {version} ({project_date})".'
        )
    if configured is not None and not isinstance(configured, str):
        fail(f"[tool.towncrier] title_format must be a string: {configured!r}")
    return configured or DEFAULT_TITLE_FORMAT


def orphan_prefix(config: Config) -> str:
    """Return the prefix marking a fragment as having no issue number yet.

    Args:
        config: The repository configuration.

    Returns:
        The configured ``orphan_prefix``, or towncrier's default. Empty when the
        repository disables orphan fragments.
    """
    configured = towncrier_table(config).get("orphan_prefix", DEFAULT_ORPHAN_PREFIX)
    if not isinstance(configured, str):
        fail(f"[tool.towncrier] orphan_prefix must be a string: {configured!r}")
    return configured


def category_order(config: Config) -> list[str]:
    """Read the towncrier category display names, in configured order.

    Args:
        config: The repository configuration.

    Returns:
        The category names from the ``[[tool.towncrier.type]]`` entries.
    """
    return [entry["name"] for entry in towncrier_table(config).get("type", [])]


def fragment_types(config: Config) -> set[str]:
    """Read the towncrier fragment type directory names.

    Args:
        config: The repository configuration.

    Returns:
        The type keys (``feature``, ``bugfix``, ...) fragments are named with.
    """
    return {entry["directory"] for entry in towncrier_table(config).get("type", [])}


def has_pending_fragments(news_dir: Path, types: set[str]) -> bool:
    """Return whether a news directory contains unmaterialized fragments.

    A fragment is any non-hidden file whose dot-separated name contains a
    configured fragment type (``1234.feature.md``, ``+name.bugfix.md``, ...);
    ``.gitkeep`` and stray files never count.

    Args:
        news_dir: The package's ``news`` directory (may not exist).
        types: The configured fragment type keys.

    Returns:
        True when at least one pending fragment exists.
    """
    if not news_dir.is_dir():
        return False
    return any(
        not path.name.startswith(".")
        and path.is_file()
        and not types.isdisjoint(path.name.split("."))
        for path in news_dir.iterdir()
    )


def split_fragment_name(basename: str, types: set[str]) -> tuple[str, str] | None:
    """Split a fragment filename into its issue part and the rest.

    Mirrors towncrier's own parsing: the fragment type is the last
    dot-separated part naming a configured type, everything before it is the
    issue and everything from it onwards is the suffix (type, optional counter,
    extension).

    Args:
        basename: The fragment filename.
        types: The configured fragment type keys.

    Returns:
        An ``(issue, suffix)`` tuple, or None when no part names a type.
    """
    parts = basename.split(".")
    for index in reversed(range(1, len(parts))):
        if parts[index] in types:
            return ".".join(parts[:index]), ".".join(parts[index:])
    return None


def pull_request_number(message: str) -> str | None:
    """Extract the pull request number a commit message refers to.

    Only the two shapes GitHub writes itself are recognized, and only in the
    subject: a number elsewhere in the message is a reference (``Fixes #12``),
    not the pull request the commit landed through.

    Args:
        message: The full commit message.

    Returns:
        The pull request number, or None when the subject names none.
    """
    subject = message.strip().partition("\n")[0].strip()
    for pattern in _PR_SUBJECT_PATTERNS:
        match = pattern.search(subject)
        if match:
            return match[1]
    return None


def _unused_fragment_name(taken: set[str], issue: str, suffix: str) -> str:
    """Return a fragment filename for an issue that no file in the directory uses.

    towncrier keys fragments by ``(issue, type, counter)``, so a second fragment
    for the same pull request and type takes the ``<issue>.<type>.<n>.<ext>``
    counter form instead of colliding with the first.

    Args:
        taken: The filenames already present in the news directory.
        issue: The issue (pull request) number to name the fragment after.
        suffix: The fragment suffix (type, optional counter, extension).

    Returns:
        A filename that is not in ``taken``.
    """
    candidate = f"{issue}.{suffix}"
    fragment_type, _, rest = suffix.partition(".")
    counter = 0
    while candidate in taken:
        counter += 1
        candidate = ".".join(filter(None, (issue, fragment_type, str(counter), rest)))
    return candidate


def _fragment_pull_request(root: Path, rel_path: str) -> str | None:
    """Return the pull request number a committed fragment landed through.

    Args:
        root: The repository root.
        rel_path: Repo-relative path of the fragment.

    Returns:
        The number named by the first candidate commit that has one, or None
        when none of them does.
    """
    for message in adding_commit_messages(root, rel_path):
        number = pull_request_number(message)
        if number is not None:
            return number
    return None


def associate_orphan_fragments(config: Config, package: str) -> list[tuple[str, str]]:
    """Rename a package's orphan fragments after the pull request that added them.

    A contributor who does not know the number yet writes ``+something.feature.md``
    and is supposed to rename it once the pull request exists; when they don't,
    the changelog entry ships with no link. The commit that added the fragment
    knows the number, so it is recovered here instead — right before towncrier
    consumes the fragments, so the entry gets its link.

    Fragments whose number cannot be recovered (added by a commit that did not
    land through a pull request, or not committed at all) are left alone, with a
    warning: towncrier renders them as entries without a link.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The ``(old name, new name)`` pairs that were renamed.

    Raises:
        ReleaseError: When a fragment cannot be renamed. Only a tracked fragment
            is ever renamed, so ``git mv`` failing means the worktree is not in
            the state the release assumes, and a bare rename in its place would
            leave the orphan behind in the release commit.
    """
    news_dir = config.news_dir(package)
    prefix = orphan_prefix(config)
    if not prefix or not news_dir.is_dir():
        return []
    types = fragment_types(config)
    fragments = sorted(news_dir.iterdir())
    taken = {path.name for path in fragments}
    renamed: list[tuple[str, str]] = []
    for path in fragments:
        if not path.name.startswith(prefix) or not path.is_file():
            continue
        parsed = split_fragment_name(path.name, types)
        if parsed is None:
            continue
        rel_path = path.relative_to(config.root).as_posix()
        number = _fragment_pull_request(config.root, rel_path)
        if number is None:
            warning(
                f"{rel_path}: no pull request found for the commit that added "
                "this orphan fragment; its changelog entry will have no link."
            )
            continue
        new_name = _unused_fragment_name(taken, number, parsed[1])
        # git mv, not a bare rename: the release commit stages only the
        # changelogs, so an unstaged deletion would leave the orphan behind for
        # the next release to materialize a second time.
        git_run(["mv", "--", str(path), str(news_dir / new_name)], config.root)
        taken.add(new_name)
        renamed.append((path.name, new_name))
    return renamed


def changelog_packages(config: Config) -> list[str]:
    """List the packages that maintain a ``CHANGELOG.md``.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order. Internal packages are excluded: they
        release by patch-bumping their newest tag, not from a changelog. So are
        never-published ones — a stray changelog in a package that does not ship
        must not become a publish trigger.
    """
    return [
        package
        for package in config.all_packages()
        if not config.is_internal(package)
        and not config.is_never_published(package)
        and config.changelog_path(package).is_file()
    ]


def releasable_packages(config: Config) -> list[str]:
    """List the packages a release action may target.

    Args:
        config: The repository configuration.

    Returns:
        Every package except the internal ones, which release on every push,
        and the never-published ones, which release at all.
    """
    return [
        package
        for package in config.all_packages()
        if not config.is_internal(package) and not config.is_never_published(package)
    ]


def pending_fragment_packages(config: Config) -> list[str]:
    """List packages with unmaterialized news fragments.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order.
    """
    types = fragment_types(config)
    return [
        package
        for package in releasable_packages(config)
        if has_pending_fragments(config.news_dir(package), types)
    ]


def alpha_train_packages(config: Config) -> list[str]:
    """List packages whose newest changelog version is a prerelease.

    This is the auto-selection signal for ``release-from-prerelease``: the
    train's fragments were already consumed into alpha sections, so pending
    fragments say nothing about which packages are in the train.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order.
    """
    selected: list[str] = []
    for package in changelog_packages(config):
        version = latest_version(
            config.changelog_path(package).read_text(encoding="utf-8")
        )
        if version is not None and version.is_prerelease:
            selected.append(package)
    return selected


def current_version(config: Config, package: str) -> Version | None:
    """Return the baseline version for planning a package's next version.

    The changelog is the source of truth, so its newest version wins; packages
    that have never materialized a changelog fall back to the newest git tag.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The baseline version, or None for a never-released package.
    """
    path = config.changelog_path(package)
    if path.is_file():
        version = latest_version(path.read_text(encoding="utf-8"))
        if version is not None:
            return version
    return latest_tag_version(config, package)


def run_towncrier(config: Config, args: list[str], check: bool = True) -> int:
    """Run towncrier against the repository's configuration.

    Args:
        config: The repository configuration.
        args: The towncrier subcommand and its arguments.
        check: Whether a non-zero exit should fail the release command.

    Returns:
        The exit status of towncrier.
    """
    result = subprocess.run(
        [sys.executable, "-m", "towncrier", *args], cwd=config.root, check=False
    )
    if check and result.returncode != 0:
        fail(f"towncrier {args[0]} failed")
    return result.returncode


def build_changelog(config: Config, package: str, version: str, date_str: str) -> None:
    """Materialize a package's news fragments into its changelog.

    A package with no pending fragments — a lockstep member dragged along by a
    sibling's release, typically — still gets a section, holding towncrier's
    "No significant changes." placeholder. Nobody has to hand-write an entry
    just to satisfy the lockstep invariant.

    Args:
        config: The repository configuration.
        package: The package name.
        version: The version to write (no ``v`` prefix; the heading gets one).
        date_str: The date for the section heading (YYYY-MM-DD).
    """
    run_towncrier(
        config,
        [
            "build",
            "--config",
            "pyproject.toml",
            "--dir",
            config.package_dir(package),
            "--version",
            f"v{version}",
            "--date",
            date_str,
            "--yes",
        ],
    )
