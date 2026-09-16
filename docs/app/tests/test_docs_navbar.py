"""Tests for the docs navbar links.

The docs app is served under ``frontend_path="/docs"``. ``rx.el.a`` compiles to
React Router's ``Link``, which resolves its destination against that basename;
``rx.el.elements.a`` stays a raw HTML anchor, which does not. In-app links must
therefore use the former, and links that already carry a full path (other
deployments, the marketing site) must use the latter.
"""

import pytest
import reflex as rx


@pytest.fixture
def navbar():
    """Import the navbar module through the pages package.

    Importing ``reflex_docs.views.docs_navbar`` first in a fresh interpreter
    trips a pre-existing circular import via ``reflex_docs.pages``.

    Yields:
        The ``reflex_docs.views.docs_navbar`` module.
    """
    import reflex_docs.pages  # noqa: F401
    from reflex_docs.views import docs_navbar

    yield docs_navbar


def _collect_links(component) -> list[tuple[str, str]]:
    """Walk a component tree and collect every anchor destination.

    Walks the tree rather than matching against ``str(component)``, whose repr
    is truncated for a tree this size.

    Args:
        component: The component to walk.

    Returns:
        A list of ``(kind, destination)`` pairs, where kind is ``"router"`` for
        a React Router link and ``"anchor"`` for a raw HTML anchor.
    """
    links = []
    name = type(component).__name__
    if name == "ReactRouterLink":
        links.append(("router", str(component.to).strip('"')))
    elif name == "A":
        links.append(("anchor", str(component.href).strip('"')))
    for child in getattr(component, "children", ()):
        links.extend(_collect_links(child))
    return links


def test_internal_menu_items_use_router_links(navbar):
    """In-app navbar links must compile to React Router links.

    Regression test: as a raw anchor, "Build with AI" sent users to
    ``reflex.dev/ai/overview/best-practices/`` instead of
    ``reflex.dev/docs/ai/overview/best-practices/``.
    """
    links = _collect_links(
        navbar.menu_item("Build with AI", "/ai/overview/best-practices/", "ai")
    )

    assert links == [("router", "/ai/overview/best-practices/")]


def test_external_menu_items_use_plain_anchors(navbar):
    """Cross-app navbar links must stay raw anchors that own their full path."""
    links = _collect_links(navbar.menu_item("XY", "/docs/xy/", "xy", external=True))

    assert links == [("anchor", "/docs/xy/")]


def test_navigation_menu_routes_in_app_destinations(navbar):
    """Every in-app navbar destination compiles to a router link."""
    from reflex_docs.pages.docs import getting_started, hosting

    router_targets = {
        dest
        for kind, dest in _collect_links(navbar.navigation_menu())
        if kind == "router"
    }

    for path in (
        "/",
        "/ai/",
        getting_started.introduction.path,
        hosting.deploy_quick_start.path,
    ):
        assert path in router_targets, f"{path} is not a router link"

    # Router links resolve against frontend_path, so a literal /docs prefix
    # here would compile to /docs/docs/...
    double_prefixed = [dest for dest in router_targets if dest.startswith("/docs")]
    assert not double_prefixed, f"double-prefixed router links: {double_prefixed}"


def test_navigation_menu_keeps_cross_app_destinations_raw(navbar):
    """Destinations outside this app render as raw anchors."""
    anchor_targets = {
        dest
        for kind, dest in _collect_links(navbar.navigation_menu())
        if kind == "anchor"
    }

    assert "/docs/xy/" in anchor_targets


def test_external_links_bypass_the_router(navbar):
    """Absolute off-site URLs render as raw anchors, not router links."""
    from reflex_site_shared.constants import GITHUB_URL

    assert _collect_links(navbar.github_button()) == [("anchor", GITHUB_URL)]


def test_docs_logo_returns_to_docs_overview(navbar):
    """The router adds the docs mount exactly once to the overview link."""
    assert _collect_links(navbar.logo()) == [("router", "/")]


def test_reflex_el_a_and_elements_a_are_not_interchangeable():
    """Guard the distinction the navbar relies on.

    ``rx.el.a`` is aliased to React Router's ``Link``; ``rx.el.elements.a`` is
    the raw HTML anchor. If those ever converge, the navbar's internal vs.
    external split becomes meaningless and this test should be revisited.
    """
    assert _collect_links(rx.el.a(href="/x/")) == [("router", "/x/")]
    assert _collect_links(rx.el.elements.a(href="/x/")) == [("anchor", "/x/")]


def test_ai_overview_is_in_the_ai_navbar_section(navbar):
    """The AI landing route remains selected when the router strips its slash."""
    rendered = str(navbar.menu_item("Build with AI", "/ai/", "ai"))
    assert '=== "/ai"' in rendered
    framework = str(
        navbar.menu_item("Framework", "/getting-started/introduction/", "framework")
    )
    assert '=== "/ai"' in framework


def test_desktop_and_mobile_demo_actions_link_to_marketing(navbar):
    """Both navbar layouts navigate to the booking page outside the docs mount."""
    links = _collect_links(navbar.navigation_menu())
    assert links.count(("anchor", "https://reflex.dev/demo/")) == 2
    assert ("router", "/demo/") not in links


def test_section_links_hover_with_text_only(navbar):
    """Keep section navigation free of button hover backgrounds."""
    item = navbar.menu_item("Framework", "/getting-started/introduction/", "framework")
    link = item.children[0]
    assert all(child.tag != "GradientButton" for child in link.children)
    assert "hover:text-muted-foreground" in str(link.class_name)
    assert "hover:bg-" not in str(link.class_name)


def test_logo_has_accessible_name_and_keyboard_focus(navbar):
    """The docs home link must be named and visible during keyboard navigation."""
    link = navbar.logo()
    assert "Reflex Docs home" in str(link)
    assert "focus-visible:outline-ring" in str(link.class_name)


def test_navigation_switches_to_mobile_before_links_overflow(navbar):
    """Keep desktop links and the mobile menu mutually exclusive below 1280px."""
    menu = navbar.navigation_menu()
    sections, actions = menu.children[:2]
    assert "hidden xl:flex" in str(sections.class_name)
    assert "xl:flex hidden" in str(actions.children[0].class_name)
    assert "xl:hidden flex" in str(actions.children[-1].class_name)
