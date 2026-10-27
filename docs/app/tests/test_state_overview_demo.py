"""Regression coverage for the State overview page's color-cycling example."""

import re

from reflex_docs.docgen_pipeline import render_docgen_document


def test_example_heading_starts_theme_aware():
    """The first color is the theme foreground, not black, so it reads in dark mode."""
    body, _ = render_docgen_document("docs/state/overview.md", "../state/overview.md")
    rendered = str(body)
    # The example source is embedded with escaped quotes, so match loosely.
    assert re.search(r'colors: list\[str\] = \[\\?"var\(--gray-12\)\\?"', rendered)
    assert not re.search(r'colors: list\[str\] = \[\\?"black\\?"', rendered)
