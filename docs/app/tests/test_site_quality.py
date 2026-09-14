"""Regression checks for shared documentation presentation."""

import reflex as rx

from reflex_docs.pages.docs.source import stacked_description_rows
from reflex_docs.pages.docs_landing.views.ai_builder import card
from reflex_docs.pages.docs_landing.views.link_item import link_item
from reflex_docs.templates.docpage.docpage import breadcrumb


def test_mobile_breadcrumb_drawer_has_a_named_button_trigger():
    """The mobile navigation overlay must be keyboard and screen-reader usable."""
    rendered = str(breadcrumb("/getting-started/introduction/", rx.el.nav()))
    assert '"aria-label":"Open documentation navigation"' in rendered


def test_landing_card_link_has_an_accessible_name():
    """Overlay links remain understandable without the surrounding visual card."""
    rendered = str(link_item("BookOpen01Icon", "Learn Reflex", "Start here", "/intro/"))
    assert "aria-label" in rendered and "Learn Reflex" in rendered


def test_ai_card_focus_outline_is_inside_the_clipped_card():
    """The overlay's focus indicator must fit within the rounded clipping box."""
    rendered = str(card("AI Builder", "Build an app", "Preview", "/ai/"))
    assert "focus-visible:-outline-offset-4" in rendered
    assert "focus-visible:outline-offset-4" not in rendered


def test_responsive_description_is_rendered_once():
    """Mobile and desktop layouts share one description and its element IDs."""
    calls = []

    def description():
        """Return content with a document-wide unique anchor."""
        calls.append(True)
        return rx.el.p("Field description", id="unique-description")

    rows = stacked_description_rows([(rx.text("Field"), "")], description, "2xl")
    assert len(calls) == 1
    assert sum(str(row).count('id:"unique-description"') for row in rows) == 1


def test_deferred_demo_preserves_code_and_defers_only_the_preview():
    """Heavy previews can wait for the viewport while their code stays readable."""
    from reflex_docs.docgen_pipeline import render_markdown

    rendered = str(
        render_markdown(
            '```python demo exec defer\nimport reflex as rx\ndef preview():\n    return rx.text("Preview")\n```'
        )
    )
    assert "DeferredDemo" in rendered
    assert "Preview" in rendered
    assert "rx.text" in rendered
