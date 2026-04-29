"""Integration tests for all routes in Reflex."""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def routes_fixture():
    from reflex_docs.pages import routes

    yield routes


def test_unique_routes(routes_fixture):
    assert routes_fixture is not None

    paths = [route.path for route in routes_fixture if route.path]

    # Count occurrences of each path
    path_counts = Counter(paths)
    # Find duplicate paths
    duplicates = {path: count for path, count in path_counts.items() if count > 1}

    # Assert that there are no duplicates
    assert len(duplicates) == 0, f"Duplicate routes found: {duplicates}"

    print(f"Test passed. All {len(paths)} routes are unique.")


def test_ai_builder_routes_use_ai_prefix(routes_fixture):
    paths = {route.path for route in routes_fixture if route.path}

    assert "/ai/overview/best-practices/" in paths
    assert "/ai/integrations/ai-onboarding/" in paths
    assert "/ai/integrations/mcp-overview/" in paths
    assert "/ai/integrations/skills/" in paths
    assert "/ai-builder/overview/best-practices/" not in paths
    assert "/ai-builder/integrations/ai-onboarding/" not in paths
    assert "/ai-builder/integrations/mcp-overview/" not in paths
    assert "/ai-builder/integrations/skills/" not in paths


def test_ai_overview_sidebar_order_and_active_index():
    from reflex_docs.pages.docs import ai_builder
    from reflex_docs.templates.docpage.sidebar.sidebar import calculate_index
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        ai_builder_overview_items,
    )

    overview_children = ai_builder_overview_items[0].children

    assert overview_children[0].link == ai_builder.overview.what_is_reflex_build.path
    assert overview_children[1].link == ai_builder.overview.best_practices.path
    assert (
        calculate_index(
            ai_builder_overview_items,
            ai_builder.overview.best_practices.path,
        )
        == [0, 1]
    )


def test_sidebar_index_matches_rendered_item_positions():
    from reflex_docs.templates.docpage.sidebar.sidebar import calculate_index
    from reflex_docs.templates.docpage.sidebar.state import SideBarItem

    items = [
        SideBarItem(names="Intro", link="/intro/"),
        SideBarItem(
            names="Group",
            children=[SideBarItem(names="Target", link="/target/")],
        ),
    ]

    assert calculate_index(items, "/target/") == [1, 0]


def test_breadcrumb_titles_preserve_acronyms():
    from reflex_docs.templates.docpage.docpage import format_title_with_acronyms

    assert format_title_with_acronyms("ai") == "AI"
    assert format_title_with_acronyms("mcp-overview") == "MCP Overview"
