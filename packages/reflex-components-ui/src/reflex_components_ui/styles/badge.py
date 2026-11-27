"""The look of a badge."""

from __future__ import annotations

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.typography import ACCENT_SCOPE

accent = tokens.accent

_HALF_SPACE = f"calc({tokens.space[1]} * 0.5)"
_GAP = f"calc({tokens.space[1]} * 1.5)"

BADGE: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "inline-flex",
        "align_items": "center",
        "white_space": "nowrap",
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.medium,
        "font_style": "normal",
        "flex_shrink": 0,
        # Not stretched by a flex or grid container.
        "height": "fit-content",
    },
    "variants": {
        "size": {
            "1": {
                "font_size": tokens.font_size[1],
                "line_height": tokens.line_height[1],
                "letter_spacing": tokens.letter_spacing[1],
                "padding": f"{_HALF_SPACE} {_GAP}",
                "gap": _GAP,
                "border_radius": f"max({tokens.radius[1]}, {tokens.radius.full})",
            },
            "2": {
                "font_size": tokens.font_size[1],
                "line_height": tokens.line_height[1],
                "letter_spacing": tokens.letter_spacing[1],
                "padding": f"{tokens.space[1]} {tokens.space[2]}",
                "gap": _GAP,
                "border_radius": f"max({tokens.radius[2]}, {tokens.radius.full})",
            },
            "3": {
                "font_size": tokens.font_size[2],
                "line_height": tokens.line_height[2],
                "letter_spacing": tokens.letter_spacing[2],
                "padding": f"{tokens.space[1]} calc({tokens.space[2]} * 1.25)",
                "gap": tokens.space[2],
                "border_radius": f"max({tokens.radius[2]}, {tokens.radius.full})",
            },
        },
        "variant": {
            "solid": {
                "background_color": accent[9],
                "color": accent.contrast,
                "_selection": {
                    "background_color": accent[7],
                    "color": accent[12],
                },
            },
            "surface": {
                "background_color": accent.surface,
                "box_shadow": f"inset 0 0 0 1px {accent.a[6]}",
                "color": accent.a[11],
            },
            "soft": {"background_color": accent.a[3], "color": accent.a[11]},
            "outline": {
                "box_shadow": f"inset 0 0 0 1px {accent.a[8]}",
                "color": accent.a[11],
            },
        },
        "color_scheme": {"true": unchecked(ACCENT_SCOPE)},
    },
    "defaults": {"size": "1", "variant": "soft"},
    "compound": [
        {
            "props": {"variant": "solid", "high_contrast": "true"},
            "style": {
                "background_color": accent[12],
                "color": accent[1],
                "_selection": {
                    "background_color": accent.a[11],
                    "color": accent[1],
                },
            },
        },
        {
            "props": {"variant": "surface", "high_contrast": "true"},
            "style": {"color": accent[12]},
        },
        {
            "props": {"variant": "soft", "high_contrast": "true"},
            "style": {"color": accent[12]},
        },
        {
            "props": {"variant": "outline", "high_contrast": "true"},
            "style": {
                "box_shadow": (
                    f"inset 0 0 0 1px {accent.a[7]}, "
                    f"inset 0 0 0 1px {tokens.gray.a[11]}"
                ),
                "color": accent[12],
            },
        },
    ],
}
