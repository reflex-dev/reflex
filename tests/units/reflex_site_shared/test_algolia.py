"""Tests for the shared keyword-only Algolia search."""

from pathlib import Path

from reflex_site_shared.components.algolia import AlgoliaSearch, Search
from reflex_site_shared.plugins import SharedSiteStylesPlugin


def test_algolia_search_uses_local_keyword_only_component() -> None:
    """Use the local Algolia UI without shipping an AI search dependency."""
    assert AlgoliaSearch.library == "$/public/components/AlgoliaSearch"
    assert AlgoliaSearch.tag == "AlgoliaSearch"
    assert Search.create().children[0].library == AlgoliaSearch.library


def test_algolia_search_asset_is_published_and_non_ai() -> None:
    """Publish the search client with the production index and no AI hooks."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'ALGOLIA_APP_ID = "WLK9YABRW4"' in source
    assert 'ALGOLIA_INDEX_NAME = "reflex_dev_wlk9yabrw4_pages"' in source
    assert "const SEARCH_DEBOUNCE_MS = 350" in source
    assert "const MIN_QUERY_LENGTH = 2" in source
    assert "window.setTimeout" in source
    debounce_start = source.index("const controller = new AbortController()")
    assert source.rindex("setHits([]);", 0, debounce_start) > source.index(
        "if (cachedSearch)"
    )
    assert source.rindex('setStatus("loading");', 0, debounce_start) > source.index(
        "if (cachedSearch)"
    )
    assert "<strong>Searching…</strong>" in source
    assert "/query" in source
    assert "href={hit.url}" in source
    assert "analytics: false" in source
    assert "clickAnalytics: false" in source
    assert "enablePersonalization: false" in source

    for route, section in (
        ("/docs/xy/", "XY"),
        ("/docs/library/", "Components"),
        ("/docs/api-reference/", "API Reference"),
        ("/docs/", "Docs"),
        ("/blog/", "Blog"),
    ):
        assert f'path.startsWith("{route}")' in source
        assert f'return "{section}"' in source
    assert 'return "Reflex"' in source

    normalized_source = source.casefold()
    assert "askai" not in normalized_source
    assert "openai" not in normalized_source
    assert "chatcompletion" not in normalized_source


def test_algolia_dialog_escapes_the_filtered_navbar_stacking_context() -> None:
    """Portal the overlay outside the navbar without escaping the active theme."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'import { createPortal } from "react-dom"' in source
    assert "createPortal(" in source
    assert (
        "ROOT_THEME_SELECTOR = '.radix-themes[data-is-root-theme=\"true\"]'" in source
    )
    assert (
        "buttonRef.current?.closest(ROOT_THEME_SELECTOR) ??\n"
        "        document.querySelector(ROOT_THEME_SELECTOR) ??\n"
        "        document.body"
    ) in source
    assert "portalRoot," in source


def test_algolia_results_use_category_specific_icons() -> None:
    """Render a distinct decorative icon for every result section."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "type ResultSection =" in source
    assert "function ResultIcon(" in source
    sections = ("XY", "Components", "API Reference", "Docs", "Blog", "Reflex")
    for section in sections:
        assert f'case "{section}":' in source

    result_icon = source.split("function ResultIcon(", 1)[1].split(
        "function CloseIcon(", 1
    )[0]
    svg_tag = result_icon.split("<svg", 1)[1].split(">", 1)[0]
    for attribute in (
        'aria-hidden="true"',
        "data-section=",
        'fill="none"',
        'focusable="false"',
        'height="18"',
        'stroke="currentColor"',
        'viewBox="0 0 24 24"',
        'width="18"',
    ):
        assert attribute in svg_tag
    assert "aria-label" not in svg_tag
    assert "<title" not in result_icon
    assert "return assertNever(section)" in result_icon

    case_offsets = [result_icon.index(f'case "{section}":') for section in sections]
    switch_end = result_icon.index("\n  }\n\n  return (")
    glyphs = []
    for index, offset in enumerate(case_offsets):
        glyph_start = offset + len(f'case "{sections[index]}":')
        glyph_end = (
            case_offsets[index + 1] if index + 1 < len(case_offsets) else switch_end
        )
        glyphs.append("".join(result_icon[glyph_start:glyph_end].split()))
    assert len(set(glyphs)) == len(sections)

    hit_icon = source.split('<span className="ReflexSearch-hitIcon">', 1)[1].split(
        "</span>", 1
    )[0]
    assert "<ResultIcon section={resultSection(hit.url)} />" in hit_icon
    assert "<SearchIcon" not in hit_icon
    assert (
        "{resultSection(hit.url)}"
        in source.split('<span className="ReflexSearch-hitMeta">', 1)[1].split(
            "</span>", 1
        )[0]
    )
