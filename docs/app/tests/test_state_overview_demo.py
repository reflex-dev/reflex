"""Regression coverage for the State overview page's color-cycling example."""

import re
from pathlib import Path

import pytest
import reflex as rx
from reflex_base.registry import RegistrationContext

from reflex_docs.docgen_pipeline import render_docgen_document

DOCS = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_registration():
    """Keep the demo's state class out of the shared registries other tests use."""
    with RegistrationContext(
        _config=rx.Config(app_name="reflex_docs", frontend_path="/docs")
    ):
        yield


def test_example_heading_starts_theme_aware():
    """The first color is the theme foreground, not black, so it reads in dark mode."""
    # A test-specific virtual path keeps the demo's state class from colliding
    # with the one test_docgen_double_eval registers for the real page.
    body, _ = render_docgen_document(
        "docs/state/overview_heading_test.md", str(DOCS / "state" / "overview.md")
    )
    rendered = str(body)
    # The example source is embedded with escaped quotes, so match loosely.
    assert re.search(r'colors: list\[str\] = \[\\?"var\(--gray-12\)\\?"', rendered)
    assert not re.search(r'colors: list\[str\] = \[\\?"black\\?"', rendered)
