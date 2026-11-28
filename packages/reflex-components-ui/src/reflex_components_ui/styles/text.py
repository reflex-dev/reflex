"""The look of text, and of the inline elements that mark it up."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, StyleProps, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.styles.typography import (
    ALIGN,
    COLOR,
    COLOR_HIGH_CONTRAST,
    SIZE,
    TRIM,
    WEIGHT,
)

# What every element that is text has, a link and a quotation among them.
TEXT_BASE: StyleProps = {
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
            "label": unchecked({
                "@media (pointer: coarse)": {
                    "WebkitTapHighlightColor": "transparent",
                    "_active": {
                        "outline_width": "0.75em",
                        "outline_style": "solid",
                        "outline_color": tokens.gray.a[4],
                        "outline_offset": "-0.6em",
                    },
                },
            }),
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
        # The font style is a token, where the property is typed by keywords.
        "base": unchecked({
            "font_family": element.font_family,
            "font_size": f"calc({element.font_size_adjust} * 1em)",
            "font_style": element.font_style,
            "font_weight": element.font_weight,
            "letter_spacing": (
                f"calc({element.letter_spacing} + "
                f"var(--letter-spacing, {tokens.default.letter_spacing}))"
            ),
            **style,
        }),
    }


_BOXED: dict[str, Any] = {
    "box_sizing": "border-box",
    "line_height": "1.25",
    "color": "inherit",
}

EM: ComponentStyles = _inline(tokens.em, **_BOXED)
STRONG: ComponentStyles = _inline(tokens.strong)
QUOTE: ComponentStyles = _inline(tokens.quote, **_BOXED)

# The layers of the shadow of a key, of the one appearance alone: a layer the
# other appearance has, left in as transparent, still rounds what is under it.
_KEY_SHADOW = by_appearance(
    ", ".join([
        f"inset 0 -0.05em 0.5em {tokens.gray.a[2]}",
        f"inset 0 0.05em {tokens.white.a[12]}",
        f"inset 0 0.25em 0.5em {tokens.gray.a[2]}",
        f"inset 0 -0.05em {tokens.gray.a[6]}",
        f"0 0 0 0.05em {tokens.gray.a[5]}",
        f"0 0.08em 0.17em {tokens.gray.a[7]}",
    ]),
    ", ".join([
        f"inset 0 -0.05em 0.5em {tokens.gray.a[3]}",
        f"inset 0 0.05em {tokens.gray.a[11]}",
        f"inset 0 0.25em 0.5em {tokens.gray.a[2]}",
        f"inset 0 -0.1em {tokens.black.a[11]}",
        f"0 0 0 0.075em {tokens.gray.a[7]}",
        f"0 0.08em 0.17em {tokens.black.a[12]}",
    ]),
)

KBD: ComponentStyles = {
    "base": {
        "display": "inline-flex",
        "align_items": "center",
        "justify_content": "center",
        "flex_shrink": "0",
        "font_family": tokens.default.font_family,
        "font_weight": "normal",
        "vertical_align": "text-top",
        "white_space": "nowrap",
        "user_select": "none",
        "position": "relative",
        "top": "-0.03em",
        "font_size": "0.75em",
        "min_width": "1.75em",
        "line_height": "1.7em",
        "box_sizing": "border-box",
        "padding_left": "0.5em",
        "padding_right": "0.5em",
        "padding_bottom": "0.05em",
        "word_spacing": "-0.1em",
        "border_radius": f"calc({tokens.radius.factor} * 0.35em)",
        "letter_spacing": f"var(--letter-spacing, {tokens.default.letter_spacing})",
        # Not stretched by a flex or grid container.
        "height": "fit-content",
        "color": tokens.gray[12],
        # The classic variant, the one a key has.
        "background_color": tokens.gray[1],
        "box_shadow": _KEY_SHADOW,
    },
    "variants": {
        "size": {
            str(step): unchecked({
                "font_size": f"calc({tokens.font_size[step]} * 0.8)",
                "--letter-spacing": tokens.letter_spacing[step],
            })
            for step in (1, 2, 3, 4, 5, 6, 7, 8, 9)
        },
    },
}
