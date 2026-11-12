"""Tests for Radix Accordion components."""

from reflex_components_radix.primitives.accordion import AccordionItem


def test_accordion_item_uses_ssr_safe_first_item_selector() -> None:
    """Use Emotion-safe selectors for the first accordion item."""
    style = AccordionItem.create().add_style()

    assert style is not None
    assert "&:first-of-type" in style
    assert not any(":first-child" in selector for selector in style)
    assert any(
        "data-variant='ghost'" in selector and ":first-of-type" in selector
        for selector in style
    )
