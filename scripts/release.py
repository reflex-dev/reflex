# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "packaging==26.2",
#     "towncrier==25.8.0",
#     "tomli==2.4.1; python_version < '3.11'",
# ]
# ///
# Exact pins, resolved with hashes in release.py.lock (regenerate with
# `uv lock --script scripts/release.py` after editing the list above).
# Every workflow call site passes --locked so header/lock drift fails loudly.
"""Changelog-driven release helpers for the CI release workflows.

The ``CHANGELOG.md`` files (repo root for ``reflex``, ``packages/<name>/`` for
sub-packages) are the source of truth for publishing: a package must be
published exactly when the newest version heading in its changelog has no
corresponding git tag. Tags are only created *after* a successful publish, so a
failed build or upload is retried by pushing a fix on top of the changelog bump
— no tags or releases ever need to be deleted.

Subcommands (all read their inputs from environment variables, GitHub Actions
style, and append to ``$GITHUB_OUTPUT`` / ``$GITHUB_STEP_SUMMARY``):

- ``detect``: list packages whose newest changelog version is untagged.
  Used by the ``release_from_changelog`` workflow on every push to ``main``,
  ``r/pre-*`` and ``r/hotfix/**`` branches. Final (non-prerelease) versions are
  only released from ``main`` or ``r/hotfix/**``; prereleases only from
  ``r/pre-*`` or ``r/hotfix/**``.
- ``plan``: compute the next version for each selected package for a release
  action (``new-prerelease-patch``, ``continued-prerelease``,
  ``release-from-prerelease``, ``release-major``, ...). An empty selection
  auto-detects packages with pending news fragments (or alpha-topped
  changelogs for ``release-from-prerelease``).
- ``materialize``: write the planned versions into the changelogs with
  towncrier; for ``release-from-prerelease`` also collapse the accumulated
  alpha sections into the single final-version section (alpha headings never
  appear in a published final changelog).
- ``prepare-publish``: validate a (package, version) pair against the
  changelog, the branch rules, the reflex/reflex-base lockstep invariant and
  existing tags, and emit build metadata for the publish workflow.
- ``pin-reflex-base``: rewrite reflex's ``reflex-base >= ...`` requirement to
  the exact release version before building.
- ``verify-dist``: check the core-metadata Version of every built artifact
  against the target version.
- ``extract-notes``: write the changelog section for a version to a file, for
  use as GitHub release notes.
- ``check-headings``: fail when the working tree adds changelog version
  headings that BASE_REF does not have — used by PR CI so hand-edited
  headings (which would otherwise be publish triggers) are rejected by the
  exact parser the release pipeline uses.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import NoReturn

from packaging.version import InvalidVersion, Version

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # pyright: ignore[reportMissingImports]

REPO_ROOT = Path(__file__).resolve().parent.parent

ROOT_PACKAGE = "reflex"

# Maps a dispatch action to (mode, submode) driving next_version().
ACTIONS: dict[str, tuple[str, str | None]] = {
    "new-prerelease-patch": ("new-prerelease", "patch"),
    "new-prerelease-minor": ("new-prerelease", "minor"),
    "new-prerelease-major": ("new-prerelease", "major"),
    "continued-prerelease": ("continued-prerelease", None),
    "release-from-prerelease": ("release", "from-prerelease"),
    "release-post": ("release", "post"),
    "release-patch": ("release", "patch"),
    "release-minor": ("release", "minor"),
    "release-major": ("release", "major"),
}

NO_SIGNIFICANT_CHANGES = "No significant changes"

_HEADING_RE = re.compile(r"^(?P<label>.*?)(?:\s+\((?P<date>[^()]*)\))?\s*$")

_PACKAGE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def fail(message: str) -> NoReturn:
    """Print an error to stderr and exit 1.

    Args:
        message: Human-readable description of the failure.
    """
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(1)


def notice(message: str) -> None:
    """Emit a GitHub Actions notice annotation (plain line outside Actions).

    Args:
        message: The notice text.
    """
    sys.stdout.write(f"::notice::{message}\n")


def package_dir(package: str) -> str:
    """Return the directory of a package relative to the repo root.

    Args:
        package: The package name (``reflex`` for the repo-root package).

    Returns:
        ``"."`` for the root package, ``packages/<name>`` otherwise.
    """
    return "." if package == ROOT_PACKAGE else f"packages/{package}"


def changelog_path(root: Path, package: str) -> Path:
    """Return the CHANGELOG.md path for a package.

    Args:
        root: The repo root.
        package: The package name.

    Returns:
        The path to the package's CHANGELOG.md (may not exist).
    """
    return root / package_dir(package) / "CHANGELOG.md"


def tag_prefix(package: str) -> str:
    """Return the git tag prefix for a package.

    Args:
        package: The package name.

    Returns:
        ``v`` for the root package (tags like ``v0.9.7``), ``<package>-v``
        otherwise (tags like ``reflex-base-v0.9.7``).
    """
    return "v" if package == ROOT_PACKAGE else f"{package}-v"


def tag_for(package: str, version: str) -> str:
    """Return the git tag name for a package version.

    Args:
        package: The package name.
        version: The version string (no ``v`` prefix).

    Returns:
        The tag name.
    """
    return f"{tag_prefix(package)}{version}"


def is_final(version: Version) -> bool:
    """Return whether a version is a final release (not a pre/dev release).

    Post releases count as final.

    Args:
        version: The parsed version.

    Returns:
        True when the version is neither a prerelease nor a dev release.
    """
    return not version.is_prerelease and not version.is_devrelease


def branch_allows_publish(version: Version, ref_name: str) -> bool:
    """Return whether a version may be published from a branch.

    Final (non-prerelease) tags can only be published and pushed from ``main``
    or from a hotfix branch like ``r/hotfix/...``; prereleases only from the
    branches the Dispatch release workflow materializes them on (``r/pre-*``,
    or ``r/pre-*`` trains cut from an ``r/hotfix/**`` branch).

    Args:
        version: The version to publish.
        ref_name: The branch name (``github.ref_name``).

    Returns:
        True when the branch may publish the version.
    """
    if is_final(version):
        return ref_name == "main" or ref_name.startswith("r/hotfix/")
    return ref_name.startswith(("r/pre-", "r/hotfix/"))


def lockstep_partner(package: str) -> str | None:
    """Return the package that must release in lockstep with ``package``.

    ``reflex`` and ``reflex-base`` always release together at the same version
    (reflex's metadata pins ``reflex-base`` exactly), so publishing one
    requires the other at the identical version.

    Args:
        package: The package name.

    Returns:
        The partner package name, or None when the package has no partner.
    """
    if package == ROOT_PACKAGE:
        return "reflex-base"
    if package == "reflex-base":
        return ROOT_PACKAGE
    return None


@dataclasses.dataclass(frozen=True)
class Section:
    """One ``## <version> (<date>)`` section of a towncrier changelog."""

    label: str
    date: str | None
    version: Version | None
    body: str
    raw: str


def heading_version(label: str, date: str | None) -> Version | None:
    """Parse the version out of a section heading label.

    Args:
        label: The heading text without the ``## `` prefix or date suffix.
        date: The parenthesized date portion of the heading, if any.

    Returns:
        The parsed version, or None for unparsable or "Unreleased" headings.
    """
    if "unreleased" in label.lower() or "unreleased" in (date or "").lower():
        return None
    try:
        return Version(label.removeprefix("v"))
    except InvalidVersion:
        return None


def parse_sections(text: str) -> tuple[str, list[Section]]:
    """Split changelog markdown into a preamble and its ``## `` sections.

    Args:
        text: The changelog markdown.

    Returns:
        A ``(preamble, sections)`` tuple; the preamble is everything before the
        first ``## `` heading (usually empty for towncrier changelogs).
    """
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not starts:
        return text, []
    preamble = "".join(lines[: starts[0]])
    sections: list[Section] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        match = _HEADING_RE.match(lines[start][3:].strip())
        label = match["label"] if match else ""
        date = match["date"] if match else None
        sections.append(
            Section(
                label=label,
                date=date,
                version=heading_version(label, date),
                body="".join(lines[start + 1 : end]),
                raw="".join(lines[start:end]),
            )
        )
    return preamble, sections


def latest_version(text: str) -> Version | None:
    """Return the newest version in a changelog, skipping "Unreleased".

    The newest version is the first section heading that parses as a version;
    towncrier prepends new sections, so document order is version order.

    Args:
        text: The changelog markdown.

    Returns:
        The version of the first versioned section, or None.
    """
    _, sections = parse_sections(text)
    for section in sections:
        if section.version is not None:
            return section.version
    return None


def extract_notes(text: str, version: Version) -> str | None:
    """Return the body of the changelog section for a version.

    Args:
        text: The changelog markdown.
        version: The version whose section to extract.

    Returns:
        The section body without the heading, stripped, or None if the version
        has no section.
    """
    _, sections = parse_sections(text)
    for section in sections:
        if section.version == version:
            return section.body.strip()
    return None


def split_categories(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a section body into leading text and its ``### `` category blocks.

    Args:
        body: The section body (text below a ``## `` heading).

    Returns:
        A ``(lead, categories)`` tuple where lead is the text before the first
        category heading and categories is a list of ``(name, block)`` pairs.
    """
    lines = body.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("### ")]
    if not starts:
        return body, []
    lead = "".join(lines[: starts[0]])
    categories: list[tuple[str, str]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        categories.append((lines[start][4:].strip(), "".join(lines[start + 1 : end])))
    return lead, categories


def load_category_order(root: Path) -> list[str]:
    """Read the towncrier category display names, in configured order.

    Args:
        root: The repo root containing pyproject.toml.

    Returns:
        The category names from ``[[tool.towncrier.type]]`` entries.
    """
    data = tomllib.loads((root / "pyproject.toml").read_text())
    return [entry["name"] for entry in data["tool"]["towncrier"]["type"]]


def load_fragment_types(root: Path) -> set[str]:
    """Read the towncrier fragment type directory names.

    Args:
        root: The repo root containing pyproject.toml.

    Returns:
        The type keys (``feature``, ``bugfix``, ...) fragments are named with.
    """
    data = tomllib.loads((root / "pyproject.toml").read_text())
    return {entry["directory"] for entry in data["tool"]["towncrier"]["type"]}


def _has_pending_fragments(news_dir: Path, types: set[str]) -> bool:
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


def pending_fragment_packages(root: Path) -> list[str]:
    """List packages with unmaterialized news fragments.

    Fragments in the repo-root ``news/`` belong to ``reflex``, which is not
    independently releasable — they select ``reflex-base`` instead (the plan
    pairing releases reflex alongside it, consuming the root fragments).

    Args:
        root: The repository root.

    Returns:
        Package names with pending fragments, reflex-base first (when the
        root has fragments), then sub-packages in alphabetical order.
    """
    types = load_fragment_types(root)
    selected: list[str] = []
    if _has_pending_fragments(root / "news", types):
        selected.append("reflex-base")
    selected.extend(
        news_dir.parent.name
        for news_dir in sorted((root / "packages").glob("*/news"))
        if _has_pending_fragments(news_dir, types)
    )
    return list(dict.fromkeys(selected))


def alpha_train_packages(root: Path) -> list[str]:
    """List packages whose newest changelog version is a prerelease.

    This is the auto-selection signal for ``release-from-prerelease``: the
    train's fragments were already consumed into alpha sections, so pending
    fragments say nothing about which packages are in the train. ``reflex``
    maps to ``reflex-base`` (the pair releases together via plan pairing).

    Args:
        root: The repository root.

    Returns:
        Package names, deduplicated, in changelog-discovery order.
    """
    selected: list[str] = []
    for package in discover_changelog_packages(root):
        version = latest_version(changelog_path(root, package).read_text())
        if version is None or not version.is_prerelease:
            continue
        selected.append("reflex-base" if package == ROOT_PACKAGE else package)
    return list(dict.fromkeys(selected))


def collapse_prereleases(
    text: str, final_version: Version, date_str: str, category_order: list[str]
) -> str:
    """Collapse the top prerelease sections into a single final section.

    Merges the section for ``final_version`` (freshly written by towncrier from
    any remaining fragments) together with every consecutive prerelease section
    at the top of the changelog into one ``## v<final_version>`` section,
    concatenating each category's entries oldest-first. "No significant
    changes." placeholders are dropped unless nothing else remains.

    Args:
        text: The changelog markdown.
        final_version: The final version being released.
        date_str: The date for the new section heading (YYYY-MM-DD).
        category_order: Category names in canonical display order.

    Returns:
        The rewritten changelog markdown.
    """
    preamble, sections = parse_sections(text)
    run: list[Section] = []
    for section in sections:
        if section.version is not None and (
            section.version == final_version or section.version.is_prerelease
        ):
            run.append(section)
        else:
            break
    if not run:
        fail(f"no prerelease sections to collapse into v{final_version}")

    strays = [
        section
        for section in sections[len(run) :]
        if section.version is not None and section.version.is_prerelease
    ]
    for stray in strays:
        sys.stderr.write(
            f"Warning: prerelease section '{stray.label}' is not contiguous "
            "with the top of the changelog and was left in place.\n"
        )

    merged: dict[str, list[str]] = {}
    extra_categories: list[str] = []
    leads: list[str] = []
    for section in reversed(run):
        lead, categories = split_categories(section.body)
        lead = lead.strip()
        if lead and not lead.startswith(NO_SIGNIFICANT_CHANGES):
            leads.append(lead)
        for name, block in categories:
            block = block.strip()
            if not block:
                continue
            if name not in merged:
                merged[name] = []
                if name not in category_order:
                    extra_categories.append(name)
            merged[name].append(block)

    parts: list[str] = [f"## v{final_version} ({date_str})", ""]
    if leads:
        parts.extend(["\n\n".join(leads), ""])
    for name in [*category_order, *extra_categories]:
        if name in merged:
            parts.extend([f"### {name}", "", "\n".join(merged[name]), ""])
    if not leads and not merged:
        parts.extend([f"{NO_SIGNIFICANT_CHANGES}.", ""])

    new_section = "\n".join(parts).rstrip("\n") + "\n"
    remainder = "".join(section.raw for section in sections[len(run) :])
    if remainder:
        return f"{preamble}{new_section}\n\n{remainder}"
    return preamble + new_section


def _git(args: list[str], cwd: Path) -> str:
    """Run a git command and return its stdout.

    Args:
        args: The git arguments (without the leading ``git``).
        cwd: The repository directory.

    Returns:
        The command's stdout.
    """
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def _tag_versions(root: Path, package: str) -> list[Version]:
    """Return every PEP 440 version tagged for a package.

    Args:
        root: The repository root.
        package: The package name.

    Returns:
        The parsed versions, unordered.
    """
    prefix = tag_prefix(package)
    versions: list[Version] = []
    for line in _git(["tag", "-l", f"{prefix}*"], cwd=root).splitlines():
        raw = line.removeprefix(prefix).strip()
        if not raw:
            continue
        try:
            versions.append(Version(raw))
        except InvalidVersion:
            continue
    return versions


def latest_tag_version(root: Path, package: str) -> Version | None:
    """Return the largest PEP 440 version tagged for a package.

    Args:
        root: The repository root.
        package: The package name.

    Returns:
        The largest tagged version, or None if the package has no tags.
    """
    versions = _tag_versions(root, package)
    return max(versions) if versions else None


def latest_final_tag_version(root: Path, package: str) -> Version | None:
    """Return the largest final (non-pre, non-dev) version tagged for a package.

    Args:
        root: The repository root.
        package: The package name.

    Returns:
        The largest final tagged version, or None if there is none.
    """
    finals = [v for v in _tag_versions(root, package) if is_final(v)]
    return max(finals) if finals else None


def tag_exists(root: Path, tag: str) -> bool:
    """Return whether a git tag exists in the local repository.

    Args:
        root: The repository root.
        tag: The tag name.

    Returns:
        True when the tag exists.
    """
    return (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def current_version(root: Path, package: str) -> Version | None:
    """Return the baseline version for planning a package's next version.

    The changelog is the source of truth, so its newest version wins; packages
    that have never materialized a changelog fall back to the newest git tag.

    Args:
        root: The repository root.
        package: The package name.

    Returns:
        The baseline version, or None for a never-released package.
    """
    path = changelog_path(root, package)
    if path.is_file():
        version = latest_version(path.read_text())
        if version is not None:
            return version
    return latest_tag_version(root, package)


def next_version(current: Version | None, action: str, package: str) -> str:
    """Compute the next version for a package given a release action.

    Args:
        current: The baseline version, or None if the package was never
            released.
        action: One of the keys in ACTIONS.
        package: Package name, used for error messages.

    Returns:
        The next version string (canonical PEP 440, no ``v`` prefix).
    """
    mode, sub = ACTIONS[action]

    if current is None:
        major = minor = patch = alpha_n = post_n = 0
        is_alpha = False
    else:
        major, minor, patch = current.major, current.minor, current.micro
        is_alpha = current.pre is not None and current.pre[0] == "a"
        alpha_n = current.pre[1] if is_alpha and current.pre is not None else 0
        post_n = current.post or 0

    display = str(current) if current is not None else "<none>"
    # Only aN prereleases are produced by this tooling; a b/rc heading means
    # the changelog was edited outside the sanctioned flow.
    alpha_hint = (
        " (only alpha aN prereleases are supported)"
        if current is not None and current.pre is not None and not is_alpha
        else ""
    )

    if mode == "new-prerelease":
        if current is not None and current.is_prerelease:
            fail(
                f"new-prerelease-* would abandon the in-progress {display} "
                f"train for {package}; use continued-prerelease or "
                "release-from-prerelease on its r/pre-* branch, or dispatch "
                "from main to start a new train"
            )
        if sub == "patch":
            return f"{major}.{minor}.{patch + 1}a1"
        if sub == "minor":
            return f"{major}.{minor + 1}.0a1"
        return f"{major + 1}.0.0a1"

    if mode == "continued-prerelease":
        if not is_alpha:
            fail(
                f"continued-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}{alpha_hint}"
            )
        return f"{major}.{minor}.{patch}a{alpha_n + 1}"

    if sub == "from-prerelease":
        if not is_alpha:
            fail(
                f"release-from-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}{alpha_hint}"
            )
        return f"{major}.{minor}.{patch}"
    if sub == "post":
        if current is None:
            fail(f"release-post requires an existing release; none for {package}")
        if is_alpha:
            fail(
                f"release-post cannot follow an alpha; newest for {package} "
                f"is {display!r}"
            )
        return f"{major}.{minor}.{patch}.post{post_n + 1}"
    if sub == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if sub == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"


def run_towncrier(root: Path, package: str, version: str) -> None:
    """Materialize a package's news fragments into its CHANGELOG.md.

    Args:
        root: The repository root.
        package: The package name.
        version: The version to write (no ``v`` prefix; the heading gets one).
    """
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--config",
            "pyproject.toml",
            "--dir",
            package_dir(package),
            "--version",
            f"v{version}",
            "--yes",
        ],
        cwd=root,
        check=True,
    )


def discover_changelog_packages(root: Path) -> list[str]:
    """List the packages that maintain a CHANGELOG.md.

    Args:
        root: The repository root.

    Returns:
        Package names — ``reflex`` first (when the root changelog exists),
        then sub-packages in alphabetical order. Only packages that also have
        a pyproject.toml are included.
    """
    packages: list[str] = []
    if (root / "CHANGELOG.md").is_file() and (root / "pyproject.toml").is_file():
        packages.append(ROOT_PACKAGE)
    packages.extend(
        sorted(
            path.parent.name
            for path in (root / "packages").glob("*/CHANGELOG.md")
            if (path.parent / "pyproject.toml").is_file()
        )
    )
    return packages


def _append_lines(env_var: str, lines: list[str]) -> None:
    """Append lines to the file named by a GitHub Actions environment variable.

    Args:
        env_var: ``GITHUB_OUTPUT`` or ``GITHUB_STEP_SUMMARY``.
        lines: The lines to append.
    """
    with Path(os.environ[env_var]).open("a") as f:
        f.write("\n".join(lines) + "\n")


def write_outputs(**outputs: str) -> None:
    """Append ``key=value`` pairs to ``$GITHUB_OUTPUT``.

    Args:
        **outputs: Output names and single-line values.
    """
    _append_lines("GITHUB_OUTPUT", [f"{key}={value}" for key, value in outputs.items()])


def _plan_table(releases: list[dict[str, str]]) -> list[str]:
    """Render the release plan as a markdown table.

    Args:
        releases: Release dicts with package/current/next/tag keys.

    Returns:
        The markdown lines.
    """
    rows = [
        "| Package | Current | Next | Tag |",
        "|---------|---------|------|-----|",
    ]
    rows.extend(
        f"| `{r['package']}` | `{r['current'] or '<none>'}` | `{r['next']}` "
        f"| `{r['tag']}` |"
        for r in releases
    )
    return rows


def _check_lockstep(root: Path, due: dict[str, str]) -> list[str]:
    """Verify the reflex/reflex-base lockstep invariant for a release batch.

    Each lockstep partner of a due package must either be due at the identical
    version in the same batch or already carry the tag for that version (the
    retry case where one half published earlier).

    Args:
        root: The repository root.
        due: Mapping of due package name to version string.

    Returns:
        A list of human-readable violations (empty when the batch is sound).
    """
    errors: list[str] = []
    for package, version in due.items():
        partner = lockstep_partner(package)
        if partner is None:
            continue
        partner_tag = tag_for(partner, version)
        if due.get(partner) != version and not tag_exists(root, partner_tag):
            errors.append(
                f"{package} v{version} is due but its lockstep partner "
                f"{partner} is neither due at v{version} nor already tagged "
                f"{partner_tag}; publishing would break the exact "
                "reflex/reflex-base pin. Materialize both changelogs together "
                "(Dispatch release workflow)."
            )
    return errors


def cmd_detect() -> None:
    """Detect packages whose newest changelog version has no git tag.

    Reads REF_NAME from the environment. Writes to ``$GITHUB_OUTPUT``:
    ``packages`` (JSON array of ``{package, version, tag}``, excluding
    ``reflex``), ``any`` (whether that array is non-empty), and
    ``reflex_version`` (empty when reflex is not due). ``reflex`` is emitted
    separately so the caller can publish it after its dependencies.

    Fails closed when the reflex/reflex-base lockstep invariant is violated.
    """
    root = REPO_ROOT
    ref_name = os.environ["REF_NAME"]

    releases: list[dict[str, str]] = []
    rows = [
        "## Changelog release check",
        "",
        f"Branch: `{ref_name}`",
        "",
        "| Package | Newest changelog version | Status |",
        "|---------|--------------------------|--------|",
    ]
    for package in discover_changelog_packages(root):
        version = latest_version(changelog_path(root, package).read_text())
        if version is None:
            rows.append(f"| `{package}` | `<none>` | no versioned section |")
            continue
        tag = tag_for(package, str(version))
        if tag_exists(root, tag):
            rows.append(f"| `{package}` | `{version}` | already tagged `{tag}` |")
            continue
        if not branch_allows_publish(version, ref_name):
            kind = "final" if is_final(version) else "prerelease"
            allowed = (
                "main and r/hotfix/**"
                if is_final(version)
                else "r/pre-* and r/hotfix/**"
            )
            notice(
                f"{package} v{version} is a {kind} version but branch "
                f"'{ref_name}' cannot publish {kind}s (only {allowed} can); "
                "skipping."
            )
            rows.append(f"| `{package}` | `{version}` | skipped: branch rule |")
            continue
        releases.append({"package": package, "version": str(version), "tag": tag})
        rows.append(f"| `{package}` | `{version}` | **will publish** `{tag}` |")

    due = {r["package"]: r["version"] for r in releases}
    lockstep_errors = _check_lockstep(root, due)

    others = [r for r in releases if r["package"] != ROOT_PACKAGE]
    reflex_version = due.get(ROOT_PACKAGE, "")

    _append_lines("GITHUB_STEP_SUMMARY", rows)
    write_outputs(
        packages=json.dumps(others),
        any="true" if others else "false",
        reflex_version=reflex_version,
    )
    if lockstep_errors:
        for error in lockstep_errors:
            sys.stdout.write(f"::error::{error}\n")
        sys.exit(1)


def cmd_plan() -> None:
    """Plan the next version for each selected package.

    Reads PACKAGES_JSON and ACTION from the environment; writes ``releases``
    (JSON array of ``{package, current, next, tag}``) to ``$GITHUB_OUTPUT``.

    An empty selection auto-detects the packages to release: those with
    pending news fragments — or, for ``release-from-prerelease``, those whose
    changelog is topped by an alpha (their fragments are already consumed).
    """
    root = REPO_ROOT
    action = os.environ["ACTION"]
    packages: list[str] = json.loads(os.environ["PACKAGES_JSON"])

    if action not in ACTIONS:
        fail(f"unknown action '{action}'")

    selection = "explicit"
    if not packages:
        if action == "release-from-prerelease":
            packages = alpha_train_packages(root)
            selection = "auto: alpha-topped changelogs"
            source = "an alpha-topped changelog"
        else:
            packages = pending_fragment_packages(root)
            selection = "auto: pending news fragments"
            source = "pending news fragments"
        if not packages:
            fail(f"no packages selected and no package has {source}")
        notice(f"no packages selected; auto-detected {', '.join(packages)}")

    releases: list[dict[str, str]] = []
    for package in packages:
        current = current_version(root, package)
        nxt = next_version(current, action, package)
        tag = tag_for(package, nxt)
        if tag_exists(root, tag):
            fail(f"tag {tag} already exists")
        releases.append({
            "package": package,
            "current": str(current) if current is not None else "",
            "next": nxt,
            "tag": tag,
        })

    # reflex is not independently releasable: when reflex-base is released,
    # reflex is released alongside it with a matching version (the publish
    # workflow pins reflex-base exactly when building reflex).
    base = next((r for r in releases if r["package"] == "reflex-base"), None)
    if base is not None and all(r["package"] != ROOT_PACKAGE for r in releases):
        reflex_tag = tag_for(ROOT_PACKAGE, base["next"])
        if tag_exists(root, reflex_tag):
            fail(f"tag {reflex_tag} already exists")
        current = current_version(root, ROOT_PACKAGE)
        releases.append({
            "package": ROOT_PACKAGE,
            "current": str(current) if current is not None else "",
            "next": base["next"],
            "tag": reflex_tag,
        })

    _append_lines(
        "GITHUB_STEP_SUMMARY",
        [
            "## Release plan",
            "",
            f"Action: `{action}`  ",
            f"Selection: `{selection}`",
            "",
            *_plan_table(releases),
        ],
    )
    write_outputs(releases=json.dumps(releases))


def cmd_materialize() -> None:
    """Write the planned versions into the changelogs via towncrier.

    Reads RELEASES_JSON and ACTION from the environment. For
    ``release-from-prerelease``, collapses the alpha sections of each changelog
    into the single final-version section after building it.
    """
    root = REPO_ROOT
    action = os.environ["ACTION"]
    releases: list[dict[str, str]] = json.loads(os.environ["RELEASES_JSON"])
    collapse = action == "release-from-prerelease"
    category_order = load_category_order(root) if collapse else []
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    for release in releases:
        package, version = release["package"], release["next"]
        run_towncrier(root, package, version)
        if collapse:
            path = changelog_path(root, package)
            path.write_text(
                collapse_prereleases(
                    path.read_text(), Version(version), today, category_order
                )
            )


def cmd_prepare_publish() -> None:
    """Validate a (package, version) pair for publishing and emit metadata.

    Reads PACKAGE, VERSION and REF_NAME from the environment. Enforces the
    changelog as source of truth (the version must be the newest changelog
    version when the package has a changelog), the branch rules for final
    versions, and detects already-published (tagged) versions. An empty
    VERSION is only valid for packages without a changelog (the internal
    packages) and patch-bumps the newest tag; it is computed here, inside the
    per-package publish concurrency group, so back-to-back publishes cannot
    compute the same version.

    Writes to ``$GITHUB_OUTPUT``: ``package``, ``version`` (canonical),
    ``tag``, ``build_dir``, ``prerelease``, ``mark_latest`` and ``skipped``.
    """
    root = REPO_ROOT
    package = os.environ["PACKAGE"]
    raw_version = os.environ.get("VERSION", "").strip().removeprefix("v")
    ref_name = os.environ["REF_NAME"]

    if not _PACKAGE_NAME_RE.fullmatch(package):
        fail(f"invalid package name {package!r}")
    if (
        package != ROOT_PACKAGE
        and not (root / "packages" / package / "pyproject.toml").is_file()
    ):
        fail(f"unknown package {package!r} (no packages/{package}/pyproject.toml)")

    path = changelog_path(root, package)
    if raw_version:
        try:
            version = Version(raw_version)
        except InvalidVersion:
            fail(f"invalid version {raw_version!r}")
        if version.epoch or version.local or version.is_devrelease:
            fail(f"refusing to publish epoch/local/dev version {version}")
    elif path.is_file():
        fail(
            f"a target version is required for {package}: its CHANGELOG.md is "
            "the source of truth (materialize it via the Dispatch release "
            "workflow)."
        )
    else:
        newest_tag = latest_tag_version(root, package)
        version = (
            Version(f"{newest_tag.major}.{newest_tag.minor}.{newest_tag.micro + 1}")
            if newest_tag is not None
            else Version("0.0.1")
        )
        notice(f"no version given; auto patch-bump for {package}: {version}")

    if not branch_allows_publish(version, ref_name):
        allowed = (
            "main or an r/hotfix/** branch"
            if is_final(version)
            else "an r/pre-* or r/hotfix/** branch"
        )
        fail(
            f"version {version} can only be published from {allowed}, not {ref_name!r}"
        )

    if path.is_file():
        newest = latest_version(path.read_text())
        if newest != version:
            fail(
                f"changelog is the source of truth: newest version in "
                f"{path.relative_to(root)} is "
                f"{newest if newest is not None else '<none>'}, not {version}. "
                "Materialize the changelog first (Dispatch release workflow)."
            )
    else:
        notice(f"{package} has no CHANGELOG.md; skipping changelog check.")

    partner = lockstep_partner(package)
    if partner is not None and not tag_exists(root, tag_for(partner, str(version))):
        partner_path = changelog_path(root, partner)
        partner_newest = (
            latest_version(partner_path.read_text()) if partner_path.is_file() else None
        )
        if partner_newest != version:
            fail(
                f"{package} v{version} releases in lockstep with {partner}, "
                f"but {partner} is neither tagged at v{version} nor "
                f"materialized at it (its newest changelog version is "
                f"{partner_newest if partner_newest is not None else '<none>'})."
            )

    tag = tag_for(package, str(version))
    skipped = tag_exists(REPO_ROOT, tag)
    if skipped:
        notice(f"tag {tag} already exists; nothing to publish.")

    # Only mark the GitHub release "Latest" when this is genuinely the newest
    # final reflex version — a hotfix of an older line must not steal the
    # badge from a newer release.
    newest_final = latest_final_tag_version(root, ROOT_PACKAGE)
    mark_latest = (
        package == ROOT_PACKAGE
        and is_final(version)
        and (newest_final is None or version >= newest_final)
    )

    summary = [
        "## Publish",
        "",
        f"Package: `{package}`  ",
        f"Version: `{version}`  ",
        f"Tag: `{tag}`  ",
        f"Status: {'skipped (already tagged)' if skipped else 'publishing'}",
    ]
    _append_lines("GITHUB_STEP_SUMMARY", summary)
    write_outputs(
        package=package,
        version=str(version),
        tag=tag,
        build_dir=package_dir(package),
        prerelease="true" if version.is_prerelease else "false",
        mark_latest="true" if mark_latest else "false",
        skipped="true" if skipped else "false",
    )


def cmd_pin_reflex_base() -> None:
    """Pin reflex's reflex-base dependency to the exact release version.

    Reads VERSION from the environment and rewrites the single
    ``"reflex-base >= ..."`` requirement in the repo-root pyproject.toml to
    ``"reflex-base == <version>"``, failing unless exactly one requirement was
    rewritten. The two packages release in lockstep, so the built reflex wheel
    must depend on exactly the sibling version published alongside it.
    """
    version = Version(os.environ["VERSION"])
    path = REPO_ROOT / "pyproject.toml"
    new_pin = f'"reflex-base == {version}"'
    updated, count = re.subn(r'"reflex-base >= [^"]*"', new_pin, path.read_text())
    if count != 1:
        fail(
            f'expected exactly one "reflex-base >= ..." requirement in '
            f"pyproject.toml, found {count}"
        )
    path.write_text(updated)
    sys.stderr.write(f"Pinned {new_pin} in pyproject.toml\n")


def _dist_metadata_version(path: Path) -> str:
    """Read the ``Version`` metadata field of a built distribution.

    Args:
        path: A wheel (``*.whl``) or sdist (``*.tar.gz``).

    Returns:
        The Version header value from the wheel's METADATA / sdist's PKG-INFO.
    """
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as wheel:
            names = [
                n
                for n in wheel.namelist()
                if n.endswith(".dist-info/METADATA") and n.count("/") == 1
            ]
            if len(names) != 1:
                fail(f"expected one .dist-info/METADATA in {path.name}, got {names}")
            content = wheel.read(names[0]).decode()
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as sdist:
            names = [
                m.name
                for m in sdist.getmembers()
                if m.name.endswith("/PKG-INFO") and m.name.count("/") == 1
            ]
            if len(names) != 1:
                fail(f"expected one top-level PKG-INFO in {path.name}, got {names}")
            member = sdist.extractfile(names[0])
            if member is None:
                fail(f"could not read {names[0]} from {path.name}")
            content = member.read().decode()
    else:
        fail(f"unexpected artifact type: {path.name}")
    for line in content.splitlines():
        if not line.strip():
            break
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    fail(f"no Version field in the metadata of {path.name}")


def cmd_verify_dist() -> None:
    """Verify every built artifact carries exactly the target version.

    Reads VERSION (and optionally DIST_DIR, default ``dist``) from the
    environment and compares each artifact's core-metadata ``Version`` field
    against the target with PEP 440 equality. Catches a misconfigured
    uv-dynamic-versioning tag prefix building e.g. ``0.0.0dev0``.
    """
    target = Version(os.environ["VERSION"])
    dist = REPO_ROOT / os.environ.get("DIST_DIR", "dist")
    # Verify exactly what `uv publish dist/*` will upload: the shell glob
    # skips hidden files (uv build drops a .gitignore into dist/).
    files = sorted(
        path
        for path in dist.glob("*")
        if path.is_file() and not path.name.startswith(".")
    )
    if not files:
        fail(f"no artifacts in {dist}")
    for path in files:
        raw = _dist_metadata_version(path)
        try:
            found = Version(raw)
        except InvalidVersion:
            fail(f"artifact {path.name} has unparsable version {raw!r}")
        if found != target:
            fail(f"artifact {path.name} has version {found}, expected {target}")
    sys.stderr.write(f"✓ {len(files)} artifact(s) at version {target}\n")


def _git_show(root: Path, ref: str, rel_path: str) -> str | None:
    """Return a file's content at a git ref, or None if absent there.

    Args:
        root: The repository root.
        ref: The git ref (e.g. ``origin/main``).
        rel_path: Repo-relative file path.

    Returns:
        The file content at the ref, or None when the path does not exist.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def cmd_check_headings() -> None:
    """Fail when the working tree adds changelog version headings vs BASE_REF.

    Reads BASE_REF from the environment. Any versioned section heading (as
    recognized by the same parser the release pipeline publishes from) that
    exists in a working-tree CHANGELOG.md but not at BASE_REF is rejected:
    a merged heading without a git tag is a real publish trigger, so new
    headings must come from the Dispatch release workflow.
    """
    root = REPO_ROOT
    base_ref = os.environ["BASE_REF"]
    errors: list[str] = []
    for package in discover_changelog_packages(root):
        path = changelog_path(root, package)
        rel_path = path.relative_to(root).as_posix()
        base_text = _git_show(root, base_ref, rel_path) or ""
        known = {
            section.version
            for section in parse_sections(base_text)[1]
            if section.version is not None
        }
        errors.extend(
            f"{rel_path}: adds version heading '## {section.label}' "
            f"(v{section.version})"
            for section in parse_sections(path.read_text())[1]
            if section.version is not None and section.version not in known
        )
    if errors:
        for error in errors:
            sys.stdout.write(f"::error::{error}\n")
        fail(
            "new CHANGELOG.md version headings are publish triggers and must "
            "be materialized by the Dispatch release workflow (release/* "
            "branches). If this is deliberate restructuring of "
            "already-published sections, apply the 'changelog-version-edit' "
            "label."
        )
    sys.stderr.write("No new changelog version headings.\n")


def cmd_extract_notes() -> None:
    """Write the changelog section for a version to NOTES_PATH.

    Reads PACKAGE, VERSION and NOTES_PATH from the environment. Falls back to
    a generic one-liner when the package has no changelog section for the
    version.
    """
    root = REPO_ROOT
    package = os.environ["PACKAGE"]
    version = Version(os.environ["VERSION"].removeprefix("v"))
    notes_path = Path(os.environ["NOTES_PATH"])

    notes: str | None = None
    path = changelog_path(root, package)
    if path.is_file():
        notes = extract_notes(path.read_text(), version)
    if not notes:
        notes = f"Release of {package} {version}."
    notes_path.write_text(notes + "\n")


def main() -> None:
    """Dispatch to the subcommand named by the first CLI argument."""
    commands = {
        "detect": cmd_detect,
        "plan": cmd_plan,
        "materialize": cmd_materialize,
        "prepare-publish": cmd_prepare_publish,
        "pin-reflex-base": cmd_pin_reflex_base,
        "verify-dist": cmd_verify_dist,
        "extract-notes": cmd_extract_notes,
        "check-headings": cmd_check_headings,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        fail(f"usage: release.py {{{','.join(commands)}}}")
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
