# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "packaging>=24.2",
#     "towncrier>=24.8",
#     "tomli>=2; python_version < '3.11'",
# ]
# ///
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
  Used by the ``release_from_changelog`` workflow on every push to ``main`` and
  ``r/**`` branches. Final (non-prerelease) versions are only released from
  ``main`` or ``r/hotfix/**`` branches.
- ``plan``: compute the next version for each selected package for a release
  action (``new-prerelease-patch``, ``continued-prerelease``,
  ``release-from-prerelease``, ``release-major``, ...).
- ``materialize``: write the planned versions into the changelogs with
  towncrier; for ``release-from-prerelease`` also collapse the accumulated
  alpha sections into the single final-version section (alpha headings never
  appear in a published final changelog).
- ``prepare-publish``: validate a (package, version) pair against the
  changelog, the branch rules and existing tags, and emit build metadata for
  the publish workflow.
- ``extract-notes``: write the changelog section for a version to a file, for
  use as GitHub release notes.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import re
import subprocess
import sys
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


def branch_allows_final(ref_name: str) -> bool:
    """Return whether final versions may be published from a branch.

    Non-prerelease tags can only be published and pushed from ``main`` or from
    a hotfix branch like ``r/hotfix/...``.

    Args:
        ref_name: The branch name (``github.ref_name``).

    Returns:
        True when the branch may publish final versions.
    """
    return ref_name == "main" or ref_name.startswith("r/hotfix/")


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


def latest_tag_version(root: Path, package: str) -> Version | None:
    """Return the largest PEP 440 version tagged for a package.

    Args:
        root: The repository root.
        package: The package name.

    Returns:
        The largest tagged version, or None if the package has no tags.
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
    return max(versions) if versions else None


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

    if mode == "new-prerelease":
        if sub == "patch":
            return f"{major}.{minor}.{patch + 1}a1"
        if sub == "minor":
            return f"{major}.{minor + 1}.0a1"
        return f"{major + 1}.0.0a1"

    if mode == "continued-prerelease":
        if not is_alpha:
            fail(
                f"continued-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}"
            )
        return f"{major}.{minor}.{patch}a{alpha_n + 1}"

    if sub == "from-prerelease":
        if not is_alpha:
            fail(
                f"release-from-prerelease requires the newest version to be an "
                f"alpha; newest for {package} is {display!r}"
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


def cmd_detect() -> None:
    """Detect packages whose newest changelog version has no git tag.

    Reads REF_NAME from the environment; writes ``packages`` (JSON array of
    ``{package, version, tag}``) and ``any`` to ``$GITHUB_OUTPUT``.
    """
    root = REPO_ROOT
    ref_name = os.environ["REF_NAME"]
    allow_final = branch_allows_final(ref_name)

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
        if is_final(version) and not allow_final:
            notice(
                f"{package} v{version} is a final version but branch "
                f"'{ref_name}' cannot publish finals (only main and "
                "r/hotfix/** can); skipping."
            )
            rows.append(f"| `{package}` | `{version}` | skipped: branch rule |")
            continue
        releases.append({"package": package, "version": str(version), "tag": tag})
        rows.append(f"| `{package}` | `{version}` | **will publish** `{tag}` |")

    _append_lines("GITHUB_STEP_SUMMARY", rows)
    write_outputs(
        packages=json.dumps(releases),
        any="true" if releases else "false",
    )


def cmd_plan() -> None:
    """Plan the next version for each selected package.

    Reads PACKAGES_JSON and ACTION from the environment; writes ``releases``
    (JSON array of ``{package, current, next, tag}``) to ``$GITHUB_OUTPUT``.
    """
    root = REPO_ROOT
    action = os.environ["ACTION"]
    packages: list[str] = json.loads(os.environ["PACKAGES_JSON"])

    if action not in ACTIONS:
        fail(f"unknown action '{action}'")

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
        ["## Release plan", "", f"Action: `{action}`", "", *_plan_table(releases)],
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
    today = datetime.date.today().isoformat()

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

    if is_final(version) and not branch_allows_final(ref_name):
        fail(
            f"final version {version} can only be published from main or an "
            f"r/hotfix/** branch, not {ref_name!r}"
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

    tag = tag_for(package, str(version))
    skipped = tag_exists(REPO_ROOT, tag)
    if skipped:
        notice(f"tag {tag} already exists; nothing to publish.")

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
        mark_latest="true"
        if package == ROOT_PACKAGE and is_final(version)
        else "false",
        skipped="true" if skipped else "false",
    )


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
        "extract-notes": cmd_extract_notes,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        fail(f"usage: release.py {{{','.join(commands)}}}")
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
