"""Integration tests for all routes in Reflex."""

from collections import Counter
from pathlib import Path

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
    assert "/ai/integrations/agent-toolkit/" in paths
    assert "/ai/integrations/mcp-overview/" in paths
    assert "/ai/integrations/skills/" in paths
    assert "/ai/integrations/ai-onboarding/" not in paths
    assert "/ai-builder/overview/best-practices/" not in paths
    assert "/ai-builder/integrations/ai-onboarding/" not in paths
    assert "/ai-builder/integrations/agent-toolkit/" not in paths
    assert "/ai-builder/integrations/mcp-overview/" not in paths
    assert "/ai-builder/integrations/skills/" not in paths


def test_authentication_overview_moved_to_enterprise(routes_fixture):
    """The old authentication overview route is freed for its redirect to enterprise auth."""
    paths = {route.path for route in routes_fixture if route.path}

    assert "/authentication/authentication-overview/" not in paths
    assert "/enterprise/auth/overview/" in paths


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

    rendered = docpage_footer.__wrapped__(
        rx.Var.create("/test"), rx.Var.create("https://example.com/edit")
    ).render()

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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "docs/getting_started/introduction.md",
            "https://github.com/reflex-dev/reflex/edit/main/docs/getting_started/introduction.md",
        ),
        (
            "docs/library/forms/input-ll.md",
            "https://github.com/reflex-dev/reflex/edit/main/docs/library/forms/input-ll.md",
        ),
        (
            "CHANGELOG.md",
            "https://github.com/reflex-dev/reflex/edit/main/CHANGELOG.md",
        ),
        (
            "docs/app/reflex_docs/pages/docs/env_vars.py",
            "https://github.com/reflex-dev/reflex/edit/main/docs/app/reflex_docs/pages/docs/env_vars.py",
        ),
    ],
)
def test_github_edit_url_points_at_repo_source(source: str, expected: str):
    """The footer edit link must target the actual source file of the page."""
    from reflex_docs.templates.docpage.docpage import REPO_ROOT, github_edit_url

    assert (REPO_ROOT / source).is_file()
    assert github_edit_url(str(REPO_ROOT / source)) == expected


@pytest.mark.parametrize("use_venv", [False, True])
def test_github_edit_url_falls_back_outside_repo(tmp_path, use_venv: bool):
    """Sources outside the checkout or installed into the venv link to the docs tree."""
    import sys

    from reflex_docs.templates.docpage.docpage import github_edit_url

    outside = (Path(sys.prefix) if use_venv else tmp_path) / "some_package" / "page.md"

    assert github_edit_url(str(outside)) == (
        "https://github.com/reflex-dev/reflex/tree/main/docs"
    )


def test_github_edit_url_without_source():
    """Pages with no known source file link to the docs tree."""
    from reflex_docs.templates.docpage.docpage import github_edit_url

    assert (
        github_edit_url(None) == "https://github.com/reflex-dev/reflex/tree/main/docs"
    )


def test_markdown_doc_routes_edit_their_own_source(routes_fixture):
    """Every markdown-backed route's footer edit link is its real source file."""
    import sys

    from reflex_docs.pages.docs import doc_markdown_sources
    from reflex_docs.templates.docpage.docpage import REPO_ROOT, doc_edit_hrefs

    edit_prefix = "https://github.com/reflex-dev/reflex/edit/main/"
    venv = Path(sys.prefix).resolve()
    for route, actual in doc_markdown_sources.items():
        if route.endswith("-ll"):
            # Low-level sources are served for the copy button, not as routes.
            continue
        actual_path = Path(actual).resolve()
        if not actual_path.is_relative_to(REPO_ROOT) or actual_path.is_relative_to(
            venv
        ):
            # Docs shipped inside installed packages are not editable on GitHub.
            continue
        assert doc_edit_hrefs.get(route) == (
            edit_prefix + actual_path.relative_to(REPO_ROOT).as_posix()
        ), route
