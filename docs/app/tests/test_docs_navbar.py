"""Tests for the docs navbar links.

The docs app is served under ``frontend_path="/docs"``. ``rx.el.a`` compiles to
React Router's ``Link``, which resolves its destination against that basename;
``rx.el.elements.a`` stays a raw HTML anchor, which does not. In-app links must
therefore use the former, and links that already carry a full path (other
deployments, the marketing site) must use the latter.
"""

import importlib

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


def _walk_components(component):
    """Yield a component and its descendants, including conditional branches.

    Args:
        component: The root component to walk.

    Yields:
        Each component in the tree.
    """
    yield component
    for child in getattr(component, "children", ()):
        yield from _walk_components(child)


def test_internal_menu_items_use_router_links(navbar):
    """In-app navbar links must compile to React Router links.

    Regression test: as a raw anchor, "Build with AI" sent users to
    ``reflex.dev/ai/overview/best-practices/`` instead of
    ``reflex.dev/docs/ai/overview/best-practices/``.
    """
    links = _collect_links(
        navbar.menu_item("Build with AI", "/ai/overview/best-practices/")
    )

    assert links == [("router", "/ai/overview/best-practices/")]


def test_external_menu_items_use_plain_anchors(navbar):
    """Cross-app navbar links must stay raw anchors that own their full path."""
    links = _collect_links(navbar.menu_item("XY", "/docs/xy/", external=True))

    assert links == [("anchor", "/docs/xy/")]


def test_navigation_menu_routes_in_app_destinations(navbar):
    """Every in-app navbar destination compiles to a router link."""
    from reflex_docs.pages.docs import cloud, getting_started

    router_targets = {
        dest
        for kind, dest in _collect_links(navbar.navigation_menu())
        if kind == "router"
    }

    for path in (
        "/",
        "/ai/",
        getting_started.introduction.path,
        cloud.overview.path,
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
    assert _collect_links(navbar.logo())[0] == ("anchor", REFLEX_URL)


def test_docs_logo_returns_to_docs_overview(navbar):
    """The Reflex wordmark is a raw anchor; the Docs wordmark routes in-app."""
    from reflex_site_shared.constants import REFLEX_URL

    assert _collect_links(navbar.logo()) == [
        ("anchor", REFLEX_URL),
        ("router", "/"),
    ]


def test_reflex_el_a_and_elements_a_are_not_interchangeable():
    """Guard the distinction the navbar relies on.

    ``rx.el.a`` is aliased to React Router's ``Link``; ``rx.el.elements.a`` is
    the raw HTML anchor. If those ever converge, the navbar's internal vs.
    external split becomes meaningless and this test should be revisited.
    """
    assert _collect_links(rx.el.a(href="/x/")) == [("router", "/x/")]
    assert _collect_links(rx.el.elements.a(href="/x/")) == [("anchor", "/x/")]


def _current_tabs(menu) -> list[str]:
    """List the section links a navigation menu marks as the current page.

    A link built for the current tab compiles its ``aria-current`` to a constant
    ``true`` condition, which server rendering resolves to ``page``.

    Args:
        menu: The rendered navigation menu.

    Returns:
        The text of every section link whose ``aria-current`` is ``page``.
    """
    links = [item.children[0] for item in menu.children[0].children]
    return [
        str(link.children[0].contents).strip('"')
        for link in links
        if str(link.custom_attrs["aria-current"]) == '(true ? "page" : null)'
    ]


@pytest.mark.parametrize(
    ("tab", "expected"),
    [
        ("overview", ["Overview"]),
        ("ai", ["Build with AI"]),
        ("framework", ["Framework"]),
        ("cloud", ["Cloud"]),
        ("xy", ["XY"]),
        ("", []),
    ],
)
def test_navigation_menu_marks_only_the_current_tab(navbar, tab, expected):
    """A literal tab marks its link at build time, so prerendered HTML is correct."""
    assert _current_tabs(navbar.navigation_menu(tab)) == expected


def _navbar_tab_prop(component) -> str:
    """Find the tab a page passes to the docs navbar.

    Args:
        component: The page's root component.

    Returns:
        The ``activeTab`` prop of the page's docs navbar.
    """
    navbar = next(
        child
        for child in _walk_components(component)
        if str(getattr(child, "tag", "")).startswith("DocsNavbar")
    )
    return str(navbar.activeTab)


@pytest.mark.parametrize(
    ("path", "tab"),
    [
        ("/ai/", "ai"),
        ("/ai/integrations/okta/", "ai"),
        ("/getting-started/introduction/", "framework"),
        ("/wrapping-react/library-and-tags/", "framework"),
        ("/library/forms/button/", "framework"),
        ("/api-reference/app/", "framework"),
        ("/changelog/reflex-hosting-cli/", "framework"),
        ("/enterprise/overview/", "framework"),
        ("/hosting/overview/", "cloud"),
        ("/hosting/deploy-quick-start/", "cloud"),
    ],
)
def test_docpages_pass_their_tab_to_the_navbar(navbar, monkeypatch, path, tab):
    """Every docs page tells the navbar its tab instead of matching the router path.

    Regression test: the navbar matched the runtime router path, which is unset
    while prerendering, so every page's HTML marked "Framework"; and it matched
    substrings, so the reflex-hosting-cli changelog lit "Cloud".
    """
    from reflex_docs.templates.docpage import docpage

    # Keep this throwaway page out of the registries other tests read.
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(docpage_module, "doc_edit_hrefs", {})
    monkeypatch.setattr(docpage_module, "_REGISTERED_DOC_ROUTES", set())

    def content() -> rx.Component:
        return rx.text("Content")

    page = docpage(set_path=path, t="Page")(content)
    assert _navbar_tab_prop(page.component()) == f'"{tab}"'


def test_landing_and_missing_pages_pass_their_tab_to_the_navbar(navbar):
    """The landing page marks Overview, and a missing page marks no tab."""
    from reflex_docs.pages.docs_landing import docs_landing
    from reflex_docs.pages.page404 import page404

    assert _navbar_tab_prop(docs_landing.component()) == '"overview"'
    assert _navbar_tab_prop(page404.component()) == '""'


def test_desktop_and_mobile_demo_actions_link_to_marketing(navbar):
    """Both navbar layouts navigate to the booking page outside the docs mount."""
    links = _collect_links(navbar.navigation_menu())
    assert links.count(("anchor", "https://reflex.dev/demo/")) == 2
    assert ("router", "/demo/") not in links


def test_section_links_hover_with_text_only(navbar):
    """Keep section navigation free of button hover backgrounds."""
    item = navbar.menu_item("Framework", "/getting-started/introduction/")
    link = item.children[0]
    assert all(child.tag != "GradientButton" for child in link.children)
    assert "hover:text-foreground" in str(link.class_name)
    assert "hover:bg-" not in str(link.class_name)


def test_logo_has_accessible_name_and_keyboard_focus(navbar):
    """The docs home link must be named and visible during keyboard navigation."""
    for link, label in zip(
        navbar.logo().children, ("Reflex home", "Docs overview"), strict=True
    ):
        assert label in str(link)
        assert "focus-visible:outline-ring" in str(link.class_name)


def test_navigation_switches_to_mobile_before_links_overflow(navbar):
    """Keep desktop links and the mobile menu mutually exclusive below 1280px."""
    menu = navbar.navigation_menu()
    sections, actions = menu.children[:2]
    assert "hidden xl:flex" in str(sections.class_name)
    assert "xl:flex hidden" in str(actions.children[0].class_name)
    assert "xl:hidden flex" in str(actions.children[-1].class_name)


def test_mobile_menu_preserves_primary_docs_destinations(navbar):
    """Mobile readers can reach every top-level docs section."""
    from reflex_docs.components.docpage.navbar.buttons.sidebar import (
        navbar_sidebar_button,
    )

    links = _collect_links(navbar_sidebar_button())
    for path in (
        "/docs/",
        "/docs/ai/",
        "/docs/getting-started/introduction/",
        "/docs/hosting/deploy-quick-start/",
        "/docs/xy/",
    ):
        assert ("anchor", path) in links


def test_docs_announcement_preserves_link_and_dismissal():
    """The branded announcement remains an accessible, dismissible external link."""
    from reflex_docs.views.docs_announcement_banner import docs_announcement_banner

    banner = docs_announcement_banner()
    assert _collect_links(banner) == [
        ("anchor", "https://reflex.dev/blog/series-a-announcement/")
    ]
    region = next(
        component
        for component in _walk_components(banner)
        if "data-announcement" in getattr(component, "custom_attrs", {})
    )
    link, dismiss = region.children
    copy = link.children[0].children[0]
    assert len(copy.children) == 2
    assert all("Announcing our $14M Series A" in str(line) for line in copy.children)
    assert copy.children[1].custom_attrs["aria-hidden"] is True
    assert "docs-announcement-glass" not in str(region)
    assert "Latest announcement" in str(region.custom_attrs["aria-label"])
    assert str(link.target) == '"_blank"'
    assert "noopener noreferrer" in str(link.rel)
    assert "opens in a new tab" in str(link.custom_attrs["aria-label"])
    assert "Announcing our $14M Series A" in str(link.custom_attrs["aria-label"])
    assert "Dismiss announcement" in str(dismiss.custom_attrs["aria-label"])
    assert "hide_banner" in str(dismiss.event_triggers["on_click"])


def test_mobile_navigation_retains_native_disclosure(navbar):
    """Styling must preserve native summary activation and a named navigation area."""
    menu = navbar.navbar_sidebar_button()
    assert menu.tag == "details"
    assert menu.children[0].tag == "summary"
    assert "Toggle navigation menu" in str(menu.children[0])
    assert str(menu.children[1].role) == '"navigation"'
    assert "Documentation navigation" in str(menu.children[1])


def test_docs_sidebar_drawer_has_a_title_and_keyboard_close(navbar):
    """Mobile sidebar readers need a named dialog and a focusable close control."""
    from reflex_site_shared.views.sidebar import docs_sidebar_drawer

    drawer = docs_sidebar_drawer(rx.text("Guides"), rx.el.button("Open guides"))
    nodes = list(_walk_components(drawer))
    titles = [node for node in nodes if node.tag == "Drawer.Title"]
    assert len(titles) == 1
    assert "Documentation navigation" in str(titles[0])
    close = next(node for node in nodes if node.tag == "Drawer.Close")
    assert close.children[0].tag == "button"
    assert (
        close.children[0].custom_attrs["aria-label"] == "Close documentation navigation"
    )


def test_editorial_footer_product_links_skip_the_retired_pricing_page():
    """The footer lists real product destinations; /pricing/ redirects to /demo/."""
    from reflex_site_shared.constants import REFLEX_BUILD_URL

    from reflex_docs.views.editorial_footer import _FOOTER_LINKS

    assert dict(_FOOTER_LINKS)["Product"] == (
        ("AI Builder", REFLEX_BUILD_URL),
        ("Agent Toolkit", "/docs/ai/integrations/agent-toolkit/"),
        ("Enterprise", "/docs/enterprise/overview/"),
        ("App Management", "/hosting/"),
    )
