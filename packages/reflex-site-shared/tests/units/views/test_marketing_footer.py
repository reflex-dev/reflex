"""Tests for the shared marketing footer."""

from collections.abc import Iterator
from typing import Any

import pytest
from reflex_site_shared.views.marketing_footer import marketing_footer


def _walk(component: Any) -> Iterator[Any]:
    """Yield every component in a footer tree.

    Args:
        component: Root component.

    Yields:
        Each component, including its root.
    """
    yield component
    for child in component.children:
        yield from _walk(child)


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_footer_links_do_not_resolve_under_a_docs_basename(appearance):
    """Keep marketing destinations usable from independently hosted docs apps."""
    footer = marketing_footer(appearance=appearance)
    anchors = [node for node in _walk(footer) if node.tag == "a"]
    destinations = {str(node.href).strip('"') for node in anchors}

    assert "https://reflex.dev/platform/" in destinations
    assert "https://reflex.dev/docs/" in destinations
    assert "https://reflex.dev/use-cases/finance/" in destinations
    assert all(href.startswith("https://") for href in destinations)
    for anchor in anchors:
        if str(anchor.target).strip('"') == "_blank":
            assert str(anchor.rel).strip('"') == "noopener noreferrer"


def test_footer_preserves_accessible_newsletter_form_and_five_columns():
    """Keep a labeled native email form and the marketing navigation groups."""
    footer = marketing_footer(show_color_mode_toggle=True)
    nodes = list(_walk(footer))

    assert footer.tag == "footer"
    assert len([node for node in nodes if node.tag == "nav"]) == 5
    inputs = [node for node in nodes if node.tag == "input"]
    assert len(inputs) == 1
    assert str(inputs[0].name).strip('"') == "input_email"
    assert str(inputs[0].type).strip('"') == "email"
    assert str(inputs[0].id).strip('"') == "footer-newsletter-email"
    assert any(node.tag == "label" for node in nodes)
    forms = [node for node in nodes if node.tag == "form"]
    assert len(forms) == 1
    assert "on_submit" in forms[0].event_triggers
