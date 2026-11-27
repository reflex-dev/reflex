"""The look of a heading."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.typography import (
    ALIGN,
    COLOR,
    COLOR_HIGH_CONTRAST,
    TRIM,
    WEIGHT,
)

# The line height is a custom property, which text inside the heading follows.
SIZE: dict[str, Any] = {
    str(step): {
        "font_size": (
            f"calc({tokens.font_size[step]} * {tokens.heading.font_size_adjust})"
        ),
        "--line-height": tokens.heading.line_height[step],
        "letter_spacing": (
            f"calc({tokens.letter_spacing[step]} + {tokens.heading.letter_spacing})"
        ),
    }
    for step in (1, 2, 3, 4, 5, 6, 7, 8, 9)
}

HEADING: ComponentStyles = {
    "base": {
        "--leading-trim-start": tokens.heading.leading_trim_start,
        "--leading-trim-end": tokens.heading.leading_trim_end,
        "font_family": tokens.heading.font_family,
        "font_style": tokens.heading.font_style,
        "font_weight": tokens.font_weight.bold,
        "line_height": "var(--line-height)",
        "margin": "0",
    },
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        "align": ALIGN,
        "trim": TRIM,
        **COLOR,
    },
    "defaults": {"size": "6"},
    "compound": [COLOR_HIGH_CONTRAST],
}
