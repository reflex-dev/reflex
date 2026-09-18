"""Tests for the docs sidebar structure and prev/next chain."""

import pytest


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
        "Minification",
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
