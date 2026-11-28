"""The look of a text area: a box around a native textarea."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.text_field import (
    AUTOFILLED,
    DISABLED,
    INPUT_RESET,
    OFF,
)

accent, gray, focus = tokens.accent, tokens.gray, tokens.focus

_BORDER = "--text-area-border-width"
_PADDING_Y = "--text-area-padding-y"
_PADDING_X = "--text-area-padding-x"

_FOCUSED = ":focus-within"
_FILLED = f"inset 0 0 0 1px {focus.a[5]}, inset 0 0 0 1px {gray.a[5]}"
_DISABLED_FILL = f"linear-gradient({gray.a[2]}, {gray.a[2]})"


def _ring(color: str) -> dict[str, Any]:
    """Make the color of the ring of a focused text area.

    Args:
        color: The color around a text area that takes text.

    Returns:
        The color, by whether the text area takes text.
    """
    return {
        "outline_color": {
            f"{_FOCUSED}:not({DISABLED})": color,
            f"{_FOCUSED}{DISABLED}": gray[8],
        },
    }


def _input_size(y: str, x: str, step: int) -> dict[str, Any]:
    """Make the styles of the textarea of one size.

    Args:
        y: The room above and below the text.
        x: The room beside it.
        step: The step of the type scale.

    Returns:
        The styles.
    """
    return {
        _PADDING_Y: f"calc({y} - var({_BORDER}))",
        _PADDING_X: f"calc({x} - var({_BORDER}))",
        "font_size": tokens.font_size[step],
        "line_height": tokens.line_height[step],
        "letter_spacing": tokens.letter_spacing[step],
    }


TEXT_AREA: ComponentStyles = {
    "base": unchecked({
        "display": "flex",
        "flex_direction": "column",
        "box_sizing": "border-box",
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.regular,
        "font_style": "normal",
        "text_align": "start",
        # What lets the box be resized.
        "overflow": "hidden",
        "padding": f"var({_BORDER})",
        _FOCUSED: {
            "outline_width": "2px",
            "outline_style": "solid",
            "outline_offset": "-1px",
        },
    }),
    "variants": {
        "size": {
            "1": {"min_height": tokens.space[8], "border_radius": tokens.radius[2]},
            "2": {"min_height": tokens.space[9], "border_radius": tokens.radius[2]},
            "3": {"min_height": "80px", "border_radius": tokens.radius[3]},
        },
        "variant": {
            "surface": unchecked({
                _BORDER: "1px",
                "background_clip": "content-box",
                "background_color": tokens.color.surface,
                "background_image": {
                    AUTOFILLED: f"linear-gradient({focus.a[2]}, {focus.a[2]})",
                    DISABLED: _DISABLED_FILL,
                },
                "box_shadow": {
                    "default": f"inset 0 0 0 var({_BORDER}) {gray.a[7]}",
                    AUTOFILLED: _FILLED,
                    DISABLED: f"inset 0 0 0 var({_BORDER}) {gray.a[6]}",
                },
                "color": gray[12],
                **_ring(focus[8]),
            }),
            "classic": unchecked({
                _BORDER: "1px",
                "background_clip": "content-box",
                "background_color": tokens.color.surface,
                "background_image": {
                    AUTOFILLED: f"linear-gradient({focus.a[2]}, {focus.a[2]})",
                    DISABLED: _DISABLED_FILL,
                },
                "box_shadow": {"default": tokens.shadow[1], AUTOFILLED: _FILLED},
                "color": gray[12],
                **_ring(focus[8]),
            }),
            "soft": unchecked({
                _BORDER: "0px",
                "background_color": {"default": accent.a[3], DISABLED: gray.a[3]},
                "box_shadow": {
                    AUTOFILLED: (
                        f"inset 0 0 0 1px {accent.a[5]}, inset 0 0 0 1px {gray.a[4]}"
                    ),
                },
                "color": accent[12],
                # A gray ring for a gray text area.
                **_ring(accent[8]),
            }),
        },
        "resize": {
            "none": {"resize": "none"},
            "vertical": {"resize": "vertical"},
            "horizontal": {"resize": "horizontal"},
            "both": {"resize": "both"},
        },
    },
    "defaults": {"size": "2", "variant": "surface"},
}

_SCROLLBAR_PART: dict[str, Any] = {
    "background_clip": "content-box",
    "border_width": tokens.space[1],
    "border_style": "solid",
    "border_color": "transparent",
    "border_radius": tokens.space[3],
}


def _placeholder(color: str, opacity: float) -> dict[str, Any]:
    """Make the placeholder and the selection of the textarea of a variant.

    Args:
        color: The color of the placeholder.
        opacity: How much of it shows in a textarea that takes text.

    Returns:
        The styles.
    """
    return {
        "_placeholder": {
            "user_select": "none",
            "color": color,
            "opacity": {"default": opacity, OFF: 0.5},
        },
    }


# The textarea. Its box says how it looks, so the variants are not props.
TEXT_AREA_INPUT: ComponentStyles = {
    "base": unchecked({
        **INPUT_RESET,
        "border_radius": "inherit",
        "resize": "none",
        "display": "block",
        "width": "100%",
        "flex_grow": 1,
        "text_align": "start",
        "text_indent": "initial",
        "padding": f"var({_PADDING_Y}) var({_PADDING_X})",
        # An arrow over the scrollbar, and over a text area that takes no
        # text and has none.
        "cursor": {
            "default": "auto",
            f"{OFF}:not(:placeholder-shown)": "text",
            f"{OFF}:placeholder-shown": tokens.cursor.disabled,
        },
        "color": {"default": "inherit", OFF: gray.a[11]},
        "WebkitTextFillColor": {OFF: gray.a[11], ":autofill": gray[12]},
        "background_clip": {":autofill": "text"},
        "::-webkit-scrollbar": {
            "width": tokens.space[3],
            "height": tokens.space[3],
        },
        "::-webkit-scrollbar-track": {
            **_SCROLLBAR_PART,
            "background_color": gray.a[3],
        },
        "::-webkit-scrollbar-thumb": {
            **_SCROLLBAR_PART,
            "background_color": gray.a[8],
        },
    }),
    "variants": {
        "_size": {
            "1": unchecked(_input_size(tokens.space[1], f"{tokens.space[1]} * 1.5", 1)),
            "2": unchecked(_input_size(f"{tokens.space[1]} * 1.5", tokens.space[2], 2)),
            "3": unchecked(_input_size(tokens.space[2], tokens.space[3], 3)),
        },
        "_variant": {
            "surface": unchecked({
                **_placeholder(gray.a[10], 1),
                "_selection": {"background_color": {OFF: gray.a[5]}},
            }),
            "classic": unchecked({
                **_placeholder(gray.a[10], 1),
                "_selection": {"background_color": {OFF: gray.a[5]}},
            }),
            "soft": unchecked({
                **_placeholder(accent[12], 0.65),
                # A gray selection in a gray text area.
                "_selection": {
                    "background_color": {"default": accent.a[5], OFF: gray.a[5]},
                },
            }),
        },
    },
    "defaults": {"_size": "2", "_variant": "surface"},
}
