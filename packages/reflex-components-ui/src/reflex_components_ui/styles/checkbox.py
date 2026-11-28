"""The look of a checkbox: a native input drawn as a box and a check."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.control import DISABLED, FOCUS, FOCUS_RING, RESET, mask

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

_SIZE = "--checkbox-size"
_INDICATOR = "--checkbox-indicator-size"
_RADIUS = "--checkbox-border-radius"

# Checked, or neither checked nor unchecked: the box is filled either way.
_ON = ":is(:checked, :indeterminate)"
_ON_ENABLED = f"{_ON}:not({DISABLED})"

# The icons Radix Themes draws in the box.
_CHECK = mask(
    "M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 "
    "8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 "
    "3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 "
    "5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 "
    "4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 "
    "0.396414 8.53547 0.62293Z"
)
_DIVIDER = mask(
    "M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 "
    "4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 "
    "4.91421 0.75 4.5Z"
)


def _look(variant: str, high_contrast: bool) -> dict[str, Any]:
    """Make the box and the check of one variant.

    Args:
        variant: The variant.
        high_contrast: Whether the checkbox is high contrast.

    Returns:
        The styles of the two pseudo-elements, for every state of the input.
    """
    fill = accent[12] if high_contrast else accent.indicator
    check = accent[1] if high_contrast else accent.contrast
    if variant == "surface":
        box: dict[str, Any] = {
            "background_color": {
                "default": tokens.color.surface,
                _ON_ENABLED: fill,
                DISABLED: gray.a[3],
            },
            "box_shadow": {
                "default": f"inset 0 0 0 1px {gray.a[7]}",
                _ON_ENABLED: "none",
                DISABLED: f"inset 0 0 0 1px {gray.a[6]}",
            },
        }
    elif variant == "classic":
        box = {
            "background_color": {
                "default": tokens.color.surface,
                _ON_ENABLED: fill,
                DISABLED: gray.a[3],
            },
            "background_image": {
                "default": "none",
                _ON_ENABLED: (
                    f"linear-gradient(to bottom, {white.a[3]}, transparent, "
                    f"{black.a[1]})"
                ),
            },
            "box_shadow": {
                "default": f"inset 0 0 0 1px {gray.a[3]}, {tokens.shadow[1]}",
                _ON_ENABLED: (
                    f"inset 0 0.5px 0.5px {white.a[4]}, "
                    f"inset 0 -0.5px 0.5px {black.a[4]}"
                ),
                DISABLED: tokens.shadow[1],
            },
        }
    else:
        box = {"background_color": {"default": accent.a[5], DISABLED: gray.a[3]}}
        check = accent[12] if high_contrast else accent.a[11]
    return {
        "_before": box,
        "_after": {"background_color": {"default": check, DISABLED: gray.a[8]}},
    }


_VARIANTS = ("classic", "surface", "soft")


def _table(size: str, variant: str, high_contrast: str) -> ComponentStyles:
    """Make the table of a checkbox.

    Args:
        size: The name of the prop that says how large it is.
        variant: The name of the prop that says which look it has.
        high_contrast: The name of the prop that says whether it is high
            contrast.

    Returns:
        The table.
    """
    return {
        "base": unchecked({
            **RESET,
            "position": "relative",
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "vertical_align": "top",
            "flex_shrink": 0,
            "cursor": {
                "default": tokens.cursor.checkbox,
                DISABLED: tokens.cursor.disabled,
            },
            # In a line of text it is as high as the line.
            "height": f"var(--line-height, var({_SIZE}))",
            "_before": {
                "content": "''",
                "display": "block",
                "height": f"var({_SIZE})",
                "width": f"var({_SIZE})",
                "border_radius": f"var({_RADIUS})",
                FOCUS: FOCUS_RING,
            },
            # The check, or the line of a checkbox that is neither.
            "_after": {
                _ON: {"content": "''"},
                "position": "absolute",
                "width": f"var({_INDICATOR})",
                "height": f"var({_INDICATOR})",
                "transform": "translate(-50%, -50%)",
                "top": "50%",
                "left": "50%",
                "pointer_events": "none",
                "mask_image": {"default": _CHECK, ":indeterminate": _DIVIDER},
                "mask_size": "100% 100%",
                "mask_repeat": "no-repeat",
            },
        }),
        "variants": {
            size: {
                "1": unchecked({
                    _SIZE: f"calc({tokens.space[4]} * 0.875)",
                    _INDICATOR: f"calc(9px * {tokens.scaling})",
                    _RADIUS: f"calc({tokens.radius[1]} * 0.875)",
                }),
                "2": unchecked({
                    _SIZE: tokens.space[4],
                    _INDICATOR: f"calc(10px * {tokens.scaling})",
                    _RADIUS: tokens.radius[1],
                }),
                "3": unchecked({
                    _SIZE: f"calc({tokens.space[4]} * 1.25)",
                    _INDICATOR: f"calc(12px * {tokens.scaling})",
                    _RADIUS: f"calc({tokens.radius[1]} * 1.25)",
                }),
            },
            variant: {look: unchecked(_look(look, False)) for look in _VARIANTS},
        },
        "defaults": {size: "2", variant: "surface"},
        "compound": [
            {
                "props": {variant: look, high_contrast: "true"},
                "style": unchecked(_look(look, True)),
            }
            for look in _VARIANTS
        ],
    }


CHECKBOX: ComponentStyles = _table("size", "variant", "high_contrast")

# A checkbox of a group, which says how it looks: the variants are not props.
CHECKBOX_GROUP_ITEM: ComponentStyles = _table("_size", "_variant", "_high_contrast")
