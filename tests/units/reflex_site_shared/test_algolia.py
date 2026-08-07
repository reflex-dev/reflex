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
