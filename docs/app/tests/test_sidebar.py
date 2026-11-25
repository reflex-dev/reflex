"""Tests for the docs sidebar structure and prev/next chain."""

import inspect
import json
from pathlib import Path

import pytest


def test_mobile_navigation_auth_links_directly_to_enterprise_docs():
    """The shared mobile menu must not send readers through the legacy alias."""
    from reflex_site_shared.views.sidebar import solutions_panel

    rendered = str(solutions_panel())
    assert "/docs/enterprise/auth/overview/" in rendered
    assert "/docs/authentication/authentication-overview/" not in rendered


@pytest.mark.parametrize("label", ["APIs", "URLs"])
def test_ai_integration_group_and_page_use_matching_acronyms(label):
    """Keep plural acronyms consistent between sidebar groups and their pages."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        get_ai_builder_integrations,
    )

    group = next(item for item in get_ai_builder_integrations() if item.names == label)
    assert [child.names for child in group.children] == [label]


def test_backend_authentication_links_to_enterprise_auth():
    """The backend Authentication entry is a cross-reference to the enterprise auth docs."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import backend

    auth = next(item for item in backend if item.names == "Authentication")
    assert [child.link for child in auth.children] == ["/enterprise/auth/overview/"]
    assert all(child.exclude_from_prev_next for child in auth.children)


def test_cross_reference_excluded_from_prev_next_chain():
    """The enterprise auth overview keeps its enterprise-section footer links."""
    from reflex_docs.templates.docpage.sidebar.sidebar import flat_items, get_prev_next

    links = [item.link for item in flat_items]
    assert links.count("/enterprise/auth/overview/") == 1

    prev, next_ = get_prev_next("/enterprise/auth/overview/")
    assert prev is not None and prev.link == "/enterprise/event-handler-api/"
    assert next_ is not None and next_.link == "/enterprise/auth/secure-by-default/"


def test_upgrade_guide_leads_the_changelog_section():
    """The upgrade guides sit, newest first, in an Upgrading accordion atop the Changelog section."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import learn
    from reflex_docs.templates.docpage.sidebar.sidebar_items.reference import (
        changelog_items,
    )

    upgrading = changelog_items[0]
    assert upgrading.names == "Upgrading"
    assert [(child.names, child.link) for child in upgrading.children] == [
        ("Upgrading to 0.11", "/changelog/upgrading/upgrading-to-0-11/"),
        ("Upgrading to 0.10", "/changelog/upgrading/upgrading-to-0-10/"),
    ]
    assert changelog_items[1].link == "/changelog/"

    getting_started = next(item for item in learn if item.names == "Getting Started")
    assert all("Upgrading" not in child.names for child in getting_started.children)


@pytest.mark.parametrize("active", [False, True])
def test_single_page_group_is_a_direct_link(active):
    """Single-page groups navigate directly and announce the selected page."""
    import reflex as rx

    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar_item_comp
    from reflex_docs.templates.docpage.sidebar.state import SideBarItem

    group = SideBarItem(
        names="Webhooks",
        children=[SideBarItem(names="Webhooks", link="/ai/webhooks/")],
    )
    rendered = str(
        sidebar_item_comp(
            0,
            group,
            rx.Var.create([0, 0]),
            rx.Var.create("/ai/webhooks/" if active else "/ai/files/"),
        )
    )
    assert 'jsx("details"' not in rendered
    assert 'jsx("summary"' not in rendered
    assert rendered.count('"Webhooks"') == 1
    assert 'to:"/ai/webhooks/"' in rendered
    assert '"aria-current":' in rendered
    assert '"page"' in rendered and '"false"' in rendered


def test_group_with_nested_pages_remains_expandable():
    """One nested group must not hide its multiple destination pages."""
    import reflex as rx

    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar_item_comp
    from reflex_docs.templates.docpage.sidebar.state import SideBarItem

    group = SideBarItem(
        names="Data",
        children=[
            SideBarItem(
                names="Databases",
                children=[
                    SideBarItem(names="Postgres", link="/postgres/"),
                    SideBarItem(names="SQLite", link="/sqlite/"),
                ],
            )
        ],
    )
    rendered = str(
        sidebar_item_comp(0, group, rx.Var.create([0, 0]), rx.Var.create("/postgres/"))
    )
    assert rendered.count('jsx("details"') == 2
    assert 'href:"/postgres/"' in rendered
    assert 'href:"/sqlite/"' in rendered


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("title", ["Overview", "Tutorial", "Webhooks"])
def test_single_page_group_label_uses_foreground(title, active):
    """Direct-link labels must not inherit the link wrapper's muted color."""
    import reflex as rx

    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar_item_comp
    from reflex_docs.templates.docpage.sidebar.state import SideBarItem

    component = sidebar_item_comp(
        0,
        SideBarItem(
            names=title,
            children=[SideBarItem(names=title, link="/enterprise/ag-chart/")],
        ),
        rx.Var.create([]),
        rx.Var.create("/enterprise/ag-chart/" if active else "/enterprise/testing/"),
    )
    label = component.children[0].children[0].children[0]
    assert label.tag == "p"
    classes = str(label.class_name).strip('"').split()
    assert "text-foreground" in classes
    assert "docs-sidebar-group-label" in classes


@pytest.mark.parametrize(
    ("stylesheet", "selector"),
    [
        ("docs-theme.css", ".docs-sidebar"),
        ("docs-header-theme.css", ".docs-sidebar-drawer"),
    ],
)
def test_inactive_sidebar_styles_use_foreground(stylesheet, selector):
    """Desktop and mobile theme overrides must keep inactive links readable."""
    css = (Path(__file__).parents[1] / "assets" / stylesheet).read_text()
    rule = css.split(
        f"{selector} a:where(:not([aria-current='page'], [aria-current='true'])) p {{",
        1,
    )[1].split("}", 1)[0]
    assert "color: var(--foreground)" in rule


def test_api_reference_groups_related_symbols():
    """The API reference section keeps related symbols adjacent."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.reference import (
        api_reference,
    )

    assert [item.names for item in api_reference] == [
        "App",
        "Config",
        "Environment Variables",
        "State",
        "StateManager",
        "Component",
        "ComponentState",
        "Event Triggers",
        "Special Events",
        "EventHandler",
        "EventSpec",
        "Event",
        "Var",
        "ImportVar",
        "Var System",
        "CLI",
        "Browser Storage",
        "Browser Javascript",
        "Plugins",
        "Utils",
        "Telemetry",
        "Observability",
    ]


def test_api_reference_section_order_places_every_page_once():
    """Every API reference page has exactly one explicit place in the section."""
    from reflex_docs.pages.docs import api_reference as pages
    from reflex_docs.pages.docs.apiref import section_order
    from reflex_docs.templates.docpage.sidebar.sidebar_items.reference import (
        api_reference,
    )

    paths = {route.path for route in vars(pages).values()}
    assert {f"/api-reference/{slug}/" for slug in section_order} == paths

    links = [item.link for item in api_reference]
    assert len(links) == len(set(links)) == len(paths)


def test_workflow_sidebar_labels_match_page_headings():
    """Building Workflows labels spell each page the way its heading does."""
    from reflex_docs.templates.docpage.sidebar.sidebar import get_prev_next
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import (
        get_sidebar_items_workflows,
    )

    building = next(
        item
        for item in get_sidebar_items_workflows()
        if item.names == "Building Workflows"
    )
    assert [(child.names, child.link) for child in building.children] == [
        ("Defining Workflows", "/workflows/defining-workflows/"),
        ("Steps", "/workflows/steps/"),
        ("Runs", "/workflows/runs/"),
        ("Events", "/workflows/events/"),
        ("Schedules", "/workflows/schedules/"),
        ("Fan-Out", "/workflows/fan-out/"),
        ("Concurrency", "/workflows/concurrency/"),
    ]
    _, next_ = get_prev_next("/workflows/schedules/")
    assert next_ is not None and next_.names == "Fan-Out"


def test_utility_methods_list_exception_handlers():
    """Exception Handlers is reachable from the Utility Methods group."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import backend

    utility = next(item for item in backend if item.names == "Utility Methods")
    assert [(child.names, child.link) for child in utility.children] == [
        ("Router Attributes", "/utility-methods/router-attributes/"),
        ("Lifespan Tasks", "/utility-methods/lifespan-tasks/"),
        ("Exception Handlers", "/utility-methods/exception-handlers/"),
        ("Other Methods", "/utility-methods/other-methods/"),
    ]


def test_cloud_sidebar_opens_with_the_cloud_overview():
    """The Cloud overview leads the Cloud sidebar and its prev/next chain."""
    from reflex_docs.templates.docpage.sidebar.sidebar import get_prev_next
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import hosting

    assert [(child.names, child.link) for child in hosting[0].children] == [
        ("Overview", "/hosting/overview/")
    ]
    prev, next_ = get_prev_next("/hosting/deploy-quick-start/")
    assert prev is not None
    assert (prev.alt_name_for_next_prev, prev.link) == (
        "Cloud Overview",
        "/hosting/overview/",
    )
    assert next_ is not None and next_.link == "/hosting/project-members/"


def test_integrations_are_grouped_with_legacy_cards_last():
    """Integration cards sit in category groups; superseded cards close the list."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        get_ai_builder_integrations,
    )

    groups = {
        item.names: [child.link.split("/")[-2] for child in item.children]
        for item in get_ai_builder_integrations()
    }
    assert groups == {
        "Overview": ["overview"],
        "AI Models": [
            "anthropic",
            "cartesia",
            "cohere",
            "gemini",
            "groq",
            "hugging-face",
            "openai",
            "perplexity",
            "replicate",
            "roboflow",
        ],
        "Authentication": [
            "auth0",
            "clerk",
            "custom-oidc",
            "google",
            "keycloak",
            "microsoft-entra-id",
            "okta",
        ],
        "Data Infrastructure": [
            "aws",
            "database",
            "databricks",
            "hubspot",
            "notion",
            "supabase",
        ],
        "Communication": ["circleback", "resend", "twilio"],
        "Developer Tools": ["github", "linear"],
        "Payments": ["stripe"],
        "Python Libraries": ["python-libraries"],
        "APIs": ["apis"],
        "Webhooks": ["webhooks"],
        "URLs": ["urls"],
        "Files": ["files"],
        "Images": ["images"],
        "Figma": ["figma"],
        "Legacy": ["azure-auth", "descope", "google-auth", "okta-auth"],
    }
    assert list(groups)[-1] == "Legacy"


def test_every_integration_card_is_in_the_sidebar():
    """Each integration page that has a card is listed in the Integrations sidebar."""
    from reflex_docs.pages.integrations.integration_list import get_integration_path
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        get_ai_builder_integrations,
    )

    listed = {
        child.link
        for item in get_ai_builder_integrations()
        for child in item.children
        if child.link.startswith("/ai/integrations/")
    }
    cards = {next(iter(card.values()))["path"] for card in get_integration_path()}
    assert listed == cards | {"/ai/integrations/overview/"}


@pytest.mark.parametrize(
    ("url", "section"),
    [
        ("/wrapping-react/library-and-tags/", "framework"),
        ("/docs/library/forms/button/low/", "components"),
        ("/changelog/reflex-hosting-cli/", "api-reference"),
        ("/hosting/overview/", "cloud"),
    ],
)
def test_sidebar_receives_the_route_section(url, section):
    """The sidebar picks its content from the section computed at build time."""
    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar

    rendered = sidebar(url=url).children[0]
    assert str(rendered.section) == f'"{section}"'


def _category_labels(component) -> list[str]:
    """Collect sidebar category names, including those in every conditional branch.

    Args:
        component: The root of a rendered component tree.

    Returns:
        The name of each category link, in tree order.
    """
    label = getattr(component, "custom_attrs", {}).get("aria-label")
    labels = [label.removeprefix("Navigate to ")] if label else []
    for child in (
        *getattr(component, "children", ()),
        *(
            branch
            for branch in (
                getattr(component, "comp1", None),
                getattr(component, "comp2", None),
            )
            if branch is not None
        ),
    ):
        labels.extend(_category_labels(child))
    return labels


def test_sidebar_categories_use_the_navbar_section_names():
    """No sidebar repeats a one-item Cloud category above its Cloud heading, and the
    guides' category is named Framework like its navbar tab.
    """
    import reflex as rx

    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar_comp

    params = inspect.signature(sidebar_comp.__wrapped__).parameters
    args = {name: rx.Var.create([]) for name in params}
    args["url"] = rx.Var.create("/hosting/overview/")
    args["section"] = rx.Var.create("cloud")

    assert _category_labels(sidebar_comp.__wrapped__(**args)) == [
        "Build with AI",
        "AI Builder",
        "Agent Toolkit",
        "Framework",
        "Components",
        "API Reference",
        "Enterprise",
    ]


def _css_rule(css: str, selectors: str) -> str:
    """Find the declarations of the stylesheet rule with exactly these selectors.

    Args:
        css: The stylesheet source.
        selectors: The rule's complete selector list, one selector per line.

    Returns:
        The rule's declarations, stripped of surrounding whitespace.
    """
    rules = {
        head.strip(): body.strip()
        for head, sep, body in (rule.partition("{") for rule in css.split("}"))
        if sep
    }
    return rules[selectors]


@pytest.mark.parametrize(
    ("stylesheet", "selector"),
    [
        ("docs-theme.css", ".docs-sidebar"),
        ("docs-header-theme.css", ".docs-sidebar-drawer"),
    ],
)
def test_group_labels_outweigh_page_links(stylesheet, selector):
    """Collapsible and direct-link group labels are heavier than page links."""
    css = (Path(__file__).parents[1] / "assets" / stylesheet).read_text()
    assert _css_rule(css, f"{selector} p,\n{selector} h3,\n{selector} summary") == (
        "font-weight: 400;"
    )
    assert _css_rule(
        css, f"{selector} summary p,\n{selector} .docs-sidebar-group-label"
    ) == ("font-weight: 500;")


# The item lists the docs sidebar renders, as named in its module.
SIDEBAR_LISTS = (
    "learn",
    "frontend",
    "backend",
    "workflows",
    "hosting",
    "component_lib",
    "graphing_libs",
    "html_lib",
    "recipes",
    "ai_builder_overview_items",
    "ai_builder_integrations",
    "agent_toolkit_items",
    "mcp_items",
    "skills_items",
    "api_reference",
    "changelog_items",
    "enterprise_usage_items",
    "enterprise_component_items",
)


def _sidebar_lists() -> dict[str, list]:
    """Get every item list the docs sidebar renders.

    Returns:
        Each rendered list of sidebar items, keyed by its name in the sidebar module.
    """
    import importlib

    module = importlib.import_module("reflex_docs.templates.docpage.sidebar.sidebar")
    return {name: getattr(module, name) for name in SIDEBAR_LISTS}


def _page_items(items) -> list:
    """Collect the sidebar items that link to a page, including nested ones.

    Args:
        items: Sidebar items.

    Returns:
        Each item with a link, in sidebar order.
    """
    pages = []
    for item in items:
        if item.link:
            pages.append(item)
        pages.extend(_page_items(item.children))
    return pages


def _rendered_links(component, href=None) -> list[tuple[str, str | None]]:
    """Collect the page links of a rendered sidebar, in every conditional branch.

    Args:
        component: The root of a rendered component tree.
        href: The route of the link enclosing ``component``, if any.

    Returns:
        A ``(route, label)`` pair for each page link, with label None for the
        section and category links that only head a list of pages.
    """
    to = getattr(component, "to", None)
    if to is None:
        to = getattr(component, "href", None)
    if to is not None:
        href = json.loads(str(to))
    if (getattr(component, "tag", None) or "").startswith("DocsSidebarLeaf"):
        return [(href, json.loads(str(component.title)))]
    if "docs-sidebar-group-label" in str(getattr(component, "class_name", "")):
        return [(href, json.loads(str(component.children[0])))]
    links = [(href, None)] if to is not None else []
    for child in (
        *getattr(component, "children", ()),
        *(
            branch
            for branch in (
                getattr(component, "comp1", None),
                getattr(component, "comp2", None),
            )
            if branch is not None
        ),
    ):
        links.extend(_rendered_links(child, href))
    return links


def _rendered_sidebar():
    """Render the whole docs sidebar with every group closed.

    Returns:
        The sidebar's component tree.
    """
    import reflex as rx

    from reflex_docs.templates.docpage.sidebar.sidebar import sidebar_comp

    params = inspect.signature(sidebar_comp.__wrapped__).parameters
    args = {name: rx.Var.create([]) for name in params}
    args["url"] = rx.Var.create("/")
    args["section"] = rx.Var.create("framework")
    return sidebar_comp.__wrapped__(**args)


def test_every_sidebar_page_is_shown_under_its_own_name():
    """Each sidebar entry renders as a link labelled with that entry's own name.

    A one-page group whose page has another name (Payments holding Stripe)
    lists the page under the group heading rather than hiding its name, and
    section overview entries such as State Overview are links that the page
    can mark as current.
    """
    from collections import Counter

    expected = Counter(
        (item.link, item.names)
        for items in _sidebar_lists().values()
        for item in _page_items(items)
    )
    rendered = Counter(
        (href, label)
        for href, label in _rendered_links(_rendered_sidebar())
        if label is not None
    )
    assert rendered == expected


@pytest.mark.parametrize("name", SIDEBAR_LISTS)
def test_sidebar_index_opens_the_group_holding_each_page(name):
    """``calculate_index`` points at the rendered position of every listed page."""
    from reflex_docs.templates.docpage.sidebar.sidebar import calculate_index

    items = _sidebar_lists()[name]
    for page in _page_items(items):
        found, level = None, items
        for position in calculate_index(items, page.link):
            found = level[position]
            level = found.children
        assert found is not None and found.link == page.link


def test_every_sidebar_page_is_listed_once():
    """No page appears in two places, apart from marked cross-references."""
    from collections import Counter

    counts = Counter(
        item.link
        for items in _sidebar_lists().values()
        for item in _page_items(items)
        if not item.exclude_from_prev_next
    )
    assert [link for link, count in counts.items() if count > 1] == []


def test_integration_groups_follow_each_card_tag():
    """An integration card sits in the sidebar group its frontmatter tag names."""
    from reflex_docs.pages.integrations.integration_list import get_integration_path
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        get_ai_builder_integrations,
    )

    # Sidebar group names for the tags whose gallery filter name is shorter.
    group_by_tag = {"AI": "AI Models", "DevTools": "Developer Tools"}
    cards = [next(iter(card.values())) for card in get_integration_path()]
    groups = {
        child.link: item.names
        for item in get_ai_builder_integrations()
        if item.names != "Legacy"
        for child in item.children
    }
    assert {
        card["path"]: group_by_tag.get(card["tags"], card["tags"])
        for card in cards
        if card["path"] in groups
    } == {
        card["path"]: groups[card["path"]] for card in cards if card["path"] in groups
    }


# Docs routes deliberately left out of every sidebar, with the reason.
UNLISTED_ROUTES = {
    "/": "The docs landing page, reached from the logo and the Overview navbar tab.",
}


def test_every_docs_route_is_in_a_sidebar_or_explicitly_unlisted():
    """Every registered docs page is reachable from a sidebar, so none is orphaned."""
    from reflex_docs.pages import routes
    from reflex_docs.templates.docpage.sidebar.sidebar import normalize_url

    linked = {href for href, _ in _rendered_links(_rendered_sidebar())}
    registered = {normalize_url(route.path) for route in routes}
    assert sorted(registered - linked) == sorted(UNLISTED_ROUTES)
