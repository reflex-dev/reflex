"""The stylesheet of a part of Reflex's own interface."""

from reflex_base.components.component import Component

from reflex_components_core.el.elements.metadata import StyleEl


def static_style(name: str, css: str) -> Component:
    """Create a stylesheet that needs no styling library in the page.

    The connection indicator, the badge and the error boundary are part of
    every app, so they are styled with class names and plain CSS rather than
    a ``css`` prop, which only Emotion applies. React keeps one copy of the
    stylesheet per name at the start of the document head, wherever and
    however often it is rendered: its rules stay unlayered single class
    selectors, as Emotion's were, and a ``css`` prop added to one of the
    elements still overrides them.

    Args:
        name: What tells the stylesheet from any other in the document.
        css: The rules.

    Returns:
        The style element.
    """
    return StyleEl.create(css, custom_attrs={"href": name, "precedence": "reflex"})
