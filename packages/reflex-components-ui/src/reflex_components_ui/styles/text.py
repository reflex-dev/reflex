"""The look of text, and of the inline elements that mark it up."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.typography import (
    ALIGN,
    COLOR,
    COLOR_HIGH_CONTRAST,
    SIZE,
    TRIM,
    WEIGHT,
)

# What every element that is text has, a link and a quotation among them.
TEXT_BASE: dict[str, Any] = {
    "margin": "0",
    "line_height": f"var(--line-height, {tokens.default.line_height})",
    "letter_spacing": "var(--letter-spacing, inherit)",
}

TEXT: ComponentStyles = {
    "base": TEXT_BASE,
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        "align": ALIGN,
        "trim": TRIM,
        **COLOR,
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
    "compound": [COLOR_HIGH_CONTRAST],
}


def _inline(element: Any, **style: Any) -> ComponentStyles:
    """Make the look of an inline element from its typography tokens.

    Args:
        element: The tokens of the element.
        **style: What the element has beside its font.

    Returns:
        The style table.
    """
    return {
        "base": {
            "font_family": element.font_family,
            "font_size": f"calc({element.font_size_adjust} * 1em)",
            "font_style": element.font_style,
            "font_weight": element.font_weight,
            "letter_spacing": (
                f"calc({element.letter_spacing} + "
                f"var(--letter-spacing, {tokens.default.letter_spacing}))"
            ),
            **style,
        },
    }


_BOXED: dict[str, Any] = {
    "box_sizing": "border-box",
    "line_height": "1.25",
    "color": "inherit",
}

EM: ComponentStyles = _inline(tokens.em, **_BOXED)
STRONG: ComponentStyles = _inline(tokens.strong)
QUOTE: ComponentStyles = _inline(tokens.quote, **_BOXED)
