"""Inline SVG icons used internally by Reflex UI components.

Icons are plain ``<svg>`` elements so the library carries no icon-font or
icon-library dependency. They inherit ``currentColor`` and size via classes.
"""

from __future__ import annotations

from reflex_base.components.component import Component

from reflex_components_core.el.elements.media import Path, Svg

_STROKE_ATTRS = {
    "fill": "none",
    "stroke": "currentColor",
    "strokeWidth": "2",
    "strokeLinecap": "round",
    "strokeLinejoin": "round",
}


def _stroke_icon(*paths: str, **props) -> Component:
    """Build a 24x24 stroked icon from SVG path data.

    Args:
        *paths: The SVG path definitions.
        **props: Additional props for the svg element.

    Returns:
        The svg component.
    """
    props.setdefault("custom_attrs", dict(_STROKE_ATTRS))
    props.setdefault("aria_hidden", "true")
    return Svg.create(
        *[Path.create(d=d) for d in paths],
        view_box="0 0 24 24",
        **props,
    )


def chevron_down(**props) -> Component:
    """A downward chevron icon.

    Args:
        **props: Additional props for the svg element.

    Returns:
        The svg component.
    """
    return _stroke_icon("m6 9 6 6 6-6", **props)
