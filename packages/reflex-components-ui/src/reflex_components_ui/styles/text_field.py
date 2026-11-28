"""The look of a text field: a box around a native input and its slots."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked

accent, gray, focus = tokens.accent, tokens.gray, tokens.focus

_HEIGHT = "--text-field-height"
_PADDING = "--text-field-padding"
_RADIUS = "--text-field-border-radius"
_BORDER = "--text-field-border-width"
_ICON = "--text-field-native-icon-size"
SELECTION = "--text-field-selection-color"
FOCUS_COLOR = "--text-field-focus-color"

# What the box hands the input and the slots inside it, which a class on
# either cannot ask of the other: the room the input leaves on a side
# without a slot, and how the slots look.
_INDENT = "--rx-text-field-indent"
_PADDING_LEFT = "--rx-text-field-padding-left"
_PADDING_RIGHT = "--rx-text-field-padding-right"
_RADIUS_LEFT = "--rx-text-field-radius-left"
_RADIUS_RIGHT = "--rx-text-field-radius-right"
_SLOT_GAP = "--rx-text-field-slot-gap"
_SLOT_PADDING = "--rx-text-field-slot-padding"
_SLOT_COLOR = "--rx-text-field-slot-color"
_SLOT_CURSOR = "--rx-text-field-slot-cursor"

_INPUT = "> :is(input, textarea)"
# The state of the box is the one of the input inside it.
FOCUSED = f":has({_INPUT}:focus)"
OFF = ":is(:disabled, :read-only)"
DISABLED = f":has({_INPUT}{OFF})"
AUTOFILLED = f":has({_INPUT}:autofill:not({OFF}))"
_LEFT_SLOT = ":has(> [data-side='left'])"
_RIGHT_SLOT = ":has(> [data-side='right'])"

# The inputs the browser lays out as several fields.
_DATES = ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])"

_INNER_RADIUS = f"calc(var({_RADIUS}) - var({_BORDER}))"


def _size(
    height: str, padding: str, radius: str, icon: str, step: int, slot: str
) -> dict[str, Any]:
    """Make the styles of one size.

    Args:
        height: The height of the box.
        padding: The room between the box and the text.
        radius: The radius of the corners.
        icon: The side of the icon the browser gives a date.
        step: The step of the type scale.
        slot: The gap and the padding of a slot.

    Returns:
        The styles.
    """
    return {
        _HEIGHT: height,
        _PADDING: f"calc({padding} - var({_BORDER}))",
        _RADIUS: f"max({radius}, {tokens.radius.full})",
        _ICON: icon,
        "font_size": tokens.font_size[step],
        "letter_spacing": tokens.letter_spacing[step],
        _SLOT_GAP: slot,
        _SLOT_PADDING: tokens.space[step],
    }


def _variant(
    border: str,
    rest: dict[str, Any],
    disabled: dict[str, Any],
    autofilled: str,
    soft: bool = False,
) -> dict[str, Any]:
    """Make the styles of one variant.

    Args:
        border: The width of the border.
        rest: The fill and the border of the box.
        disabled: What a disabled or read-only input changes of them.
        autofilled: The border of a box the browser filled in.
        soft: Whether the box takes its colors from the accent.

    Returns:
        The styles, by the state of the input.
    """
    style: dict[str, Any] = {
        SELECTION: {
            "default": accent.a[5] if soft else focus.a[5],
            DISABLED: gray.a[5],
        },
        FOCUS_COLOR: {
            "default": accent[8] if soft else focus[8],
            DISABLED: gray[8],
        },
        _BORDER: border,
        "color": accent[12] if soft else gray[12],
        _SLOT_COLOR: accent[12] if soft else gray.a[11],
    }
    for key, value in rest.items():
        style[key] = {"default": value}
    for key, value in disabled.items():
        style.setdefault(key, {})[DISABLED] = value
    style.setdefault("box_shadow", {})[AUTOFILLED] = autofilled
    if not soft:
        style["background_clip"] = "content-box"
        style.setdefault("background_image", {})[AUTOFILLED] = (
            f"linear-gradient({focus.a[2]}, {focus.a[2]})"
        )
    return style


_FILLED = f"inset 0 0 0 1px {focus.a[5]}, inset 0 0 0 1px {gray.a[5]}"
_DISABLED_FILL = f"linear-gradient({gray.a[2]}, {gray.a[2]})"

# The fill and the border of each variant, which a text area shares.
VARIANTS: dict[str, Any] = {
    "surface": unchecked(
        _variant(
            "1px",
            {
                "background_color": tokens.color.surface,
                "box_shadow": f"inset 0 0 0 var({_BORDER}) {gray.a[7]}",
            },
            {
                "background_image": _DISABLED_FILL,
                "box_shadow": f"inset 0 0 0 var({_BORDER}) {gray.a[6]}",
            },
            _FILLED,
        )
    ),
    "classic": unchecked(
        _variant(
            "1px",
            {"background_color": tokens.color.surface, "box_shadow": tokens.shadow[1]},
            {"background_image": _DISABLED_FILL},
            _FILLED,
        )
    ),
    "soft": unchecked(
        _variant(
            "0px",
            {"background_color": accent.a[3]},
            {"background_color": gray.a[3]},
            f"inset 0 0 0 1px {accent.a[5]}, inset 0 0 0 1px {gray.a[4]}",
            soft=True,
        )
    ),
}

TEXT_FIELD: ComponentStyles = {
    "base": unchecked({
        "display": {
            "default": "flex",
            # A hidden input leaves no empty box behind.
            ":has(> input:is([hidden], [type='hidden' i]))": "none",
        },
        "align_items": "stretch",
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.regular,
        "font_style": "normal",
        "text_align": "start",
        "box_sizing": "border-box",
        "height": f"var({_HEIGHT})",
        "padding": f"var({_BORDER})",
        "border_radius": f"var({_RADIUS})",
        FOCUSED: {
            "outline_width": "2px",
            "outline_style": "solid",
            "outline_color": f"var({FOCUS_COLOR})",
            "outline_offset": "-1px",
        },
        "_selection": {"background_color": f"var({SELECTION})"},
        _INDENT: {"default": f"var({_PADDING})", _LEFT_SLOT: "0"},
        _PADDING_LEFT: {"default": f"var({_PADDING})", _LEFT_SLOT: "0"},
        _PADDING_RIGHT: {"default": f"var({_PADDING})", _RIGHT_SLOT: "0"},
        _RADIUS_LEFT: {"default": _INNER_RADIUS, _LEFT_SLOT: "0"},
        _RADIUS_RIGHT: {"default": _INNER_RADIUS, _RIGHT_SLOT: "0"},
        _SLOT_CURSOR: {
            "default": "text",
            f":has({_INPUT}{OFF}:placeholder-shown)": tokens.cursor.disabled,
        },
    }),
    "variants": {
        "size": {
            "1": unchecked(
                _size(
                    tokens.space[5],
                    f"{tokens.space[1]} * 1.5",
                    tokens.radius[2],
                    tokens.space[3],
                    1,
                    tokens.space[2],
                )
            ),
            "2": unchecked(
                _size(
                    tokens.space[6],
                    tokens.space[2],
                    tokens.radius[2],
                    tokens.space[4],
                    2,
                    tokens.space[2],
                )
            ),
            "3": unchecked(
                _size(
                    tokens.space[7],
                    tokens.space[3],
                    tokens.radius[3],
                    tokens.space[4],
                    3,
                    tokens.space[3],
                )
            ),
        },
        "variant": VARIANTS,
    },
    "defaults": {"size": "2", "variant": "surface"},
}

# What a text input or a text area is before its table draws it: nothing of
# the look of the platform, as Radix Themes unsets it all.
INPUT_RESET: dict[str, Any] = {
    "appearance": "none",
    "margin": "0",
    "border_width": "0",
    "border_style": "none",
    "background_color": "transparent",
    "background_image": "none",
    "box_sizing": "border-box",
    "color": "inherit",
    "font_family": "inherit",
    "font_size": "inherit",
    "font_weight": "normal",
    "font_style": "normal",
    "line_height": "inherit",
    "letter_spacing": "inherit",
    "text_transform": "inherit",
    "word_spacing": "inherit",
    "outline_style": "none",
    "outline_width": "medium",
    "outline_color": "currentcolor",
    "outline_offset": "0",
    "white_space": "pre-wrap",
    "WebkitTapHighlightColor": "transparent",
}

# The placeholder of an input, by the variant of its box.
PLACEHOLDER: dict[str, Any] = {
    "surface": {"color": gray.a[10], "opacity": {"default": 1, OFF: 0.5}},
    "classic": {"color": gray.a[10], "opacity": {"default": 1, OFF: 0.5}},
    "soft": {"color": accent[12], "opacity": {"default": 0.6, OFF: 0.5}},
}

# A disabled or read-only input, in a text field or a text area.
INPUT_OFF: dict[str, Any] = {
    "cursor": {
        "default": "text",
        f"{OFF}:placeholder-shown": tokens.cursor.disabled,
    },
    "color": {"default": "inherit", OFF: gray.a[11]},
    "WebkitTextFillColor": {OFF: gray.a[11]},
}

# The input of a text field. Its box says how it looks, so the variants are
# not props.
TEXT_FIELD_INPUT: ComponentStyles = {
    "base": unchecked({
        **INPUT_RESET,
        **INPUT_OFF,
        "width": "100%",
        # What aligns a date in Chrome and Safari.
        "display": "flex",
        "align_items": "center",
        "text_align": "inherit",
        "border_top_left_radius": f"var({_RADIUS_LEFT})",
        "border_bottom_left_radius": f"var({_RADIUS_LEFT})",
        "border_top_right_radius": f"var({_RADIUS_RIGHT})",
        "border_bottom_right_radius": f"var({_RADIUS_RIGHT})",
        # Room on the left that does not cut a long value off at its end.
        "text_indent": {"default": f"var({_INDENT})", _DATES: "0"},
        "padding_top": "0",
        "padding_left": {"default": "0", _DATES: f"var({_PADDING_LEFT})"},
        "padding_right": {"default": "0", _DATES: f"var({_PADDING_RIGHT})"},
        # The stepper of a number and the cross of a search are left out.
        "[type='number']": {"appearance": "textfield"},
        "::-webkit-inner-spin-button": {"appearance": "none"},
        "::-webkit-search-cancel-button": {"appearance": "none"},
        "_selection": {"background_color": f"var({SELECTION})"},
        # The icon Chrome gives a date or a time.
        "::-webkit-calendar-picker-indicator": {
            "box_sizing": "content-box",
            "width": f"var({_ICON})",
            "height": f"var({_ICON})",
            "padding": tokens.space[1],
            "margin_left": {"default": tokens.space[1], "[type='time']": "0"},
            "margin_right": f"calc({tokens.space[1]} * -1)",
            "border_radius": f"calc(var({_RADIUS}) - 2px)",
        },
        ":autofill": {
            "background_clip": "text",
            "WebkitTextFillColor": gray[12],
        },
    }),
    "variants": {
        "_size": {
            # Against a jitter of the baseline where the layout around the
            # field falls on a part of a pixel.
            "1": {"padding_bottom": "0px"},
            "2": {"padding_bottom": "0.5px"},
            "3": {"padding_bottom": "0px"},
        },
        "_variant": {
            variant: unchecked({
                "_placeholder": {"user_select": "none", **placeholder},
            })
            for variant, placeholder in PLACEHOLDER.items()
        },
    },
    "defaults": {"_size": "2", "_variant": "surface"},
}

_OUT = f"calc(var({_BORDER}) * -1)"

# A slot. The box says which side a slot without one is on.
TEXT_FIELD_SLOT: ComponentStyles = {
    "base": unchecked({
        "box_sizing": "border-box",
        "flex_shrink": 0,
        "display": "flex",
        "align_items": "center",
        "cursor": f"var({_SLOT_CURSOR}, text)",
        "gap": f"var({_SLOT_GAP})",
        "padding_left": f"var({_SLOT_PADDING})",
        "padding_right": f"var({_SLOT_PADDING})",
        "color": f"var({_SLOT_COLOR})",
    }),
    "variants": {
        "_side": {
            "left": {"order": -1, "margin_left": _OUT, "margin_right": "0"},
            "right": {"order": 0, "margin_left": "0", "margin_right": _OUT},
        },
        "color_scheme": {"true": {"color": accent.a[11]}},
    },
    "defaults": {"_side": "left"},
}
