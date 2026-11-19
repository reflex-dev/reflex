"""Shared marketing navigation behavior across consuming applications."""

import inspect
from collections.abc import Iterator
from typing import Any

from reflex_site_shared.components.docs_shell import docs_navbar_frame
from reflex_site_shared.views.announcement_banner import announcement_banner
from reflex_site_shared.views.marketing_navbar import (
    marketing_mobile_drawer,
    marketing_navbar,
)

import reflex as rx


def _walk(component: Any) -> Iterator[Any]:
    """Yield each component in a navigation tree.

    Args:
        component: Root component.

    Yields:
        Components including the root.
    """
    yield component
    for child in component.children:
        yield from _walk(child)


def test_mobile_navigation_uses_native_disclosures_and_absolute_links():
    """Make every marketing destination usable under a docs frontend path."""
    drawer = marketing_mobile_drawer()
    nodes = list(_walk(drawer))
    assert drawer.tag == "details"
    assert len([node for node in nodes if node.tag == "summary"]) >= 6
    anchors = [node for node in nodes if node.tag == "a"]
    destinations = {str(node.href).strip('"') for node in anchors}
    assert "https://reflex.dev/demo/" in destinations
    assert "https://reflex.dev/platform/" in destinations
    assert "https://reflex.dev/docs/" in destinations
    assert all(href.startswith("https://") for href in destinations)
    assert not any(node.tag == "button" for node in nodes)


def test_navbar_preserves_banner_customization():
    """Allow existing consumers to hide or replace the default announcement."""
    hidden = list(_walk(marketing_navbar(show_banner=False)))
    assert not any("data-announcement" in node.custom_attrs for node in hidden)
    custom = rx.el.div("Custom announcement", id="custom-announcement")
    nodes = list(_walk(marketing_navbar(banner=custom)))
    assert any(node is custom for node in nodes)
    assert not any("data-announcement" in node.custom_attrs for node in nodes)


def test_announcement_uses_reflex_state_and_accessible_dismissal():
    """Use a normal Reflex component with a state-backed dismissal button."""
    banner: Any = announcement_banner()
    assert banner.tag == "div"
    assert "AnnouncementVisibility" not in str(banner)
    buttons = [node for node in _walk(banner) if node.tag == "button"]
    assert len(buttons) == 1
    assert str(buttons[0].type).strip('"') == "button"
    assert "on_click" in buttons[0].event_triggers


def test_mobile_panel_is_positioned_against_full_navbar():
    """Keep library list positioning from shrinking the mobile panel to its trigger."""
    for navbar in (
        marketing_navbar(show_banner=False),
        docs_navbar_frame(rx.fragment(), rx.fragment()),
    ):
        header = next(node for node in _walk(navbar) if node.tag == "header")
        assert "[&_nav]:!static" in str(header.class_name)
        assert "[&_ul]:!static" in str(header.class_name)


def test_navigation_does_not_link_the_retired_pricing_page():
    """reflex.dev/pricing/ redirects to the demo form, so no menu offers it."""
    from reflex_site_shared.views.footer import footer_index
    from reflex_site_shared.views.sidebar import navbar_sidebar_drawer

    for root in (
        marketing_navbar(),
        marketing_mobile_drawer(),
        navbar_sidebar_drawer(rx.el.button()),
        inspect.unwrap(footer_index)(),
    ):
        hrefs = [
            str(node.href).strip('"')
            for node in _walk(root)
            if getattr(node, "href", None) is not None
        ]
        assert hrefs
        assert [href for href in hrefs if "pricing" in href] == []
