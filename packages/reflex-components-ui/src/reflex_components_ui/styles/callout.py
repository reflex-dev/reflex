"""The look of a callout: a short message with an icon beside it."""

from __future__ import annotations

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.text import TEXT_BASE
from reflex_components_ui.styles.typography import (
    ACCENT_SCOPE,
    ACCENT_SCOPE_HIGH_CONTRAST,
)

accent = tokens.accent

# What the root tells its parts, as the size of a callout is the size of
# its text in Radix Themes: the height of the icon is the height of a line.
_ICON_HEIGHT = "--callout-icon-height"
_FONT_SIZE = "--rx-callout-font-size"
_LINE_HEIGHT = "--rx-callout-line-height"
_LETTER_SPACING = "--rx-callout-letter-spacing"

# The gaps, the padding and the radius of each size.
_SIZES: dict[str, tuple[str, str, str, str]] = {
    "1": (tokens.space[2], tokens.space[2], tokens.space[3], tokens.radius[3]),
    "2": (tokens.space[2], tokens.space[3], tokens.space[4], tokens.radius[4]),
    "3": (tokens.space[3], tokens.space[4], tokens.space[5], tokens.radius[5]),
}

# The text of each size: the second size of text, and the third for the last.
_TEXT: dict[str, tuple[str, str, str]] = {
    "1": (tokens.font_size[2], tokens.line_height[2], tokens.letter_spacing[2]),
    "2": (tokens.font_size[2], tokens.line_height[2], tokens.letter_spacing[2]),
    "3": (tokens.font_size[3], tokens.line_height[3], tokens.letter_spacing[3]),
}

CALLOUT_ROOT: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "grid",
        "align_items": "flex-start",
        "justify_content": "flex-start",
        "text_align": "left",
        "color": accent.a[11],
    },
    "variants": {
        "size": {
            size: unchecked({
                "row_gap": row_gap,
                "column_gap": column_gap,
                "padding": padding,
                "border_radius": radius,
                _ICON_HEIGHT: _TEXT[size][1],
                _FONT_SIZE: _TEXT[size][0],
                _LINE_HEIGHT: _TEXT[size][1],
                _LETTER_SPACING: _TEXT[size][2],
            })
            for size, (row_gap, column_gap, padding, radius) in _SIZES.items()
        },
        "variant": {
            "soft": {"background_color": accent.a[3]},
            "surface": {
                "box_shadow": f"inset 0 0 0 1px {accent.a[6]}",
                "background_color": accent.a[2],
            },
            "outline": {"box_shadow": f"inset 0 0 0 1px {accent.a[7]}"},
        },
        "color_scheme": {"true": unchecked(ACCENT_SCOPE)},
        "high_contrast": {"true": {"color": accent[12]}},
    },
    "defaults": {"size": "2", "variant": "soft"},
    "compound": [
        {
            "props": {"color_scheme": "true", "high_contrast": "true"},
            "style": unchecked(ACCENT_SCOPE_HIGH_CONTRAST),
        },
    ],
}

CALLOUT_ICON: ComponentStyles = {
    "base": {
        "display": "flex",
        "align_items": "center",
        "grid_column_start": "-2",
        "height": f"var({_ICON_HEIGHT})",
    },
}

# Text of the size of the callout around it; outside one, of no size.
CALLOUT_TEXT: ComponentStyles = {
    "base": unchecked({
        **TEXT_BASE,
        "font_size": f"var({_FONT_SIZE})",
        "--line-height": f"var({_LINE_HEIGHT})",
        "--letter-spacing": f"var({_LETTER_SPACING})",
    }),
}
