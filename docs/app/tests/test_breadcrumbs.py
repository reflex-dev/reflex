"""Tests for docs breadcrumbs."""

import importlib
from types import SimpleNamespace

import pytest
import reflex as rx


def test_enterprise_parent_breadcrumb_uses_overview_route(monkeypatch):
    """Parent breadcrumbs should link to a real overview route when needed."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(
        docpage_module,
        "_REGISTERED_DOC_ROUTES",
        {
            "/enterprise/overview/",
            "/enterprise/ag-grid/",
            "/enterprise/ag-grid/pivot-mode/",
        },
        raising=False,
    )

    rendered = str(
        docpage_module.breadcrumb("/enterprise/ag-grid/pivot-mode/", rx.box())
    )

    assert 'to:"/enterprise/overview/"' in rendered
    assert 'to:"/enterprise/ag-grid/"' in rendered
    assert 'to:"/enterprise/ag-grid/pivot-mode/"' in rendered


def test_missing_parent_breadcrumb_is_not_clickable(monkeypatch):
    """Breadcrumb segments without a real route should not be clickable links."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    # Only the leaf page is a registered route; the "ai" and "ai/overview"
    # parents have no page and no overview child (mirrors /docs/ai 404s).
    monkeypatch.setattr(
        docpage_module,
        "_REGISTERED_DOC_ROUTES",
        {"/ai/overview/some-feature/"},
        raising=False,
    )

    rendered = str(docpage_module.breadcrumb("/ai/overview/some-feature/", rx.box()))

    # The leaf resolves to a real route and stays clickable.
    assert 'to:"/ai/overview/some-feature/"' in rendered
    # The missing parents must not render as links to broken URLs.
    assert 'to:"/ai/"' not in rendered
    assert 'to:"/ai/overview/"' not in rendered
    # Their labels are still shown as plain text ("ai" renders as "AI").
    assert "AI" in rendered
    assert "Overview" in rendered


def test_resolve_breadcrumb_href_returns_none_for_missing_route():
    """A path with no registered route or overview child resolves to None."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")

    assert (
        docpage_module._resolve_breadcrumb_href("/hosting", {"/hosting/deploy/"})
        is None
    )


@pytest.mark.parametrize(
    "deploy_url,frontend_path,base",
    [
        ("https://reflex.dev", "/docs", "https://reflex.dev/docs"),
        ("http://localhost:3000", "/docs", "https://reflex.dev/docs"),
        (
            "https://staging.example.com/",
            "/preview/docs/",
            "https://reflex.dev/docs",
        ),
        ("https://docs.example.com/", "", "https://reflex.dev/docs"),
    ],
)
def test_structured_breadcrumbs_use_real_canonical_routes(
    monkeypatch, deploy_url, frontend_path, base
):
    """Structured navigation matches public canonicals, independent of deployment."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(
        "reflex_site_shared.utils.url.get_config",
        lambda: SimpleNamespace(deploy_url=deploy_url, frontend_path=frontend_path),
    )
    monkeypatch.setattr(
        docpage_module,
        "_REGISTERED_DOC_ROUTES",
        {
            "/enterprise/overview/",
            "/enterprise/auth/overview/",
            "/enterprise/auth/testing/",
        },
    )
    data = docpage_module.breadcrumb_data("/enterprise/auth/testing/", "Testing")
    assert data["@type"] == "BreadcrumbList"
    items = data["itemListElement"]
    assert [item["position"] for item in items] == list(range(1, len(items) + 1))
    assert [item["item"] for item in items] == [
        base + "/",
        base + "/enterprise/overview/",
        base + "/enterprise/auth/overview/",
        base + "/enterprise/auth/testing/",
    ]


@pytest.mark.parametrize("path", ["/", ""])
def test_root_breadcrumb_has_one_location(path, monkeypatch):
    """The docs root must not repeat itself as the current location."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(
        "reflex_site_shared.utils.url.get_config",
        lambda: SimpleNamespace(deploy_url="https://reflex.dev", frontend_path="/docs"),
    )
    items = docpage_module.breadcrumb_data(path, "Documentation")["itemListElement"]
    assert items == [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Documentation",
            "item": "https://reflex.dev/docs/",
        }
    ]


@pytest.mark.parametrize(
    ("path", "names", "routes", "expected"),
    [
        (
            "/changelog/upgrading/upgrading-to-0-11/",
            ("Upgrading to Reflex 0.11", "Upgrading to 0.11"),
            {"/changelog/", "/changelog/upgrading/upgrading-to-0-11/"},
            [
                ("Changelog", "/changelog/"),
                ("Upgrading", None),
                ("Upgrading to 0.11", "/changelog/upgrading/upgrading-to-0-11/"),
            ],
        ),
        (
            "/api-reference/cli/",
            ("Cli", "CLI"),
            {"/api-reference/overview/", "/api-reference/cli/"},
            [
                ("API Reference", "/api-reference/overview/"),
                ("CLI", "/api-reference/cli/"),
            ],
        ),
        (
            "/workflows/fan-out/",
            ("Fan-Out", "Fan Out"),
            {"/workflows/overview/", "/workflows/fan-out/"},
            [
                ("Workflows", "/workflows/overview/"),
                ("Fan-Out", "/workflows/fan-out/"),
            ],
        ),
        (
            "/recipes/",
            ("Overview", "Recipes Overview"),
            {"/recipes/"},
            [("Recipes", "/recipes/")],
        ),
        (
            "/getting-started/chatapp-tutorial/",
            ("Build a Streaming AI Chatbot in Python with Reflex", "Chat App Tutorial"),
            {"/getting-started/chatapp-tutorial/"},
            [
                ("Getting Started", None),
                ("Chat App Tutorial", "/getting-started/chatapp-tutorial/"),
            ],
        ),
        (
            "/ai/integrations/overview/",
            (),
            {"/ai/integrations/overview/"},
            [
                ("AI", None),
                ("Integrations", "/ai/integrations/overview/"),
                ("Overview", "/ai/integrations/overview/"),
            ],
        ),
        (
            "/enterprise/mcp/authentication/",
            ("MCP Authentication", "Authentication"),
            {"/enterprise/overview/", "/enterprise/mcp/authentication/"},
            [
                ("Enterprise", "/enterprise/overview/"),
                ("MCP", None),
                ("Authentication", "/enterprise/mcp/authentication/"),
            ],
        ),
        (
            "/library/html/html/",
            ("HTML Elements", "HTML"),
            {"/library/html/html/"},
            [("Library", None), ("HTML", None), ("HTML", "/library/html/html/")],
        ),
        (
            "/ai/organization/sso/",
            ("Sso", "SSO"),
            {"/ai/organization/sso/"},
            [("AI", None), ("Organization", None), ("SSO", "/ai/organization/sso/")],
        ),
        (
            "/ai/integrations/github/",
            ("Github",),
            {"/ai/integrations/github/"},
            [
                ("AI", None),
                ("Integrations", None),
                ("GitHub", "/ai/integrations/github/"),
            ],
        ),
    ],
)
def test_breadcrumb_labels_spell_the_route_and_keep_acronyms(
    monkeypatch, path, names, routes, expected
):
    """The last crumb takes the first page name that spells its route segment.

    A name with other words, such as an SEO title or a generic sidebar label, is
    skipped so the crumb keeps naming the route.
    """
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(docpage_module, "_REGISTERED_DOC_ROUTES", routes)

    assert docpage_module._breadcrumb_items(path, names) == expected


def test_sidebar_label_finds_the_page_entry():
    """The sidebar label lookup returns each page's label, with or without slashes."""
    from reflex_docs.templates.docpage.sidebar import sidebar_label

    assert sidebar_label("/changelog/upgrading/upgrading-to-0-11/") == (
        "Upgrading to 0.11"
    )
    assert sidebar_label("api-reference/cli") == "CLI"
    assert sidebar_label("/not-a-docs-page/") is None


@pytest.mark.parametrize(
    ("route", "title", "label"),
    [
        (
            "/ai/integrations/github/",
            "GitHub · Integrations · AI · Reflex Docs",
            "GitHub",
        ),
        (
            "/ai/integrations/openai/",
            "OpenAI · Integrations · AI · Reflex Docs",
            "OpenAI",
        ),
        (
            "/ai/features/connect-to-github/",
            "Connect To GitHub · Features · AI · Reflex Docs",
            "Connect To GitHub",
        ),
        (
            "/library/other/html-embed/",
            "rx.html: Python HTML Embed Component · Reflex Docs",
            "HTML Embed",
        ),
        ("/hosting/cli/vmtypes/", "VM Types", "VM Types"),
        (
            "/ai/integrations/custom-oidc/",
            "Custom OIDC · Integrations · AI · Reflex Docs",
            "Custom OIDC",
        ),
        (
            "/ai/integrations/microsoft-entra-id/",
            "Microsoft Entra ID · Integrations · AI · Reflex Docs",
            "Microsoft Entra ID",
        ),
    ],
)
def test_page_titles_and_sidebar_labels_keep_acronyms(route, title, label):
    """Page titles and sidebar labels spell acronyms and brands like the page."""
    from reflex_docs.pages import routes
    from reflex_docs.templates.docpage.sidebar import sidebar_label

    page = next(page for page in routes if page.path.strip("/") == route.strip("/"))
    assert page.title == title
    assert sidebar_label(route) == label


def test_structured_breadcrumb_parents_keep_acronyms(monkeypatch):
    """Structured breadcrumbs label multi-word parents like the visible ones."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    monkeypatch.setattr(
        "reflex_site_shared.utils.url.get_config",
        lambda: SimpleNamespace(deploy_url="https://reflex.dev", frontend_path="/docs"),
    )
    monkeypatch.setattr(
        docpage_module,
        "_REGISTERED_DOC_ROUTES",
        {"/api-reference/overview/", "/api-reference/cli/"},
    )
    items = docpage_module.breadcrumb_data("/api-reference/cli/", "CLI")[
        "itemListElement"
    ]
    assert [item["name"] for item in items] == ["Documentation", "API Reference", "CLI"]
