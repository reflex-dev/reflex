"""Tests for docs breadcrumb rendering."""

import sys
from pathlib import Path

import reflex as rx

sys.path.append(str(Path(__file__).resolve().parent.parent))


def test_breadcrumb_keeps_docs_segment_when_present_in_path():
    """Breadcrumb segment mapping should not special-case the docs segment."""
    from reflex_docs.templates.docpage.docpage import breadcrumb

    rendered = str(breadcrumb("/docs/ai/integrations/", rx.box()))

    assert "Docs" in rendered
    assert "Ai" in rendered
    assert "Integrations" in rendered
