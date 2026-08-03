"""Integration tests for all routes in Reflex."""

from collections import Counter

import pytest
import reflex as rx


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


def test_changelog_routes(routes_fixture):
    """Every discovered package changelog is served under /changelog/."""
    from reflex_docs.pages.docs import changelog_packages

    paths = {route.path for route in routes_fixture if route.path}

    assert changelog_packages["reflex"] == "/changelog/"
    assert "/changelog/reflex-base/" in paths
    for changelog_route in changelog_packages.values():
        assert changelog_route in paths


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


def test_docs_route_descriptions_fit_search_snippet_length(routes_fixture):
    """Generated docs meta descriptions should not exceed the SEO snippet cap."""
    overlong = {
        route.path: len(route.description or "")
        for route in routes_fixture
        if route.description and len(route.description) > 155
    }

    assert overlong == {}


@pytest.mark.parametrize(
    ("label", "href"),
    [("Blog", "/blog/"), ("FAQ", "/faq/")],
)
def test_docpage_footer_uses_root_site_anchors(label: str, href: str):
    """Root-site footer links should not inherit the /docs router basename."""
    from reflex_docs.templates.docpage.docpage import docpage_footer

    rendered = docpage_footer.__wrapped__(rx.Var.create("/test")).render()

    def find_link(node: dict) -> dict | None:
        if any(child.get("contents") == f'"{label}"' for child in node["children"]):
            return node
        for child in node["children"]:
            if "children" in child and (link := find_link(child)) is not None:
                return link
        return None

    link = find_link(rendered)
    assert link is not None
    assert link["name"] == '"a"'
    assert f'href:"{href}"' in link["props"]
