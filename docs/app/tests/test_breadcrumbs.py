"""Tests for docs breadcrumbs."""

import importlib
import sys
from pathlib import Path

import reflex as rx

sys.path.append(str(Path(__file__).resolve().parent.parent))


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
    """Breadcrumb segment mapping should not special-case the docs segment."""
    from reflex_docs.templates.docpage.docpage import breadcrumb

    rendered = str(breadcrumb("/docs/ai/integrations/", rx.box()))

    assert "Docs" in rendered
    assert "Ai" in rendered
    assert "Integrations" in rendered
