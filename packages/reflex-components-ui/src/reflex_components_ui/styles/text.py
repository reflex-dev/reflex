"""The look of text."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.typography import (
    ACCENT_SCOPE,
    ACCENT_SCOPE_HIGH_CONTRAST,
    ACCENT_TEXT,
    ALIGN,
    WEIGHT,
    trim,
)

# The line height and the letter spacing are custom properties, so that text
# and code inside the element follow its size.
SIZE: dict[str, Any] = {
    str(step): {
        "font_size": tokens.font_size[step],
        "--line-height": tokens.line_height[step],
        "--letter-spacing": tokens.letter_spacing[step],
    }
    for step in (1, 2, 3, 4, 5, 6, 7, 8, 9)
}

TEXT: ComponentStyles = {
    "base": {
        "margin": "0",
        "line_height": f"var(--line-height, {tokens.default.line_height})",
        "letter_spacing": "var(--letter-spacing, inherit)",
    },
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        "align": ALIGN,
        "trim": trim(
            f"var(--leading-trim-start, {tokens.default.leading_trim_start})",
            f"var(--leading-trim-end, {tokens.default.leading_trim_end})",
        ),
        "color_scheme": {"true": {**ACCENT_SCOPE, "color": tokens.accent.a[11]}},
        # Inside an element with a color; no declaration otherwise.
        "high_contrast": {"true": {"color": f"var({ACCENT_TEXT})"}},
        "as_": {
            "label": {
                "@media (pointer: coarse)": {
                    "WebkitTapHighlightColor": "transparent",
                    "_active": {
                        "outline_width": "0.75em",
                        "outline_style": "solid",
                        "outline_color": tokens.gray.a[4],
                        "outline_offset": "-0.6em",
                    },
                },
            },
        },
    },
    "compound": [
        {
            "props": {"color_scheme": "true", "high_contrast": "true"},
            "style": {**ACCENT_SCOPE_HIGH_CONTRAST, "color": tokens.accent[12]},
        },
    ],
}
