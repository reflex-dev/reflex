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
        ("http://localhost:3000", "/docs", "http://localhost:3000/docs"),
        (
            "https://staging.example.com/",
            "/preview/docs/",
            "https://staging.example.com/preview/docs",
        ),
        ("https://docs.example.com/", "", "https://docs.example.com"),
    ],
)
def test_structured_breadcrumbs_use_real_canonical_routes(
    monkeypatch, deploy_url, frontend_path, base
):
    """Structured navigation names existing pages and includes the docs root."""
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
def test_root_breadcrumb_has_one_location(path):
    """The docs root must not repeat itself as the current location."""
    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    items = docpage_module.breadcrumb_data(path, "Documentation")["itemListElement"]
    assert items == [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Documentation",
            "item": "https://reflex.dev/docs/",
        }
    ]
