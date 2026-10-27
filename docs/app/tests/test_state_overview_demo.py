"""Regression coverage for the State overview page's color-cycling example."""

from reflex_docs.docgen_pipeline import render_docgen_document


def test_example_heading_starts_theme_aware():
    """The first color is the theme foreground, not black, so it reads in dark mode."""
    body, _ = render_docgen_document("docs/state/overview.md", "../state/overview.md")
    rendered = str(body)
    assert 'colors: list[str] = ["var(--gray-12)"' in rendered
    assert 'colors: list[str] = ["black"' not in rendered
