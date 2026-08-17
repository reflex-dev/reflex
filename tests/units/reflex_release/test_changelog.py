"""Tests for reflex_release.changelog."""

from __future__ import annotations

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.changelog import (
    collapse_prereleases,
    extract_notes,
    heading_version,
    latest_version,
    parse_sections,
    render_heading,
    split_categories,
)

CHANGELOG = """\
## v1.1.0 (2026-02-02)

### Features

- Something new. (#2)

## v1.0.0 (2026-01-01)

### Bug Fixes

- Something fixed. (#1)
"""

CATEGORIES = ["Breaking Changes", "Features", "Bug Fixes"]


def test_parse_sections() -> None:
    preamble, sections = parse_sections(CHANGELOG)
    assert preamble == ""
    assert [section.label for section in sections] == ["v1.1.0", "v1.0.0"]
    assert [section.date for section in sections] == ["2026-02-02", "2026-01-01"]
    assert sections[0].version == Version("1.1.0")


def test_parse_sections_keeps_preamble() -> None:
    preamble, sections = parse_sections("# Changelog\n\nintro\n\n" + CHANGELOG)
    assert preamble == "# Changelog\n\nintro\n\n"
    assert len(sections) == 2


def test_parse_sections_without_headings() -> None:
    assert parse_sections("just text\n") == ("just text\n", [])


@pytest.mark.parametrize(
    ("label", "date", "expected"),
    [
        ("v1.2.3", "2026-01-01", Version("1.2.3")),
        ("1.2.3", None, Version("1.2.3")),
        ("v1.2.3a1", "2026-01-01", Version("1.2.3a1")),
        ("Unreleased", None, None),
        ("v1.2.3", "unreleased", None),
        ("Some heading", None, None),
    ],
)
def test_heading_version(
    label: str, date: str | None, expected: Version | None
) -> None:
    assert heading_version(label, date) == expected


def test_latest_version_skips_unreleased() -> None:
    assert latest_version("## Unreleased\n\ntbd\n\n" + CHANGELOG) == Version("1.1.0")
    assert latest_version("no headings") is None


def test_extract_notes() -> None:
    assert (
        extract_notes(CHANGELOG, Version("1.0.0"))
        == "### Bug Fixes\n\n- Something fixed. (#1)"
    )
    assert extract_notes(CHANGELOG, Version("9.9.9")) is None


def test_split_categories() -> None:
    lead, categories = split_categories(
        "intro text\n\n### Features\n\n- a\n\n### Bug Fixes\n\n- b\n"
    )
    assert lead == "intro text\n\n"
    assert [name for name, _ in categories] == ["Features", "Bug Fixes"]


def test_render_heading_uses_towncrier_format() -> None:
    assert render_heading("## {version} ({project_date})", "v1.0.0", "2026-01-01") == (
        "## v1.0.0 (2026-01-01)"
    )
    assert render_heading(
        "## Release {version} on {project_date}", "v1.0.0", "2026-01-01"
    ) == ("## Release v1.0.0 on 2026-01-01")
    # Same substitution towncrier performs, including its empty {name}.
    assert render_heading("## {name} {version}", "v1.0.0", "2026-01-01") == "##  v1.0.0"


def test_collapse_merges_alpha_sections_oldest_first() -> None:
    text = """\
## v1.1.0 (2026-03-03)

No significant changes.

## v1.1.0a2 (2026-02-02)

### Features

- Second feature. (#2)

### Bug Fixes

- A fix. (#3)

## v1.1.0a1 (2026-01-01)

### Features

- First feature. (#1)

## v1.0.0 (2025-12-12)

### Features

- Old. (#0)
"""
    result = collapse_prereleases(text, Version("1.1.0"), "2026-03-03", CATEGORIES)
    assert (
        result
        == """\
## v1.1.0 (2026-03-03)

### Features

- First feature. (#1)
- Second feature. (#2)

### Bug Fixes

- A fix. (#3)


## v1.0.0 (2025-12-12)

### Features

- Old. (#0)
"""
    )


def test_collapse_keeps_categories_in_configured_order() -> None:
    text = """\
## v2.0.0 (2026-03-03)

### Bug Fixes

- Late fix. (#9)

## v2.0.0a1 (2026-01-01)

### Breaking Changes

- Removed a thing. (#8)
"""
    result = collapse_prereleases(text, Version("2.0.0"), "2026-03-03", CATEGORIES)
    assert result.index("### Breaking Changes") < result.index("### Bug Fixes")


def test_collapse_preserves_unknown_categories() -> None:
    text = """\
## v1.0.0 (2026-03-03)

### Sponsors

- Thanks. (#1)

## v1.0.0a1 (2026-01-01)

### Features

- A feature. (#2)
"""
    result = collapse_prereleases(text, Version("1.0.0"), "2026-03-03", CATEGORIES)
    assert result.index("### Features") < result.index("### Sponsors")


def test_collapse_of_empty_train_keeps_placeholder() -> None:
    text = """\
## v1.0.1 (2026-03-03)

No significant changes.

## v1.0.1a1 (2026-01-01)

No significant changes.
"""
    result = collapse_prereleases(text, Version("1.0.1"), "2026-03-03", CATEGORIES)
    assert result == "## v1.0.1 (2026-03-03)\n\nNo significant changes.\n"


def test_collapse_leaves_non_contiguous_prereleases_alone(
    capsys: pytest.CaptureFixture,
) -> None:
    text = """\
## v2.0.0 (2026-03-03)

### Features

- New. (#2)

## v1.0.0 (2026-01-01)

### Features

- Old. (#1)

## v1.0.0a1 (2025-12-12)

### Features

- Older. (#0)
"""
    result = collapse_prereleases(text, Version("2.0.0"), "2026-03-03", CATEGORIES)
    assert "## v1.0.0a1 (2025-12-12)" in result
    assert "not contiguous" in capsys.readouterr().err


def test_collapse_without_prereleases_fails() -> None:
    with pytest.raises(ReleaseError, match="no prerelease sections"):
        collapse_prereleases(CHANGELOG, Version("2.0.0"), "2026-03-03", CATEGORIES)


def test_collapse_honors_custom_title_format() -> None:
    text = "## v1.0.0 (2026-03-03)\n\nNo significant changes.\n\n## v1.0.0a1 (2026-01-01)\n\nNo significant changes.\n"
    result = collapse_prereleases(
        text,
        Version("1.0.0"),
        "2026-03-03",
        CATEGORIES,
        "## Release {version} — {project_date}",
    )
    assert result.startswith("## Release v1.0.0 — 2026-03-03")
