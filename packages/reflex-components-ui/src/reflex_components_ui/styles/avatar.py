"""The look of an avatar: an image over what stands in for it."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.typography import ACCENT_SCOPE

accent = tokens.accent

_SIZE = "--avatar-size"
_ONE_LETTER = "--avatar-fallback-one-letter-font-size"
_TWO_LETTERS = "--avatar-fallback-two-letters-font-size"

# The side of each size, the sizes of one and of two letters, the radius and
# the letter spacing. The larger sizes have one size of letters.
_SIZES: dict[str, tuple[str, str, str | None, str, str]] = {
    "1": (
        tokens.space[5],
        tokens.font_size[2],
        tokens.font_size[1],
        tokens.radius[2],
        tokens.letter_spacing[1],
    ),
    "2": (
        tokens.space[6],
        tokens.font_size[3],
        tokens.font_size[2],
        tokens.radius[2],
        tokens.letter_spacing[2],
    ),
    "3": (
        tokens.space[7],
        tokens.font_size[4],
        tokens.font_size[3],
        tokens.radius[3],
        tokens.letter_spacing[3],
    ),
    "4": (
        tokens.space[8],
        tokens.font_size[5],
        tokens.font_size[4],
        tokens.radius[3],
        tokens.letter_spacing[4],
    ),
    "5": (
        tokens.space[9],
        tokens.font_size[6],
        None,
        tokens.radius[4],
        tokens.letter_spacing[6],
    ),
    "6": (
        "80px",
        tokens.font_size[7],
        None,
        tokens.radius[5],
        tokens.letter_spacing[7],
    ),
    "7": (
        "96px",
        tokens.font_size[7],
        None,
        tokens.radius[5],
        tokens.letter_spacing[7],
    ),
    "8": (
        "128px",
        tokens.font_size[8],
        None,
        tokens.radius[6],
        tokens.letter_spacing[8],
    ),
    "9": (
        "160px",
        tokens.font_size[9],
        None,
        tokens.radius[6],
        tokens.letter_spacing[9],
    ),
}


def _size(
    side: str, one: str, two: str | None, radius: str, spacing: str
) -> dict[str, str]:
    """Make the styles of one size.

    Args:
        side: The width and the height.
        one: The font size of a fallback of one letter.
        two: The font size of a fallback of two letters, when it is smaller.
        radius: The radius of the corners.
        spacing: The letter spacing.

    Returns:
        The styles.
    """
    style = {
        _SIZE: side,
        _ONE_LETTER: one,
        "border_radius": f"max({radius}, {tokens.radius.full})",
        "letter_spacing": spacing,
    }
    if two is not None:
        style[_TWO_LETTERS] = two
    return style


def _fallback(font_size: str | None) -> ComponentStyles:
    """Make the table of what stands in for the image.

    Args:
        font_size: The size of its letters, when their number says it.

    Returns:
        The table.
    """
    base: dict[str, Any] = {
        "box_sizing": "border-box",
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.medium,
        "font_style": "normal",
        "z_index": 0,
        "width": "100%",
        "height": "100%",
        "display": "flex",
        "align_items": "center",
        "justify_content": "center",
        "line_height": 1,
        "border_radius": "inherit",
        "text_transform": "uppercase",
        # Under the image, which is as large: neither gives way to the
        # other. Alone it is the fallback of Radix Themes, which may shrink.
        "flex_shrink": {":not(:only-child)": 0},
        # An image that loaded is all there is to see, see-through or not.
        "visibility": {"[data-status='loaded']": "hidden"},
    }
    if font_size is not None:
        base["font_size"] = font_size
    return {
        "base": unchecked(base),
        "variants": {
            "variant": {
                "solid": {
                    "background_color": accent[9],
                    "color": accent.contrast,
                },
                "soft": {"background_color": accent.a[3], "color": accent.a[11]},
            },
        },
        "defaults": {"variant": "soft"},
        "compound": [
            {
                "props": {"variant": "solid", "high_contrast": "true"},
                "style": {"background_color": accent[12], "color": accent[1]},
            },
            {
                "props": {"variant": "soft", "high_contrast": "true"},
                "style": {"color": accent[12]},
            },
        ],
    }


AVATAR: ComponentStyles = {
    "base": unchecked({
        "box_sizing": "border-box",
        "display": "inline-flex",
        "align_items": "center",
        "justify_content": "center",
        "vertical_align": "middle",
        "user_select": "none",
        "width": f"var({_SIZE})",
        "height": f"var({_SIZE})",
        "flex_shrink": 0,
    }),
    "variants": {
        "size": {size: unchecked(_size(*values)) for size, values in _SIZES.items()},
        "color_scheme": {"true": unchecked(ACCENT_SCOPE)},
    },
    "defaults": {"size": "3"},
    "parts": {
        # By the number of letters, which says how large they are.
        "fallback": _fallback(None),
        "fallback_one": _fallback(f"var({_ONE_LETTER})"),
        "fallback_two": _fallback(f"var({_TWO_LETTERS}, var({_ONE_LETTER}))"),
        "image": {
            "base": unchecked({
                "box_sizing": "border-box",
                "display": {"default": "block", "[data-status='error']": "none"},
                "max_width": "100%",
                "width": "100%",
                "height": "100%",
                "object_fit": "cover",
                "border_radius": "inherit",
                # Over what stands in for it, which comes first.
                "flex_shrink": 0,
                "margin_left": "-100%",
            }),
        },
    },
}
