"""The styles the typography components share."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import StyleProps

# What an element with a color of its own tells the text inside it, as Radix
# Themes does through `[data-accent-color]` ancestor selectors: a class on an
# element cannot select by ancestor, so the ancestor hands down the values.
# High-contrast text without a color takes the first, a link without a color
# the other two.
ACCENT_TEXT = "--rx-accent-text"
ACCENT_LINK = "--rx-accent-link"
ACCENT_LINK_LINE = "--rx-accent-link-line"

# The styles of `color_scheme`, for the "true" value of its variant.
ACCENT_SCOPE: dict[str, Any] = {
    ACCENT_TEXT: tokens.accent[12],
    ACCENT_LINK: tokens.accent[12],
    ACCENT_LINK_LINE: "underline",
}

# The same for an element that is high contrast too: links inside keep their
# own color. For a compound style of `color_scheme` and `high_contrast`.
ACCENT_SCOPE_HIGH_CONTRAST: dict[str, Any] = {
    ACCENT_LINK: None,
    ACCENT_LINK_LINE: None,
}

WEIGHT: dict[str, StyleProps] = {
    "light": {"font_weight": tokens.font_weight.light},
    "regular": {"font_weight": tokens.font_weight.regular},
    "medium": {"font_weight": tokens.font_weight.medium},
    "bold": {"font_weight": tokens.font_weight.bold},
}

ALIGN: dict[str, StyleProps] = {
    "left": {"text_align": "left"},
    "center": {"text_align": "center"},
    "right": {"text_align": "right"},
}


def trim(start: str, end: str) -> dict[str, StyleProps]:
    """Make the variants of the trim prop: the leading above and below a text.

    Args:
        start: What to take off above the first line.
        end: What to take off below the last line.

    Returns:
        The styles of each value of the prop.
    """
    half_leading = f"var(--line-height, calc(1em * {tokens.default.line_height})) / 2"
    none: Any = {"content": "none"}
    before: Any = {
        "content": "''",
        "display": "table",
        "margin_bottom": f"calc({start} - {half_leading})",
    }
    after: Any = {
        "content": "''",
        "display": "table",
        "margin_top": f"calc({end} - {half_leading})",
    }
    return {
        "normal": {"_before": none, "_after": none},
        "start": {"_before": before, "_after": none},
        "end": {"_before": none, "_after": after},
        "both": {"_before": before, "_after": after},
    }
