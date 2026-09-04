"""Integration tests for all routes in Reflex."""

import re
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


def _doc_markdown_files():
    """Every markdown file that backs a docs route, as (virtual, actual) pairs."""
    from reflex_docs.pages.docs import all_docs

    return sorted(all_docs.items())


# Link strings handed to `rx.link(href=...)`, `rx.redirect(...)` and friends inside
# ```python blocks are resolved by React Router, which prepends the `/docs`
# basename. Writing `/docs/...` there produces `/docs/docs/...`, which 404s.
_ROUTER_LINK_IN_PYTHON_BLOCK = re.compile(r"\"(/docs/[^\"]*)\"")
_PYTHON_BLOCK = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def test_python_block_links_do_not_repeat_docs_basename():
    """Router links inside ```python blocks must be relative to the /docs basename.

    `rx.link(href="/docs/x")` renders a ReactRouterLink whose `to` is joined with
    the router basename, yielding `/docs/docs/x`. The href must be written `/x`.
    """
    offenders: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        bad = [
            link
            for block in _PYTHON_BLOCK.findall(text)
            for link in _ROUTER_LINK_IN_PYTHON_BLOCK.findall(block)
        ]
        if bad:
            offenders[virtual] = sorted(set(bad))

    assert offenders == {}, (
        "Router links inside ```python blocks must omit the /docs basename "
        f"(they render as /docs/docs/...): {offenders}"
    )


# Router links that survive the basename check still have to name a real page.
# Any absolute path literal counts: docs pages pass them to `href=`, to
# `rx.redirect(...)`, and as bare entries in link tables.
_ROUTER_LINK = re.compile(r"\"(/[^\"\s]*)\"")


def test_python_block_links_resolve_to_real_routes(routes_fixture):
    """Router links inside ```python blocks must name a registered docs route.

    Only links whose first segment is a real docs section are checked, so example
    app routes (`/login`, `/dashboard`, ...) stay out of scope.
    """
    known = {route.path.rstrip("/") for route in routes_fixture if route.path}
    sections = {path.split("/")[1] for path in known if path.count("/") > 1}

    def is_broken(link: str) -> bool:
        path = link.split("#")[0].rstrip("/")
        segments = path.split("/")
        if len(segments) < 3:
            return False
        return segments[1] in sections and path not in known

    broken: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        bad = [
            link
            for block in _PYTHON_BLOCK.findall(text)
            for link in _ROUTER_LINK.findall(block)
            if is_broken(link)
        ]
        if bad:
            broken[virtual] = sorted(set(bad))

    assert broken == {}, f"Router links point at routes that do not exist: {broken}"


# Markdown links are rendered as plain anchors, so they keep the /docs prefix.
_MARKDOWN_DOCS_LINK = re.compile(r"\]\((/docs/[^)\s#]*)")


def test_markdown_docs_links_resolve_to_real_routes(routes_fixture):
    """Every `](/docs/...)` link in the docs markdown must hit a registered route."""
    known = {route.path.rstrip("/") for route in routes_fixture if route.path}

    broken: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        # Ignore links inside ```python blocks; those are covered by the test above.
        prose = _PYTHON_BLOCK.sub("", text)
        bad = [
            link
            for link in _MARKDOWN_DOCS_LINK.findall(prose)
            if link.removeprefix("/docs").rstrip("/") not in known
        ]
        if bad:
            broken[virtual] = sorted(set(bad))

    assert broken == {}, f"Markdown links point at routes that do not exist: {broken}"


def test_docpage_footer_issue_link_names_the_public_docs_url():
    """The `Raise an issue` link must report the real page URL, not the app path."""
    from reflex_docs.templates.docpage.docpage import DOCS_PROD_BASE, docpage_footer

    rendered = str(
        docpage_footer.__wrapped__(rx.Var.create("/vars/base-vars/")).render()
    )

    assert f"{DOCS_PROD_BASE}/vars/base-vars/" in rendered
    # The bare app-relative path would name a URL that 404s.
    assert "Issue%20with%20/vars/base-vars/" not in rendered


def test_docs_do_not_link_to_retired_demo_apps():
    """Docs must not point readers at demo deployments that no longer exist.

    These `*.reflex.run` demos were taken down; the links 404ed for readers.
    """
    retired = ("aggrid.reflex.run", "map.reflex.run", "customer-data-app.reflex.run")

    offenders: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        found = [host for host in retired if host in text]
        if found:
            offenders[virtual] = found

    assert offenders == {}, f"Docs link to retired demo apps: {offenders}"
