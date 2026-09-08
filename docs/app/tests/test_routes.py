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


def _doc_markdown_files():
    """Every markdown file that backs a docs route, as (virtual, actual) pairs."""
    from reflex_docs.pages.docs import all_docs

    return sorted(all_docs.items())


# Link strings handed to `rx.link(href=...)`, `rx.redirect(...)` and friends inside
# ```python blocks are resolved by React Router, which prepends the `/docs`
# basename. Writing `/docs/...` there produces `/docs/docs/...`, which 404s.
_ROUTER_LINK_IN_PYTHON_BLOCK = re.compile(r"[\"'](/docs/[^\"']*)[\"']")
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
# A path reached through `href=`, `to=` or `rx.redirect(...)` is navigation and is
# always checked. Bare path literals are checked only when their first segment is a
# real docs section, because docs code also contains paths that are not site links
# at all — API route decorators, stylesheet paths, dynamic-route patterns.
_NAVIGATION_LINK = re.compile(r"""(?:href=|to=|rx\.redirect\()\s*["'](/[^"'\s]*)["']""")
_ANY_PATH_LITERAL = re.compile(r"""["'](/[^"'\s]*)["']""")


def test_python_block_links_resolve_to_real_routes(routes_fixture):
    """Router links inside ```python blocks must name a registered docs route.

    `test_doc_links.py` validates prose links off the markdown AST, which ignores
    fenced code blocks by design — so links written in ```python blocks are checked
    here instead.
    """
    known = {route.path.rstrip("/") for route in routes_fixture if route.path}
    sections = {path.split("/")[1] for path in known if path.count("/") > 1}

    def is_broken(link: str, navigation: bool) -> bool:
        path = link.split("#")[0].rstrip("/")
        segments = path.split("/")
        if len(segments) < 3 or path in known:
            return False
        # A misspelled section (/enterprize/...) still has to fail, so navigation
        # is validated whatever its first segment says.
        return navigation or segments[1] in sections

    broken: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        bad = []
        for block in _PYTHON_BLOCK.findall(text):
            navigation = set(_NAVIGATION_LINK.findall(block))
            bad += [
                link
                for link in _ANY_PATH_LITERAL.findall(block)
                if is_broken(link, link in navigation)
            ]
        if bad:
            broken[virtual] = sorted(set(bad))

    assert broken == {}, f"Router links point at routes that do not exist: {broken}"


def test_docpage_footer_issue_link_names_the_public_docs_url():
    """The `Raise an issue` link must report the real page URL, not the app path."""
    from reflex_docs.templates.docpage.docpage import DOCS_PROD_BASE, docpage_footer

    rendered = str(
        docpage_footer.__wrapped__(
            rx.Var.create("/vars/base-vars/"), rx.Var.create("https://example.com")
        ).render()
    )

    assert f"{DOCS_PROD_BASE}/vars/base-vars/" in rendered
    # The bare app-relative path would name a URL that 404s.
    assert "Issue%20with%20/vars/base-vars/" not in rendered


# Prose links are plain anchors, so they keep the /docs prefix that python-block
# links must omit.
_MARKDOWN_DOCS_LINK = re.compile(r"\]\((/docs/[^)\s#]*)")


def test_markdown_docs_links_resolve_to_real_routes(routes_fixture):
    """Every `](/docs/...)` link in the docs markdown must hit a registered route.

    `test_doc_links.py` checks prose links far more thoroughly, off the markdown
    AST — but only against a sitemap that has to be built first, so it is marked
    `xfail(run=False)` when the sitemap is missing. `docs_tests.yml` runs pytest
    without building, and `integration_tests.yml` — the one workflow that builds
    and passes `--runxfail` — sets `paths-ignore: ["**/*.md"]`. A markdown-only PR
    therefore triggers neither. This check needs no build, so it is the one that
    runs on a docs-only change.
    """
    known = {route.path.rstrip("/") for route in routes_fixture if route.path}

    broken: dict[str, list[str]] = {}
    for virtual, actual in _doc_markdown_files():
        text = Path(actual).read_text(encoding="utf-8")
        # Links inside ```python blocks are covered by the tests above.
        prose = _PYTHON_BLOCK.sub("", text)
        bad = [
            link
            for link in _MARKDOWN_DOCS_LINK.findall(prose)
            if link.removeprefix("/docs").rstrip("/") not in known
        ]
        if bad:
            broken[virtual] = sorted(set(bad))

    assert broken == {}, f"Markdown links point at routes that do not exist: {broken}"


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
