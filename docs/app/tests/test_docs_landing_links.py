"""Tests for category navigation on the docs landing page."""


def test_component_link_is_a_padded_single_navigation_target():
    """Keep category hover backgrounds padded without nesting a button in a link."""
    import reflex_docs.pages  # noqa: F401
    from reflex_docs.pages.docs_landing.views.framework import component_link

    link = component_link("Data Display", "/data-display/")

    assert str(link.to).strip('"') == "/library/data-display/"
    assert all(child.tag != "GradientButton" for child in link.children)
    classes = str(link.class_name)
    assert "px-3" in classes
    assert "rounded-lg" in classes
    assert "focus-visible:outline-ring" in classes


def test_framework_card_link_contains_its_label_and_focus_style():
    """Cards must expose their visible content as the link's accessible name."""
    import reflex_docs.pages  # noqa: F401
    from reflex_docs.pages.docs_landing.views.framework import docs_item

    card = docs_item("DatabaseIcon", "Database", "Store your data", "/database/")
    assert type(card).__name__ == "ReactRouterLink"
    assert "Database" in str(card)
    assert "focus-visible:outline-ring" in str(card.class_name)
