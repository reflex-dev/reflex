"""Tests for docs breadcrumbs."""

import importlib

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


def test_breadcrumb_keeps_docs_segment_when_present_in_path():
    """Every non-empty path segment should produce a crumb, including 'docs'."""
    from reflex_docs.templates.docpage.docpage import breadcrumb

    rendered = str(breadcrumb("/docs/ai/integrations/", rx.box()))

    assert 'to:"/docs"' in rendered
    assert 'to:"/docs/ai"' in rendered
    assert 'to:"/docs/ai/integrations"' in rendered


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
