"""Parsing and rewriting of towncrier-generated ``CHANGELOG.md`` files.

The changelogs are the source of truth for publishing, so exactly one parser
recognizes version headings: the pull-request guard, the publish validation and
the release-notes extraction all go through this module and therefore cannot
disagree about what counts as a release.
"""

from __future__ import annotations

import dataclasses
import re
import sys

from packaging.version import InvalidVersion, Version

from .actions import fail

NO_SIGNIFICANT_CHANGES = "No significant changes"

DEFAULT_TITLE_FORMAT = "## {version} ({project_date})"

_HEADING_RE = re.compile(r"^(?P<label>.*?)(?:\s+\((?P<date>[^()]*)\))?\s*$")


@dataclasses.dataclass(frozen=True)
class Section:
    """One ``## <version> (<date>)`` section of a towncrier changelog.

    Attributes:
        label: The heading text without the ``## `` prefix or date suffix.
        date: The parenthesized date portion of the heading, if any.
        version: The parsed version, or None for unversioned headings.
        body: Everything below the heading, up to the next one.
        raw: The heading and body verbatim.
    """

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
        first ``## `` heading.
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


def render_heading(title_format: str, version: str, date_str: str) -> str:
    """Render a section heading the way towncrier would.

    Args:
        title_format: The configured ``title_format``.
        version: The version as it appears in headings (``v1.2.3``).
        date_str: The release date (YYYY-MM-DD).

    Returns:
        The heading line, without a trailing newline.
    """
    return title_format.format(name="", version=version, project_date=date_str).strip()


def collapse_prereleases(
    text: str,
    final_version: Version,
    date_str: str,
    category_order: list[str],
    title_format: str = DEFAULT_TITLE_FORMAT,
) -> str:
    """Collapse the top prerelease sections into a single final section.

    Merges the section for ``final_version`` (freshly written by towncrier from
    any remaining fragments) together with every consecutive prerelease section
    at the top of the changelog into one section, concatenating each category's
    entries oldest-first. "No significant changes." placeholders are dropped
    unless nothing else remains.

    Args:
        text: The changelog markdown.
        final_version: The final version being released.
        date_str: The date for the new section heading (YYYY-MM-DD).
        category_order: Category names in canonical display order.
        title_format: The towncrier ``title_format`` to render the heading with.

    Returns:
        The rewritten changelog markdown.

    Raises:
        ReleaseError: When the changelog has no prerelease sections to collapse.
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

    parts: list[str] = [render_heading(title_format, f"v{final_version}", date_str), ""]
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
