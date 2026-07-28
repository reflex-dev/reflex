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
    from reflex_docs.pages.docs import ai_builder, getting_started, hosting

    router_targets = {
        dest
        for kind, dest in _collect_links(navbar.navigation_menu())
        if kind == "router"
    }

    for path in (
        "/",
        ai_builder.overview.best_practices.path,
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
    from reflex_site_shared.constants import GITHUB_URL, REFLEX_URL

    assert _collect_links(navbar.github_button()) == [("anchor", GITHUB_URL)]
    assert _collect_links(navbar.logo()) == [("anchor", REFLEX_URL)]


def test_reflex_el_a_and_elements_a_are_not_interchangeable():
    """Guard the distinction the navbar relies on.

    ``rx.el.a`` is aliased to React Router's ``Link``; ``rx.el.elements.a`` is
    the raw HTML anchor. If those ever converge, the navbar's internal vs.
    external split becomes meaningless and this test should be revisited.
    """
    assert _collect_links(rx.el.a(href="/x/")) == [("router", "/x/")]
    assert _collect_links(rx.el.elements.a(href="/x/")) == [("anchor", "/x/")]
