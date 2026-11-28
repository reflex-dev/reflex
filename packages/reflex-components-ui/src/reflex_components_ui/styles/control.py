"""What the tables of the native form controls share."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles

DISABLED = ":disabled"
FOCUS = ":focus-visible"

# What a checkbox, a radio button, a switch or a range is before its table
# draws it: nothing of the look of the platform, as Radix Themes unsets it all.
RESET: dict[str, Any] = {
    "appearance": "none",
    "margin": "0",
    "padding": "0",
    "border_width": "0",
    "border_style": "none",
    "background_color": "transparent",
    "background_image": "none",
    "box_sizing": "border-box",
    "color": "inherit",
    "font_size": "inherit",
    "line_height": "inherit",
    "letter_spacing": "inherit",
    "font_weight": "normal",
    "font_style": "normal",
    "text_indent": "initial",
    # The whole outline, as the browser has one of its own for the focus.
    "outline_style": "none",
    "outline_width": "medium",
    "outline_color": "currentcolor",
    "outline_offset": "0",
    "WebkitTapHighlightColor": "transparent",
}

# The ring of the keyboard's focus around a control.
FOCUS_RING: dict[str, Any] = {
    "outline_width": "2px",
    "outline_style": "solid",
    "outline_color": tokens.focus[8],
    "outline_offset": "2px",
}


def mask(path: str) -> str:
    """Make the mask that draws an icon of Radix Themes in the current color.

    Args:
        path: The path of the icon, on its grid of nine units a side.

    Returns:
        The value of ``mask-image``: the icon as an image.
    """
    return (
        "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' "
        f"d='{path}'/%3E%3C/svg%3E\")"
    )


# A group of checkboxes or of radio buttons: one below the other.
GROUP: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "flex",
        "flex_direction": "column",
        "gap": tokens.space[1],
    },
}

# The label Radix Themes puts an item with children in: no wider than its
# text, so that the space beside it does not check the item.
GROUP_ITEM: dict[str, Any] = {
    "display": "flex",
    "gap": "0.5em",
    "width": "fit-content",
}

# What is beside the input of such an item: text that may be cut off.
GROUP_ITEM_INNER: ComponentStyles = {"base": {"min_width": 0}}
