"""The look of a scroll area: a box that scrolls what does not fit in it."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, CompoundStyle, unchecked

gray = tokens.gray

# Which way the area scrolls, by its scrollbars: each axis as a keyword of
# `overflow`, the first for an area that scrolls when there is too much and
# the second for one whose scrollbars always show.
_AXES: dict[str, tuple[bool, bool]] = {
    "vertical": (False, True),
    "horizontal": (True, False),
    "both": (True, True),
}


def _overflow(scrollbars: str, always: bool) -> dict[str, Any]:
    """Make the overflow of an area.

    Args:
        scrollbars: Which scrollbars the area has.
        always: Whether they show when everything fits.

    Returns:
        The overflow of each axis: an axis without a scrollbar is clipped.
    """
    horizontal, vertical = _AXES[scrollbars]
    shown = "scroll" if always else "auto"
    style: dict[str, Any] = {
        "overflow_x": shown if horizontal else "hidden",
        "overflow_y": shown if vertical else "hidden",
    }
    if horizontal:
        # No swipe back or forward in the history at the end of the area.
        style["overscroll_behavior_x"] = "contain"
    return style


_ALWAYS: list[CompoundStyle] = [
    {
        "props": {"scrollbars": scrollbars, "type": "always"},
        "style": unchecked(_overflow(scrollbars, always=True)),
    }
    for scrollbars in _AXES
]

# The area scrolls natively: the scrollbars are the ones of the browser, thin
# and in the grays Radix Themes draws its own with.
# The box of an area, without the way it scrolls.
SCROLL_BOX: Any = unchecked({
    "box_sizing": "border-box",
    "display": "flex",
    "flex_direction": "column",
    "position": "relative",
    "width": "100%",
    "height": "100%",
    "scrollbar_width": "thin",
    "scrollbar_color": f"{gray.a[8]} {gray.a[3]}",
    ":focus-visible": {
        "outline_width": "2px",
        "outline_style": "solid",
        "outline_color": tokens.focus[8],
        "outline_offset": "-2px",
    },
})

# What is inside is laid out as in any block, as wide as it needs and at
# least as wide as the area.
SCROLL_CONTENT: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "block",
        "width": "fit-content",
        "min_width": "100%",
        "flex_grow": 1,
    }
}

SCROLL_AREA: ComponentStyles = {
    "base": SCROLL_BOX,
    "variants": {
        "scrollbars": {
            scrollbars: unchecked(_overflow(scrollbars, always=False))
            for scrollbars in _AXES
        },
    },
    "defaults": {"scrollbars": "both"},
    "compound": _ALWAYS,
    "parts": {"content": SCROLL_CONTENT},
}
