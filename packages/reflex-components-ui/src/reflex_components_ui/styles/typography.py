"""The styles the typography components share."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import StyleProps

# What an element with a color of its own tells the text inside it, as Radix
# Themes does through `[data-accent-color]` ancestor selectors: a class on an
# element cannot select by ancestor, so the ancestor hands down the values.
# High-contrast text without a color takes the first, a link without a color
# the others.
ACCENT_TEXT = "--rx-accent-text"
ACCENT_LINK = "--rx-accent-link"
ACCENT_LINK_LINE = "--rx-accent-link-line"
ACCENT_LINK_LINE_COLOR = "--rx-accent-link-line-color"

# The same from a link to the code inside it: what the code shows under the
# pointer, by its variant.
LINK_CODE_SOLID = "--rx-link-code-solid"
LINK_CODE_SOFT = "--rx-link-code-soft"
LINK_CODE_OUTLINE = "--rx-link-code-outline"


def underline_color(step: int) -> str:
    """Mix the color of the line under a link, which keeps bright colors legible.

    Args:
        step: The translucent step of the accent.

    Returns:
        The color.
    """
    return f"color-mix(in oklab, {tokens.accent.a[step]}, {tokens.gray.a[6]})"


# The styles of `color_scheme`, for the "true" value of its variant.
ACCENT_SCOPE: dict[str, Any] = {
    ACCENT_TEXT: tokens.accent[12],
    ACCENT_LINK: tokens.accent[12],
    ACCENT_LINK_LINE: "underline",
    ACCENT_LINK_LINE_COLOR: underline_color(6),
}

# The same for an element that is high contrast too: links inside keep their
# own color. For a compound style of `color_scheme` and `high_contrast`.
ACCENT_SCOPE_HIGH_CONTRAST: dict[str, Any] = {
    ACCENT_LINK: None,
    ACCENT_LINK_LINE: None,
    ACCENT_LINK_LINE_COLOR: None,
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


# The line height and the letter spacing of a size are custom properties, so
# that text and code inside the element follow them.
SIZE: dict[str, Any] = {
    str(step): {
        "font_size": tokens.font_size[step],
        "--line-height": tokens.line_height[step],
        "--letter-spacing": tokens.letter_spacing[step],
    }
    for step in (1, 2, 3, 4, 5, 6, 7, 8, 9)
}

# Half of the leading is taken off by a pseudo-element with a negative margin.
# A heading sets the two custom properties to the trim of its own font.
_HALF_LEADING = f"var(--line-height, calc(1em * {tokens.default.line_height})) / 2"
_NO_TRIM: Any = {"content": "none"}
_TRIM_START: Any = {
    "content": "''",
    "display": "table",
    "margin_bottom": (
        f"calc(var(--leading-trim-start, {tokens.default.leading_trim_start})"
        f" - {_HALF_LEADING})"
    ),
}
_TRIM_END: Any = {
    "content": "''",
    "display": "table",
    "margin_top": (
        f"calc(var(--leading-trim-end, {tokens.default.leading_trim_end})"
        f" - {_HALF_LEADING})"
    ),
}
TRIM: dict[str, StyleProps] = {
    "normal": {"_before": _NO_TRIM, "_after": _NO_TRIM},
    "start": {"_before": _TRIM_START, "_after": _NO_TRIM},
    "end": {"_before": _NO_TRIM, "_after": _TRIM_END},
    "both": {"_before": _TRIM_START, "_after": _TRIM_END},
}

# The color of text with a color of its own, for the variants of
# `color_scheme` and `high_contrast` and their compound style.
COLOR: dict[str, dict[str, Any]] = {
    "color_scheme": {"true": {**ACCENT_SCOPE, "color": tokens.accent.a[11]}},
    # Inside an element with a color; no declaration anywhere else.
    "high_contrast": {"true": {"color": f"var({ACCENT_TEXT})"}},
}
COLOR_HIGH_CONTRAST: Any = {
    "props": {"color_scheme": "true", "high_contrast": "true"},
    "style": {**ACCENT_SCOPE_HIGH_CONTRAST, "color": tokens.accent[12]},
}
