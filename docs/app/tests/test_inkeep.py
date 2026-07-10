"""Tests for the lazy-loaded Inkeep search control."""

import re

from reflex_docs.views.inkeep import _HOTKEY_AND_HINT_HOOK, Search


def _has_prop(component: dict, prop: str) -> bool:
    """Check whether a rendered component has an exact prop.

    Args:
        component: Rendered Reflex component dictionary.
        prop: Serialized prop to find.

    Returns:
        Whether the component contains the prop.
    """
    return prop in component.get("props", [])


def test_search_keeps_local_state_in_one_memo_boundary():
    """Keep the local state hooks and their consumers in the same JS component."""
    assert not Search.create()._memoization_mode.recursive


def test_search_placeholder_stays_mounted_until_shadow_host_exists():
    """Keep the placeholder visible until Inkeep's shadow host mounts."""
    search = Search.create()
    rendered = search.render()
    placeholder = next(
        (
            child
            for child in rendered["children"]
            if child.get("name") == '"button"'
            and _has_prop(child, 'id:"inkeep-search-trigger"')
        ),
        None,
    )

    assert placeholder is not None
    global_css = "\n".join(
        nested["contents"]
        for child in rendered["children"]
        if child.get("name") == '"style"'
        for nested in child.get("children", [])
    )
    assert (
        "#inkeep-search-wrapper:has(> [id^='inkeep-shadow']) > #inkeep-search-trigger"
    ) in global_css
    assert "[id^='inkeep-shadow']" in _HOTKEY_AND_HINT_HOOK
    assert ".ikp-search-bar__container" not in _HOTKEY_AND_HINT_HOOK


def test_search_widget_kbd_hint_matches_placeholder():
    """Keep the widget's kbd hint visually identical to the placeholder's.

    Inkeep's base styles give the inner <kbd> keys a monospace font stack, so
    the hint visibly changes font (and width) when the real widget replaces
    the placeholder unless the keys inherit the wrapper's font.
    """
    styles = "\n".join(Search.create().add_hooks())
    assert re.search(
        r"\.ikp-search-bar__kbd-wrapper kbd\s*\{[^{}]*font:\s*inherit", styles
    )
    # The hook targets the placeholder's first key span to swap ⌘ for Ctrl.
    assert 'querySelector("kbd > span")' in _HOTKEY_AND_HINT_HOOK


def test_search_widget_dark_colors_match_placeholder():
    """Override Inkeep's higher-specificity dark colors with the placeholder color."""
    styles = "\n".join(Search.create().add_hooks())

    for selector in (
        ".ikp-search-bar__text",
        ".ikp-search-bar__icon",
        ".ikp-search-bar__kbd-wrapper",
    ):
        assert re.search(
            rf"\[data-theme='dark'\] {re.escape(selector)}[^{{}}]*"
            r"\{[^{}]*color:\s*var\(--secondary-11\)",
            styles,
        )
