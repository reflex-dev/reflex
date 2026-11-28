"""The look of tabs: a list of triggers, and the panel of the selected one."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.tokens import Step9

accent, gray, focus = tokens.accent, tokens.gray, tokens.focus

_HEIGHT = "--tab-height"
_PADDING_X = "--tab-padding-x"
_INNER_PADDING_X = "--tab-inner-padding-x"
_INNER_PADDING_Y = "--tab-inner-padding-y"
_INNER_RADIUS = "--tab-inner-border-radius"

# What a trigger hands the text inside it: whether it is selected, under
# the pointer, or where the keyboard is.
_WEIGHT = "--rx-tab-font-weight"
_LETTER_SPACING = "--rx-tab-letter-spacing"
_WORD_SPACING = "--rx-tab-word-spacing"
_FILL = "--rx-tab-fill"
_RING = "--rx-tab-ring"
_RING_WIDTH = "--rx-tab-ring-width"
_RING_COLOR = "--rx-tab-ring-color"
_RING_OFFSET = "--rx-tab-ring-offset"

_POINTER = "@media (hover: hover)"
_FOCUS = ":focus-visible"
SELECTED = "[aria-selected='true']"

_VERTICAL = {"vertical": {"width": "100%"}}


def _size(
    step: Step9, height: str, padding: str, inner_y: str, radius: str
) -> dict[str, Any]:
    """Make the styles of a list of one size.

    Args:
        step: The step of the type scale.
        height: The height of a trigger.
        padding: The room beside a trigger, and beside its text.
        inner_y: The room above and below the text of a trigger.
        radius: The radius of what marks a trigger under the pointer.

    Returns:
        The styles.
    """
    return {
        "font_size": tokens.font_size[step],
        "line_height": tokens.line_height[step],
        "letter_spacing": tokens.letter_spacing[step],
        _HEIGHT: height,
        _PADDING_X: padding,
        _INNER_PADDING_X: padding,
        _INNER_PADDING_Y: inner_y,
        _INNER_RADIUS: radius,
    }


TABS: ComponentStyles = {
    "variants": {"orientation": {"vertical": {"display": "flex"}}},
}

TABS_LIST: ComponentStyles = {
    "base": {
        "display": "flex",
        "justify_content": "flex-start",
        "overflow_x": "auto",
        "white_space": "nowrap",
        "font_family": tokens.default.font_family,
        "font_style": "normal",
        "scrollbar_width": "none",
        "::-webkit-scrollbar": {"display": "none"},
        "box_shadow": f"inset 0 -1px 0 0 {gray.a[5]}",
    },
    "variants": {
        "size": {
            "1": unchecked(
                _size(
                    1,
                    tokens.space[6],
                    tokens.space[1],
                    f"calc({tokens.space[1]} * 0.5)",
                    tokens.radius[1],
                )
            ),
            "2": unchecked(
                _size(
                    2,
                    tokens.space[7],
                    tokens.space[2],
                    tokens.space[1],
                    tokens.radius[2],
                )
            ),
        },
        "_orientation": {
            "vertical": {
                "display": "block",
                "box_shadow": f"inset -1px 0 0 0 {gray.a[5]}",
            },
        },
    },
    "defaults": {"size": "2"},
}

# The text of a trigger twice, as in a segmented control: the one that is
# seen, and one in the weight of a selected trigger that keeps its room.
_INNER = {
    "display": "flex",
    "align_items": "center",
    "justify_content": "center",
    "box_sizing": "border-box",
    "padding": f"var({_INNER_PADDING_Y}) var({_INNER_PADDING_X})",
    "border_radius": f"var({_INNER_RADIUS})",
}

TABS_TRIGGER: ComponentStyles = {
    "base": unchecked({
        # A button with nothing of the look of the platform.
        "appearance": "none",
        "margin": "0",
        "padding_top": "0",
        "padding_bottom": "0",
        "border_width": "0",
        "border_style": "none",
        "background_color": "transparent",
        "background_image": "none",
        "font_family": "inherit",
        "font_size": "inherit",
        "line_height": "inherit",
        "letter_spacing": "inherit",
        "word_spacing": "inherit",
        "text_transform": "inherit",
        "text_align": "inherit",
        "text_indent": "initial",
        "font_weight": "normal",
        "font_style": "normal",
        "cursor": {
            "default": tokens.cursor.button,
            ":disabled": tokens.cursor.disabled,
        },
        # The whole outline, as the browser has one of its own for the focus.
        "outline_style": "none",
        "outline_width": "medium",
        "outline_color": "currentcolor",
        "outline_offset": "0",
        "WebkitTapHighlightColor": "transparent",
        "display": "flex",
        "align_items": "center",
        "justify_content": "center",
        "flex_shrink": 0,
        "position": "relative",
        "user_select": "none",
        "box_sizing": "border-box",
        "height": f"var({_HEIGHT})",
        "padding_left": f"var({_PADDING_X})",
        "padding_right": f"var({_PADDING_X})",
        "color": {
            "default": gray.a[11],
            _POINTER: {":hover": gray[12]},
            SELECTED: gray[12],
        },
        _WEIGHT: {SELECTED: tokens.font_weight.medium},
        _LETTER_SPACING: {
            "default": tokens.tab.inactive_letter_spacing,
            SELECTED: tokens.tab.active_letter_spacing,
        },
        _WORD_SPACING: {
            "default": tokens.tab.inactive_word_spacing,
            SELECTED: tokens.tab.active_word_spacing,
        },
        _FILL: {
            _POINTER: {
                f":hover:not({_FOCUS})": gray.a[3],
                f":hover{_FOCUS}": accent.a[3],
            },
        },
        _RING: {_FOCUS: "solid"},
        _RING_WIDTH: {_FOCUS: "2px"},
        _RING_COLOR: {_FOCUS: focus[8]},
        _RING_OFFSET: {_FOCUS: "-2px"},
        # The line under the selected trigger.
        "_before": {
            SELECTED: {
                "box_sizing": "border-box",
                "content": "''",
                "height": "2px",
                "position": "absolute",
                "bottom": "0",
                "left": "0",
                "right": "0",
                "background_color": accent.indicator,
            },
        },
    }),
    "variants": {"_orientation": _VERTICAL},
    "parts": {
        "inner": {
            "base": unchecked({
                **_INNER,
                "position": "absolute",
                "font_weight": f"var({_WEIGHT}, inherit)",
                "letter_spacing": f"var({_LETTER_SPACING})",
                "word_spacing": f"var({_WORD_SPACING})",
                "background_color": f"var({_FILL}, transparent)",
                "outline_style": f"var({_RING}, none)",
                "outline_width": f"var({_RING_WIDTH}, medium)",
                "outline_color": f"var({_RING_COLOR}, currentcolor)",
                "outline_offset": f"var({_RING_OFFSET}, 0)",
            }),
        },
        "hidden": {
            "base": unchecked({
                **_INNER,
                "visibility": "hidden",
                "font_weight": tokens.font_weight.medium,
                "letter_spacing": tokens.tab.active_letter_spacing,
                "word_spacing": tokens.tab.active_word_spacing,
            }),
        },
    },
}

TABS_CONTENT: ComponentStyles = {
    "base": {
        "position": "relative",
        "outline_style": {"default": "none", _FOCUS: "solid"},
        "outline_width": {"default": "0", _FOCUS: "2px"},
        "outline_color": {_FOCUS: focus[8]},
    },
    "variants": {"_orientation": _VERTICAL},
}
