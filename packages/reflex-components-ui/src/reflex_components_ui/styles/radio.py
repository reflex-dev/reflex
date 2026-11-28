"""The look of a radio button and of a group of them."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.control import DISABLED, FOCUS, FOCUS_RING, RESET

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

_SIZE = "--radio-size"

_CHECKED_ENABLED = f":checked:not({DISABLED})"


def _look(variant: str, high_contrast: bool) -> dict[str, Any]:
    """Make the circle and the dot of one variant.

    Args:
        variant: The variant.
        high_contrast: Whether the radio button is high contrast.

    Returns:
        The styles of the two pseudo-elements, for every state of the input.
    """
    fill = accent[12] if high_contrast else accent.indicator
    dot = accent[1] if high_contrast else accent.contrast
    if variant == "surface":
        circle: dict[str, Any] = {
            "background_color": {
                "default": tokens.color.surface,
                _CHECKED_ENABLED: fill,
                DISABLED: gray.a[3],
            },
            "box_shadow": {
                "default": f"inset 0 0 0 1px {gray.a[7]}",
                _CHECKED_ENABLED: "none",
                DISABLED: f"inset 0 0 0 1px {gray.a[6]}",
            },
        }
    elif variant == "classic":
        circle = {
            "background_color": {
                "default": tokens.color.surface,
                _CHECKED_ENABLED: fill,
                DISABLED: gray.a[3],
            },
            "background_image": {
                "default": "none",
                _CHECKED_ENABLED: (
                    f"linear-gradient(to bottom, {white.a[3]}, transparent, "
                    f"{black.a[3]})"
                ),
            },
            "box_shadow": {
                "default": f"inset 0 0 0 1px {gray[7]}, {tokens.shadow[1]}",
                _CHECKED_ENABLED: (
                    f"inset 0 0.5px 0.5px {white.a[4]}, "
                    f"inset 0 -0.5px 0.5px {black.a[4]}"
                ),
                DISABLED: tokens.shadow[1],
            },
        }
    else:
        circle = {
            "background_color": {"default": accent.a[4], DISABLED: gray.a[3]},
            # A gray ring for a gray radio button.
            "outline_color": {FOCUS: accent.a[8]},
        }
        dot = accent[12] if high_contrast else accent.a[11]
    return {
        "_before": circle,
        "_after": {"background_color": {"default": dot, DISABLED: gray.a[8]}},
    }


_VARIANTS = ("classic", "surface", "soft")

# A radio button. Its group says how it looks, so the variants are not props.
RADIO: ComponentStyles = {
    "base": unchecked({
        **RESET,
        "position": "relative",
        "display": "inline-flex",
        "align_items": "center",
        "justify_content": "center",
        "vertical_align": "top",
        "flex_shrink": 0,
        "cursor": {"default": tokens.cursor.radio, DISABLED: tokens.cursor.disabled},
        # In a line of text it is as high as the line.
        "height": f"var(--line-height, var({_SIZE}))",
        "_before": {
            "content": "''",
            "display": "block",
            "height": f"var({_SIZE})",
            "width": f"var({_SIZE})",
            "border_radius": "100%",
            FOCUS: FOCUS_RING,
        },
        # The dot: as large as the circle and scaled down, which places it
        # on a part of a pixel.
        "_after": {
            ":checked": {"content": "''"},
            "pointer_events": "none",
            "position": "absolute",
            "height": f"var({_SIZE})",
            "width": f"var({_SIZE})",
            "border_radius": "100%",
            "transform": "scale(0.4)",
        },
    }),
    "variants": {
        "_size": {
            "1": unchecked({_SIZE: f"calc({tokens.space[4]} * 0.875)"}),
            "2": unchecked({_SIZE: tokens.space[4]}),
            "3": unchecked({_SIZE: f"calc({tokens.space[4]} * 1.25)"}),
        },
        "_variant": {
            variant: unchecked(_look(variant, False)) for variant in _VARIANTS
        },
    },
    "defaults": {"_size": "2", "_variant": "surface"},
    "compound": [
        {
            "props": {"_variant": variant, "_high_contrast": "true"},
            "style": unchecked(_look(variant, True)),
        }
        for variant in _VARIANTS
    ],
}

RADIO_GROUP: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "flex",
        "flex_direction": "column",
        "gap": tokens.space[1],
    },
}

# The label Radix Themes puts an item with children in: no wider than its
# text, so that the space beside it does not check the item.
RADIO_GROUP_ITEM: dict[str, Any] = {
    "display": "flex",
    "gap": "0.5em",
    "width": "fit-content",
}

# What is beside the radio button of such an item: text that may be cut off.
RADIO_GROUP_ITEM_INNER: ComponentStyles = {"base": {"min_width": 0}}
