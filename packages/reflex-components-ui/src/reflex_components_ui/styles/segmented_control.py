"""The look of a segmented control: a row of items and what marks the chosen one."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.tokens import Step9

gray, focus = tokens.gray, tokens.focus

_RADIUS = "--segmented-control-border-radius"
_DURATION = "100ms"
_FADE = "80ms"

# What the control hands its items and its indicator, which a class on
# either cannot ask of the other: how many items there are and which one is
# chosen, and the size of the labels.
COUNT = "--rx-segmented-count"
INDEX = "--rx-segmented-index"
# The index of the chosen item of a control whose items are not counted
# while compiling, from its value.
INDEX_OF_VALUE = "--rx-segmented-index-of-value"
_SHOWN = "--rx-segmented-indicator"
_FONT_SIZE = "--rx-segmented-font-size"
_LETTER_SPACING = "--rx-segmented-letter-spacing"
_PADDING = "--rx-segmented-padding"
_GAP = "--rx-segmented-gap"
_SEPARATOR_DURATION = "--rx-segmented-separator-duration"
# What an item hands the elements inside it: whether it is chosen.
_ACTIVE = "--rx-segmented-active-opacity"
_INACTIVE = "--rx-segmented-inactive-opacity"
_ACTIVE_EASING = "--rx-segmented-active-easing"
_INACTIVE_EASING = "--rx-segmented-inactive-easing"
_HOVER = "--rx-segmented-hover"

# The state of an item is the one of the radio button inside it.
_ON = ":has(> input:checked)"
_FOCUSED = ":has(> input:focus-visible)"

# How many items the table places the indicator for. A control with more
# literal items is given the further conditions as its own style.
PLACED = 10


def chosen(position: int) -> str:
    """Make the condition of a control whose chosen item is at a position.

    Args:
        position: The position of the item among the children, from 1.

    Returns:
        The condition.
    """
    return f":has(> :nth-child({position}) > input:checked)"


def _size(
    radius: str, height: str, step: Step9, padding: str, gap: str
) -> dict[str, Any]:
    """Make the styles of one size.

    Args:
        radius: The radius of the corners.
        height: The height of the control.
        step: The step of the type scale.
        padding: The room beside the text of an item.
        gap: The gap between what an item holds.

    Returns:
        The styles.
    """
    return {
        _RADIUS: f"max({radius}, {tokens.radius.full})",
        "height": height,
        _FONT_SIZE: tokens.font_size[step],
        _LETTER_SPACING: tokens.letter_spacing[step],
        _PADDING: padding,
        _GAP: gap,
    }


SEGMENTED_CONTROL: ComponentStyles = {
    "base": unchecked({
        "box_sizing": "border-box",
        "display": "inline-grid",
        "vertical_align": "top",
        "grid_auto_flow": "column",
        "grid_auto_columns": "1fr",
        "align_items": "stretch",
        "color": gray[12],
        "background_color": tokens.color.surface,
        "background_image": f"linear-gradient({gray.a[3]}, {gray.a[3]})",
        "position": "relative",
        "min_width": "max-content",
        "font_family": tokens.default.font_family,
        "font_style": "normal",
        "text_align": "center",
        # A stacking context: the indicator is behind the items, inside it.
        "isolation": "isolate",
        "border_radius": f"var({_RADIUS})",
        _SHOWN: {"default": "none", ":has(> label > input:checked)": "block"},
        INDEX: {
            "default": f"var({INDEX_OF_VALUE}, 0)",
            **{chosen(position): position - 1 for position in range(1, PLACED + 1)},
        },
        # A separator hidden by the ring of the focus does not fade.
        _SEPARATOR_DURATION: {"default": _FADE, ":has(:focus-visible)": "0ms"},
    }),
    "variants": {
        "size": {
            "1": unchecked(
                _size(
                    tokens.radius[2],
                    tokens.space[5],
                    1,
                    tokens.space[3],
                    tokens.space[1],
                )
            ),
            "2": unchecked(
                _size(
                    tokens.radius[2],
                    tokens.space[6],
                    2,
                    tokens.space[4],
                    tokens.space[2],
                )
            ),
            "3": unchecked(
                _size(
                    tokens.radius[3],
                    tokens.space[7],
                    3,
                    tokens.space[4],
                    tokens.space[3],
                )
            ),
        },
    },
    "defaults": {"size": "2", "variant": "surface"},
    "parts": {
        # What marks the chosen item: as wide as one, and moved to it.
        "indicator": {
            "base": unchecked({
                "display": f"var({_SHOWN})",
                "position": "absolute",
                "z_index": -1,
                "top": "0",
                "left": "0",
                "height": "100%",
                "width": f"calc(100% / var({COUNT}))",
                "transform": f"translateX(calc(var({INDEX}) * 100%))",
                "pointer_events": "none",
                "transition_property": "transform",
                "transition_timing_function": "cubic-bezier(0.445, 0.05, 0.55, 0.95)",
                "transition_duration": _DURATION,
                "_before": {
                    "inset": "1px",
                    "position": "absolute",
                    "border_radius": f"max(0.5px, calc(var({_RADIUS}) - 1px))",
                    "background_color": (
                        f"light-dark({tokens.color.background}, {gray.a[3]})"
                    ),
                    "content": "''",
                },
            }),
            "variants": {
                "variant": {
                    "surface": {"_before": {"box_shadow": f"0 0 0 1px {gray.a[4]}"}},
                    "classic": {"_before": {"box_shadow": tokens.shadow[2]}},
                },
            },
            "defaults": {"variant": "surface"},
        },
    },
}

# An item: a label around its radio button, which is not seen.
SEGMENTED_CONTROL_ITEM: ComponentStyles = {
    "base": unchecked({
        "display": "flex",
        "align_items": "stretch",
        "user_select": "none",
        "margin": "0",
        "padding": "0",
        # As the button an item of Radix Themes is has none.
        "border_width": "0",
        "border_style": "none",
        "cursor": tokens.cursor.button,
        "WebkitTapHighlightColor": "transparent",
        "border_top_left_radius": {":first-child": "inherit", _FOCUSED: "inherit"},
        "border_bottom_left_radius": {":first-child": "inherit", _FOCUSED: "inherit"},
        # The last item, before the indicator.
        "border_top_right_radius": {
            ":nth-last-child(2)": "inherit",
            _FOCUSED: "inherit",
        },
        "border_bottom_right_radius": {
            ":nth-last-child(2)": "inherit",
            _FOCUSED: "inherit",
        },
        _FOCUSED: {
            "outline_width": "2px",
            "outline_style": "solid",
            "outline_color": focus[8],
            "outline_offset": "-1px",
        },
        _ACTIVE: {"default": 0, _ON: 1},
        _INACTIVE: {"default": 1, _ON: 0},
        _ACTIVE_EASING: {"default": "ease-in", _ON: "ease-out"},
        _INACTIVE_EASING: {"default": "ease-out", _ON: "ease-in"},
        _HOVER: {
            "@media (hover: hover)": {f":hover:not({_ON})": gray.a[2]},
        },
    }),
    "parts": {
        "input": {
            "base": {
                "appearance": "none",
                "position": "absolute",
                "inset": "0",
                "margin": "0",
                "opacity": 0,
                "pointer_events": "none",
            },
        },
        # The line between two items, behind the indicator. A rule of
        # base.css hides it beside the chosen item.
        "separator": {
            "base": unchecked({
                "z_index": -1,
                "margin_top": "3px",
                "margin_bottom": "3px",
                "margin_left": "-0.5px",
                "margin_right": "-0.5px",
                "width": "1px",
                "background_color": gray.a[4],
                "opacity": "var(--rx-segmented-separator-opacity, 1)",
                "transition_property": "opacity",
                "transition_duration": f"var({_SEPARATOR_DURATION})",
                "transition_timing_function": (
                    "var(--rx-segmented-separator-easing, ease-out)"
                ),
            }),
        },
        "label": {
            "base": unchecked({
                "box_sizing": "border-box",
                "display": "flex",
                "flex_grow": 1,
                "align_items": "center",
                "justify_content": "center",
                "border_radius": "inherit",
                "font_size": f"var({_FONT_SIZE})",
                "letter_spacing": f"var({_LETTER_SPACING})",
                "padding_left": f"var({_PADDING})",
                "padding_right": f"var({_PADDING})",
                "gap": f"var({_GAP})",
                "background_color": f"var({_HOVER}, transparent)",
            }),
        },
        # The text of an item twice, medium and regular: the chosen item
        # shows the first, and both take the room of the wider.
        "active": {
            "base": unchecked({
                "transition_property": "opacity",
                "transition_duration": _FADE,
                "transition_timing_function": f"var({_ACTIVE_EASING})",
                "font_weight": tokens.font_weight.medium,
                "letter_spacing": tokens.tab.active_letter_spacing,
                "word_spacing": tokens.tab.active_word_spacing,
                "opacity": f"var({_ACTIVE})",
            }),
        },
        "inactive": {
            "base": unchecked({
                "position": "absolute",
                "transition_property": "opacity",
                "transition_duration": _FADE,
                "transition_timing_function": f"var({_INACTIVE_EASING})",
                "font_weight": tokens.font_weight.regular,
                "letter_spacing": tokens.tab.inactive_letter_spacing,
                "word_spacing": tokens.tab.inactive_word_spacing,
                "opacity": f"var({_INACTIVE})",
            }),
        },
    },
}
