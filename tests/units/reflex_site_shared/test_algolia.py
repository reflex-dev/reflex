"""Tests for the shared keyword-only Algolia search."""

from pathlib import Path

from reflex_site_shared.components.algolia import AlgoliaSearch, Search
from reflex_site_shared.plugins import SharedSiteStylesPlugin


def test_algolia_search_uses_local_keyword_only_component() -> None:
    """Use the local Algolia UI without shipping an AI search dependency."""
    assert AlgoliaSearch.library == "$/public/components/AlgoliaSearch"
    assert AlgoliaSearch.tag == "AlgoliaSearch"
    assert AlgoliaSearch.lib_dependencies == [
        "@hugeicons/react",
        "@hugeicons/core-free-icons",
    ]
    assert Search.create().children[0].library == AlgoliaSearch.library


def test_algolia_search_asset_is_published_and_non_ai() -> None:
    """Publish the search client with the production index and no AI hooks."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'ALGOLIA_APP_ID = "WLK9YABRW4"' in source
    assert 'ALGOLIA_SEARCH_API_KEY = "7abb638647d3aa25e7a6d29dfdca2212"' in source
    assert "aa0ebd175fcfb78706a053e5e71f6b58" not in source
    assert 'ALGOLIA_INDEX_NAME = "reflex_dev_wlk9yabrw4_pages"' in source
    assert "const SEARCH_DEBOUNCE_MS = 350" in source
    assert "const MIN_QUERY_LENGTH = 2" in source
    assert "window.setTimeout" in source
    debounce_start = source.index("const controller = new AbortController()")
    assert source.rindex('setStatus("loading");', 0, debounce_start) > source.index(
        "if (cachedSearch)"
    )
    assert 'status === "loading"\n                    ? "Searching Reflex"' in source
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
        assert f'pathname.startsWith("{route}")' in source
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
    assert "buttonRef.current?.closest(ROOT_THEME_SELECTOR)" in source
    assert "document.querySelector(ROOT_THEME_SELECTOR)" in source
    assert "document.body" in source
    assert "portalRoot," in source


def test_algolia_results_use_category_specific_icons() -> None:
    """Render every search glyph with a consistent Hugeicons treatment."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "type ResultSection =" in source
    assert "function ResultIcon(" in source
    assert "const RESULT_ICONS: Record<ResultSection, IconSvgElement>" in source
    for section, icon in (
        ("XY", "ChartLineData01Icon"),
        ("Components", "ComponentIcon"),
        ('"API Reference"', "ApiIcon"),
        ("Docs", "BookOpen01Icon"),
        ("Blog", "Notebook01Icon"),
        ("Reflex", "ReflexIcon"),
    ):
        assert f"{section}: {icon}" in source

    for icon in (
        "ApiIcon",
        "ArrowRight01Icon",
        "BookOpen01Icon",
        "Cancel01Icon",
        "ChartLineData01Icon",
        "ComponentIcon",
        "CornerDownLeftIcon",
        "Notebook01Icon",
        "ReflexIcon",
        "Search01Icon",
    ):
        assert f'from "@hugeicons/core-free-icons/{icon}"' in source
    assert 'from "@hugeicons/react"' in source
    assert "HugeiconsIcon" in source
    assert "<svg" not in source
    assert "CancelCircleIcon" not in source

    hit_icon = source.split('<span className="ReflexSearch-hitIcon">', 1)[1].split(
        "</span>", 1
    )[0]
    assert "<ResultIcon section={hit.section} />" in hit_icon
    assert "<SearchIcon" not in hit_icon


def test_algolia_search_supports_looping_arrow_navigation() -> None:
    """Select results with arrows and open the active result with Enter."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "const [activeIndex, setActiveIndex] = useState(-1);" in source
    assert 'case "ArrowDown":' in source
    assert 'case "ArrowUp":' in source
    assert 'case "Enter":' in source
    assert "(current + offset + hits.length) % hits.length" in source
    assert 'scrollIntoView({ block: "nearest" })' in source
    assert "onKeyDown={handleInputKeyDown}" in source
    assert "aria-activedescendant={activeResultId}" in source
    assert "data-selected={index === activeIndex}" in source
    assert "window.location.assign(activeHit.url)" in source


def test_algolia_search_matches_reference_card_style() -> None:
    """Use the bordered result cards and selected state from the reference."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'placeholder="What are you searching for?"' in source
    assert "width: min(90vw, 720px);" in source
    assert "height: 34rem;" in source
    assert "border: 1px solid var(--secondary-a4" in source
    assert "border-radius: 0.75rem;" in source
    assert '.ReflexSearch-hit[data-selected="true"]' in source
    assert "background: var(--primary-2, #fbfaff);" in source
    assert "border-color: var(--primary-7, #c9bfff);" in source


def test_algolia_search_dialog_has_dark_mode_surface_contrast() -> None:
    """Separate the dark dialog from the dimmed page with solid surface tokens."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    dark_dialog_styles = source.split(
        '.dark .ReflexSearch-dialog,\n  [data-theme="dark"] .ReflexSearch-dialog {',
        1,
    )[1].split("}", 1)[0]
    assert "background: var(--secondary-4, #1e2025);" in dark_dialog_styles
    assert "border-color: var(--secondary-7, #363c44);" in dark_dialog_styles


def test_algolia_search_dialog_has_visible_dark_mode_separators() -> None:
    """Separate populated dark search input, content, and footer regions."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    dark_input_separator = source.split(
        '.dark .ReflexSearch-dialog[data-results-visible="true"] '
        ".ReflexSearch-inputRow,",
        1,
    )[1].split("}", 1)[0]
    dark_footer_separator = source.split(".dark .ReflexSearch-footer,", 1)[1].split(
        "}", 1
    )[0]
    assert "border-bottom-color: var(--secondary-7, #363c44);" in dark_input_separator
    assert "border-top-color: var(--secondary-7, #363c44);" in dark_footer_separator


def test_algolia_search_input_uses_medium_typography() -> None:
    """Keep entered search text and its placeholder legible at medium weight."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    input_styles = source.split(".ReflexSearch-input {", 1)[1].split("}", 1)[0]
    placeholder_styles = source.split(".ReflexSearch-input::placeholder {", 1)[1].split(
        "}", 1
    )[0]
    assert "font: 500 1rem/1.5rem" in input_styles
    assert "font-weight: 500;" in placeholder_styles


def test_algolia_search_uses_compact_result_cards() -> None:
    """Keep result cards dense enough for a command-style search surface."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    hit_list_styles = source.split(".ReflexSearch-hitList {", 1)[1].split("}", 1)[0]
    hit_styles = source.split(".ReflexSearch-hit {", 1)[1].split("}", 1)[0]
    breadcrumb_styles = source.split(".ReflexSearch-hitBreadcrumbs {", 1)[1].split(
        "}", 1
    )[0]
    title_styles = source.split(".ReflexSearch-hitTitleRow strong {", 1)[1].split(
        "}", 1
    )[0]
    description_styles = source.split(".ReflexSearch-hitDescription {", 1)[1].split(
        "}", 1
    )[0]

    assert "gap: 0.625rem;" in hit_list_styles
    assert "gap: 0.375rem;" in hit_styles
    assert "min-height: 5.5rem;" in hit_styles
    assert "padding: 0.75rem 1rem;" in hit_styles
    assert "font-size: 0.75rem;" in breadcrumb_styles
    assert "line-height: 1.125rem;" in breadcrumb_styles
    assert "font-size: 1rem;" in title_styles
    assert "line-height: 1.5rem;" in title_styles
    assert "font-size: 0.875rem;" in description_styles
    assert "line-height: 1.25rem;" in description_styles


def test_algolia_search_uses_input_only_orbit_loading_state() -> None:
    """Show the pixel orbit only inside the input while loading."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3];" in source
    assert "const ORBIT_DELAYS = Array.from({ length: 9 }" in source
    assert "return order === -1 ? null : order * 110;" in source
    assert "function LoadingState()" in source
    assert source.count("<LoadingState />") == 1
    assert "Loading03Icon" not in source
    assert 'data-tone="loading"' not in source
    assert 'data-size="large"' not in source
    assert "@keyframes loading-state-pixel-on" in source
    assert "loading-state-pixel-on 950ms ease-in-out" in source
    assert ".ReflexSearch-loadingCell" in source
    reduced_motion = source.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert ".ReflexSearch-loadingCell" in reduced_motion
    assert "animation: none !important;" in reduced_motion


def test_algolia_search_preserves_populated_results_while_loading() -> None:
    """Keep existing cards visible but inert during a replacement request."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    loading_setup = source.split("const controller = new AbortController()", 1)[
        0
    ].rsplit("return;\n    }", 1)[1]
    assert "setHits([]);" not in loading_setup
    assert "setNbHits(0);" not in loading_setup
    assert 'setStatus("loading");' in loading_setup

    show_results = source.split("const showResults =", 1)[1].split(";", 1)[0]
    assert 'status !== "idle"' in show_results
    assert 'status !== "loading" || hits.length > 0' in show_results
    assert "{showResults ? (" in source
    results = source.split(
        'className="ReflexSearch-results scroll-mask-y-10 overscroll-none"', 1
    )[1].split("<footer", 1)[0]
    assert 'data-tone="loading"' not in results
    assert 'className="ReflexSearch-hitList"' in results
    assert 'const [resultsQuery, setResultsQuery] = useState("");' in source
    assert 'status === "ready" &&' in source
    assert "resultsQuery === query.trim().toLocaleLowerCase()" in source
    assert "data-interactive={resultsAreInteractive}" in results
    assert "aria-disabled={!resultsAreInteractive}" in results
    assert "if (!resultsAreInteractive)" in results
    assert "event.preventDefault();" in results

    move_selection = source.split("const moveSelection =", 1)[1].split(
        "const handleInputKeyDown =", 1
    )[0]
    assert "!resultsAreInteractive || hits.length === 0" in move_selection

    inert_styles = source.split('.ReflexSearch-hitList[data-interactive="false"] {', 1)[
        1
    ].split("}", 1)[0]
    assert "pointer-events: none;" in inert_styles

    input_row = source.split('<div className="ReflexSearch-inputRow">', 1)[1].split(
        "</div>", 1
    )[0]
    action_group_styles = source.split(".ReflexSearch-actions {", 1)[1].split("}", 1)[0]
    assert '<span className="ReflexSearch-actions">' in input_row
    assert "display: grid;" in action_group_styles
    assert "grid-template-columns: 1.75rem 2.5rem;" in action_group_styles
    assert "gap: 0.375rem;" in action_group_styles
    assert 'status === "loading" ? <LoadingState /> : null' in input_row
    assert input_row.index('className="ReflexSearch-actionSlot"') < input_row.index(
        'aria-label="Close search"'
    )


def test_algolia_search_dialog_uses_accessible_entrance_motion() -> None:
    """Scale in the dialog without overriding reduced-motion preferences."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "animation: ReflexSearch-dialog-enter 180ms" in source
    assert "cubic-bezier(0.32, 0.72, 0, 1) both;" in source
    assert "transform-origin: top center;" in source
    assert "@keyframes ReflexSearch-dialog-enter" in source
    assert "transform: scale(0.96);" in source
    assert "transform: scale(1);" in source
    reduced_motion = source.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert ".ReflexSearch-dialog" in reduced_motion
    assert "animation: none;" in reduced_motion


def test_algolia_search_uses_polished_status_states() -> None:
    """Keep empty, loading, error, and no-result states visually consistent."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'from "@hugeicons/core-free-icons/Alert02Icon"' in source
    assert "SearchMinusIcon" not in source
    assert "Searching Reflex" in source
    assert "Search couldn\u2019t load" in source  # codespell:ignore
    assert "Try a broader term, check the spelling" not in source
    assert "or use fewer" not in source
    assert 'data-tone="error"' in source
    neutral_state = source.split('data-tone="neutral"', 1)[1].split("</div>", 1)[0]
    assert "ReflexSearch-emptyIcon" not in neutral_state
    assert "<p>" not in neutral_state
    assert "No results for" in neutral_state
    assert "data-populated={hits.length > 0}" in source
    assert '.ReflexSearch-results[data-populated="false"]' in source
    assert "height: 20rem;" in source
    assert "font-size: 1.125rem;" in source
    assert "font-weight: 500;" in source
    assert "max-width: 32rem;" in source
    assert "text-wrap: pretty;" in source
    assert "Keyword search" not in source


def test_algolia_search_contains_the_scrollable_card_list() -> None:
    """Fade card edges and prevent scroll chaining from the results viewport."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert 'className="ReflexSearch-results scroll-mask-y-10 overscroll-none"' in source
    assert "overscroll-behavior: contain;" not in source


def test_algolia_search_collapses_empty_dialog_to_input() -> None:
    """Collapse empty idle and loading states without changing row geometry."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert source.count("data-status={status}") == 2
    assert "{showResults ? (" in source
    assert "data-results-visible={showResults}" in source
    assert 'className="ReflexSearch-visuallyHidden ReflexSearch-liveStatus"' in source
    assert 'aria-live="polite"' in source
    assert (
        '.ReflexSearch-dialog[data-results-visible="false"] .ReflexSearch-inputRow'
        in source
    )
    idle_row_styles = source.split(
        '.ReflexSearch-dialog[data-results-visible="false"] .ReflexSearch-inputRow {',
        1,
    )[1].split("}", 1)[0]
    assert "border-bottom-color: transparent;" in idle_row_styles
    assert "border-bottom: 0;" not in idle_row_styles


def test_algolia_search_row_stays_stable_while_typing() -> None:
    """Reserve control space and keep the input row at a fixed outer height."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    input_row_styles = source.split(".ReflexSearch-inputRow {", 1)[1].split("}", 1)[0]
    action_slot_styles = source.split(".ReflexSearch-actionSlot {", 1)[1].split("}", 1)[
        0
    ]
    input_row = source.split('<div className="ReflexSearch-inputRow">', 1)[1].split(
        '<button\n                    aria-label="Close search"', 1
    )[0]

    assert "box-sizing: border-box;" in input_row_styles
    assert "height: 3rem;" in input_row_styles
    assert "min-height: 3rem;" in input_row_styles
    assert "flex: 0 0 1.75rem;" in action_slot_styles
    assert "height: 1.75rem;" in action_slot_styles
    assert '<span className="ReflexSearch-actionSlot">' in input_row
    assert 'status === "loading" ? <LoadingState /> : null' in input_row
    assert "<LoadingState />" in input_row
    assert 'aria-label="Clear search"' not in source
    assert "ReflexSearch-iconButton" not in source


def test_algolia_search_input_row_contains_safari_search_input() -> None:
    """Keep Safari's native search input from moving or clipping the actions."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    input_row_styles = source.split(".ReflexSearch-inputRow {", 1)[1].split("}", 1)[0]
    input_styles = source.split(".ReflexSearch-input {", 1)[1].split("}", 1)[0]
    action_styles = source.split(".ReflexSearch-actions {", 1)[1].split("}", 1)[0]
    escape_styles = source.split(".ReflexSearch-escape {", 1)[1].split("}", 1)[0]

    assert "display: flex;" in input_row_styles
    assert "flex: 1 1 0%;" in input_styles
    assert "width: 0;" in input_styles
    assert "display: grid;" in action_styles
    assert "flex: 0 0 auto;" in action_styles
    assert "grid-template-columns: 1.75rem 2.5rem;" in action_styles
    assert "align-self: center;" in action_styles
    assert "position: static;" in action_styles
    assert "right: auto;" in action_styles
    assert "top: auto;" in action_styles
    assert "transform: none;" in action_styles
    assert "width: 2.5rem;" in escape_styles

    mobile_styles = source.split("@media (max-width: 40rem)", 1)[1].split(
        "@media (prefers-reduced-motion: reduce)", 1
    )[0]
    mobile_actions = mobile_styles.split(".ReflexSearch-actions {", 1)[1].split("}", 1)[
        0
    ]
    assert "grid-template-columns: 2.25rem 2.25rem;" in mobile_actions


def test_algolia_search_builds_result_breadcrumbs() -> None:
    """Render docs hierarchy from canonical URLs instead of indexed headings."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "breadcrumbs: string[];" in source
    assert "function resultBreadcrumbs(" in source
    assert 'section === "Blog" ? "Blogs" : section' in source
    assert "RESULT_PATH_PREFIXES" in source
    assert 'Docs: ["docs"]' in source
    assert 'Components: ["docs", "library"]' in source
    assert 'XY: ["docs", "xy"]' in source
    assert '"API Reference": ["docs", "api-reference"]' in source
    assert "RESULT_PATH_LABELS" in source
    assert 'ai: "AI"' in source
    assert "function normalizeResultUrl(hit: AlgoliaHit): URL | null" in source
    assert "function resultSection(pathname: string)" in source
    assert "function resultPathBreadcrumbs(" in source
    assert 'pathname.split("/").filter(Boolean)' in source
    assert ".slice(prefix.length, -1)" in source
    assert ".map(resultPathLabel)" in source
    assert "breadcrumb.toLowerCase() !== normalizedRoot" in source
    assert "const url = normalizedUrl.toString();" in source
    assert "const pathname = normalizedUrl.pathname;" in source
    assert "breadcrumbs: resultBreadcrumbs(pathname, section)" in source
    assert 'className="ReflexSearch-hitBreadcrumbs"' in source
    assert "hit.breadcrumbs.map((breadcrumb, index)" in source
    assert "icon={ArrowRight01Icon}" in source
    assert "(hit.headers ?? []).slice(0, 2)" not in source
    assert "<mark" not in source
    assert "font-size: 1.125rem;" in source


def test_algolia_navbar_button_matches_origin_main() -> None:
    """Preserve the original navbar search trigger styling."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "padding: 0.375rem 0.5rem;" in source
    assert "0 1px 2px 0 rgba(0, 0, 0, 0.02)" in source
    assert "0 1px 4px 0 rgba(0, 0, 0, 0.02)" in source
    assert "transition: none;" in source
    assert "width: 10rem;" in source
    assert "max-width: 10rem;" in source
    assert "padding: 0 0.25rem;" in source
    assert "background: var(--secondary-3, #f0f0f3);" in source
    assert "font-size: 0.8125rem;" in source
    assert "font-weight: 475;" in source
    assert "height: 1.25rem;" in source

    collapsed_navbar = source.split("@media (max-width: 80em)", 1)[1].split(
        "@media (max-width: 40rem)", 1
    )[0]
    collapsed_icon = collapsed_navbar.split(".ReflexSearch-button > svg {", 1)[1].split(
        "}", 1
    )[0]
    assert "flex-shrink: 0;" in collapsed_icon
    assert "height: 1.25rem;" in collapsed_icon
    assert "margin-right: 0;" in collapsed_icon
    assert "width: 1.25rem;" in collapsed_icon


def test_algolia_search_escape_matches_navbar_keycap_style() -> None:
    """Render the escape control with the navbar keycap styling."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert '<span className="ReflexSearch-escapeText">ESC</span>' in source
    escape_styles = source.split(".ReflexSearch-escape {", 1)[1].split("}", 1)[0]
    assert "align-items: center;" in escape_styles
    assert "background: var(--c-white-1, #fff);" in escape_styles
    assert "border: 1px solid var(--secondary-4, #e8e8e8);" in escape_styles
    assert "border-radius: 0.375rem;" in escape_styles
    assert "color: var(--secondary-11, #646464);" in escape_styles
    assert "display: flex;" in escape_styles
    assert "flex-shrink: 0;" in escape_styles
    assert "font: 475 0.75rem/1rem" in escape_styles
    assert "gap: 0.25rem;" in escape_styles
    assert "height: 1.5rem;" in escape_styles
    assert "padding: 0 0.375rem;" in escape_styles
    assert 'className="ReflexSearch-escapeIcon"' in source
    assert "icon={Cancel01Icon}" in source

    mobile_styles = source.split("@media (max-width: 40rem)", 1)[1].split(
        "@media (prefers-reduced-motion: reduce)", 1
    )[0]
    mobile_escape = mobile_styles.split(".ReflexSearch-escape {", 1)[1].split("}", 1)[0]
    assert "border-radius: 0.625rem;" in mobile_escape
    assert "height: 2.25rem;" in mobile_escape
    assert "width: 2.25rem;" in mobile_escape
    assert "position: static;" in mobile_escape
    assert "clip: rect(0 0 0 0);" not in mobile_escape
    assert (
        "display: none;"
        in mobile_styles.split(".ReflexSearch-escapeText {", 1)[1].split("}", 1)[0]
    )
    assert (
        "display: block;"
        in mobile_styles.split(".ReflexSearch-escapeIcon {", 1)[1].split("}", 1)[0]
    )


def test_algolia_mobile_dialog_respects_safe_area_offset() -> None:
    """Offset the mobile dialog without extending it past the viewport."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    mobile_styles = source.split("@media (max-width: 40rem)", 1)[1].split(
        "@media (prefers-reduced-motion: reduce)", 1
    )[0]
    overlay_styles = mobile_styles.split(".ReflexSearch-overlay {", 1)[1].split("}", 1)[
        0
    ]
    dialog_styles = mobile_styles.split(".ReflexSearch-dialog {", 1)[1].split("}", 1)[0]
    input_icon_styles = mobile_styles.split(".ReflexSearch-inputIcon > svg {", 1)[
        1
    ].split("}", 1)[0]
    assert "padding: calc(env(safe-area-inset-top, 0px) + 1.5rem) 1rem 1rem;" in (
        overlay_styles
    )
    assert (
        "height: calc(100dvh - env(safe-area-inset-top, 0px) - 2.5rem);"
        in dialog_styles
    )
    assert "border-radius: 0.75rem;" in dialog_styles
    assert "height: 1.375rem;" in input_icon_styles
    assert "width: 1.375rem;" in input_icon_styles


def test_algolia_search_resets_transient_ui_state() -> None:
    """Reset transient state when closing the search dialog."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    close_search = source.split("const closeSearch =", 1)[1].split(
        "const moveSelection =", 1
    )[0]

    assert "resetSearch();" in close_search
    assert "const clearSearch =" not in source
    assert "requestRef.current?.abort();" in source


def test_algolia_search_precomputes_result_metadata() -> None:
    """Avoid reparsing every result URL during each React render."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    normalize_hits = source.split("function normalizeHits(", 1)[1].split(
        "function ResultIcon(", 1
    )[0]
    rendered_results = source.split('className="ReflexSearch-hitList"', 1)[1].split(
        "</ul>", 1
    )[0]

    assert "const section = resultSection(pathname)" in normalize_hits
    assert normalize_hits.count("new URL(") == 0
    assert "const displayTitle = resultTitle(hit)" in normalize_hits
    assert "section," in normalize_hits
    assert "displayTitle," in normalize_hits
    assert "hit.section" in rendered_results
    assert "hit.displayTitle" in rendered_results
    assert "resultSection(hit.url)" not in rendered_results


def test_algolia_search_only_resolves_portal_while_open() -> None:
    """Resolve the portal target once per open dialog, not on every render."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    assert "useMemo" in source
    portal_root = source.split("const portalRoot = useMemo(", 1)[1].split(
        "const activeResultId", 1
    )[0]
    assert 'if (!isOpen || typeof document === "undefined")' in portal_root
    assert "buttonRef.current?.closest(ROOT_THEME_SELECTOR)" in portal_root
    assert "}, [isOpen]);" in portal_root


def test_algolia_search_cleans_up_settled_and_aborted_requests() -> None:
    """Treat every aborted request as stale and release settled controllers."""
    assets = dict(SharedSiteStylesPlugin().get_static_assets())
    source = assets[Path("public/components/AlgoliaSearch.tsx")]

    request = source.split("const timer = window.setTimeout", 1)[1].split(
        "}, SEARCH_DEBOUNCE_MS);", 1
    )[0]
    catch = request.split("} catch", 1)[1]
    assert "if (controller.signal.aborted)" in catch
    assert "error instanceof DOMException" not in catch
    assert "finally" in request
    assert "requestRef.current === controller" in request.split("finally", 1)[1]
