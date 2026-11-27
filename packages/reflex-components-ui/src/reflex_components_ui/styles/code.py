"""The look of inline code."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.typography import (
    ACCENT_SCOPE,
    ACCENT_SCOPE_HIGH_CONTRAST,
    ACCENT_TEXT,
    LINK_CODE_OUTLINE,
    LINK_CODE_SOFT,
    LINK_CODE_SOLID,
    WEIGHT,
)

# What the font size is multiplied by: a variant with a background is a
# little smaller than the text around it.
_ADJUST = "--code-variant-font-size-adjust"

SIZE: dict[str, Any] = {
    str(step): {
        "font_size": f"calc({tokens.font_size[step]} * var({_ADJUST}))",
        "line_height": tokens.line_height[step],
        "--letter-spacing": tokens.letter_spacing[step],
    }
    for step in (1, 2, 3, 4, 5, 6, 7, 8, 9)
}


def _hover(inside_link: str, otherwise: str) -> dict[str, Any]:
    """Make the background of code under the pointer.

    Args:
        inside_link: The custom property a link around the code sets.
        otherwise: The background of the code at rest.

    Returns:
        The background: it only changes inside a link.
    """
    return {
        "default": otherwise,
        "@media (hover: hover)": {":hover": f"var({inside_link}, {otherwise})"},
    }


_OUTLINE = "inset 0 0 0 max(1px, 0.033em)"

_SOFT: Any = {
    "background_color": _hover(LINK_CODE_SOFT, tokens.accent.a[3]),
    "color": tokens.accent.a[11],
}

CODE: ComponentStyles = {
    "base": {
        _ADJUST: f"calc({tokens.code.font_size_adjust} * 0.95)",
        "font_family": tokens.code.font_family,
        "font_size": f"calc(var({_ADJUST}) * 1em)",
        "font_style": tokens.code.font_style,
        "font_weight": tokens.code.font_weight,
        "line_height": "1.25",
        "letter_spacing": (
            f"calc({tokens.code.letter_spacing} + "
            f"var(--letter-spacing, {tokens.default.letter_spacing}))"
        ),
        "border_radius": f"calc((0.5px + 0.2em) * {tokens.radius.factor})",
        "box_sizing": "border-box",
        "padding_top": tokens.code.padding_top,
        "padding_left": tokens.code.padding_left,
        "padding_bottom": tokens.code.padding_bottom,
        "padding_right": tokens.code.padding_right,
        # Not stretched by a flex or grid container.
        "height": "fit-content",
    },
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        "variant": {
            "ghost": {_ADJUST: tokens.code.font_size_adjust, "padding": "0"},
            "solid": {
                "background_color": _hover(LINK_CODE_SOLID, tokens.accent.a[9]),
                "color": tokens.accent.contrast,
                "_selection": {
                    "background_color": tokens.accent[7],
                    "color": tokens.accent[12],
                },
            },
            "soft": _SOFT,
            "outline": {
                "box_shadow": f"{_OUTLINE} {tokens.accent.a[8]}",
                "color": tokens.accent.a[11],
                "background_color": {
                    "@media (hover: hover)": {
                        ":hover": f"var({LINK_CODE_OUTLINE}, transparent)"
                    },
                },
            },
            # Radix Themes has neither for code, and falls back to soft.
            "classic": _SOFT,
            "surface": _SOFT,
        },
        "color_scheme": {"true": ACCENT_SCOPE},
    },
    "defaults": {"variant": "soft"},
    "compound": [
        {
            "props": {"color_scheme": "true", "high_contrast": "true"},
            "style": ACCENT_SCOPE_HIGH_CONTRAST,
        },
        {
            "props": {"variant": "ghost", "color_scheme": "true"},
            "style": {"color": tokens.accent.a[11]},
        },
        {
            "props": {"variant": "ghost", "high_contrast": "true"},
            "style": {"color": f"var({ACCENT_TEXT})"},
        },
        {
            "props": {
                "variant": "ghost",
                "color_scheme": "true",
                "high_contrast": "true",
            },
            "style": {"color": tokens.accent[12]},
        },
        {
            "props": {"variant": "solid", "high_contrast": "true"},
            "style": {
                "background_color": tokens.accent[12],
                "color": tokens.accent[1],
                "_selection": {
                    "background_color": tokens.accent.a[11],
                    "color": tokens.accent[1],
                },
            },
        },
        *(
            {
                "props": {"variant": variant, "high_contrast": "true"},
                "style": {"color": tokens.accent[12]},
            }
            for variant in ("soft", "classic", "surface")
        ),
        {
            "props": {"variant": "outline", "high_contrast": "true"},
            "style": {
                "box_shadow": (
                    f"{_OUTLINE} {tokens.accent.a[7]}, {_OUTLINE} {tokens.gray.a[11]}"
                ),
                "color": tokens.accent[12],
            },
        },
    ],
}
