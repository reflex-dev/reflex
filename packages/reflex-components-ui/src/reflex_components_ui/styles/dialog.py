"""The look of a dialog: a native ``dialog`` over the page, and the panel in it."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.heading import HEADING
from reflex_components_ui.styles.text import TEXT

_PADDING = "--dialog-content-padding"

MOTION = "@media (prefers-reduced-motion: no-preference)"
OPEN = "[open]"
_EASING = "cubic-bezier(0.16, 1, 0.3, 1)"

# What a dialog hands its panel, which comes in when the dialog opens and
# goes out before it closes: where it goes, and how long it takes.
SHOWN = "--rx-dialog-shown"
GONE = "--rx-dialog-gone"
DURATION = "--rx-dialog-duration"

# The element around the parts of a dialog, which is nothing to the layout.
DIALOG_ROOT: ComponentStyles = {"base": {"display": "contents"}}

# What a `dialog` is before a table draws it: nothing of the box the browser
# gives one. It stays in the top layer until what is inside has gone out.
SURFACE: dict[str, Any] = {
    "margin": "0",
    "padding": "0",
    "border_width": "0",
    "border_style": "none",
    "background_color": "transparent",
    "color": "inherit",
    "max_width": "none",
    "max_height": "none",
    "outline_style": "none",
    "::backdrop": {"background_color": "transparent"},
    "transition_property": "display, overlay",
    "transition_duration": {"default": "0s", MOTION: f"var({DURATION})"},
    SHOWN: {"default": 0, OPEN: 1},
}

# The dialog itself covers the page, and scrolls a panel taller than it.
DIALOG: ComponentStyles = {
    "base": unchecked({
        **SURFACE,
        "position": "fixed",
        "inset": "0",
        "width": "100%",
        "height": "100%",
        "display": {"default": "none", OPEN: "flex"},
        "overflow": "auto",
        GONE: {"default": "translateY(5px) scale(0.99)", OPEN: "none"},
        DURATION: {"default": "160ms", OPEN: "200ms"},
        "_before": {
            "position": "fixed",
            "content": "''",
            "inset": "0",
            "background_color": tokens.color.overlay,
            "opacity": {"default": 0, OPEN: {"default": 1, "@starting-style": 0}},
            "transition_property": "opacity",
            "transition_duration": {"default": "0s", MOTION: f"var({DURATION})"},
            "transition_timing_function": _EASING,
        },
    }),
    "parts": {
        "pad": {
            "base": {
                "flex_grow": 1,
                "margin": "auto",
                "padding_top": tokens.space[6],
                "padding_bottom": f"max({tokens.space[6]}, 6vh)",
                "padding_left": tokens.space[4],
                "padding_right": tokens.space[4],
            },
        },
    },
}


def _size(padding: str, radius: str) -> dict[str, Any]:
    """Make the styles of a panel of one size.

    Args:
        padding: The room around what the panel holds.
        radius: The radius of its corners.

    Returns:
        The styles.
    """
    return {_PADDING: padding, "border_radius": radius}


DIALOG_CONTENT: ComponentStyles = {
    "base": unchecked({
        "margin": "auto",
        "width": "100%",
        "max_width": "600px",
        "z_index": 1,
        "position": "relative",
        "box_sizing": "border-box",
        "overflow": "auto",
        "--inset-padding-top": f"var({_PADDING})",
        "--inset-padding-right": f"var({_PADDING})",
        "--inset-padding-bottom": f"var({_PADDING})",
        "--inset-padding-left": f"var({_PADDING})",
        "padding": f"var({_PADDING})",
        "background_color": tokens.color.panel_solid,
        "box_shadow": tokens.shadow[6],
        "outline_style": "none",
        "opacity": {
            "default": f"var({SHOWN})",
            "@starting-style": 0,
        },
        "transform": {
            "default": f"var({GONE})",
            "@starting-style": "translateY(5px) scale(0.97)",
        },
        "transition_property": "opacity, transform",
        "transition_duration": {
            "default": "0s",
            MOTION: f"calc(100ms + var({SHOWN}) * 100ms)",
        },
        "transition_timing_function": _EASING,
    }),
    "variants": {
        "size": {
            "1": unchecked(_size(tokens.space[3], tokens.radius[4])),
            "2": unchecked(_size(tokens.space[4], tokens.radius[4])),
            "3": unchecked(_size(tokens.space[5], tokens.radius[5])),
            "4": unchecked(_size(tokens.space[6], tokens.radius[5])),
        },
    },
    "defaults": {"size": "3"},
}

# A heading of size 5 that keeps its distance from what is under it, and
# whose first line starts at the top of its box.
DIALOG_TITLE: ComponentStyles = {
    **HEADING,
    "base": unchecked({**HEADING.get("base", {}), "margin_bottom": tokens.space[3]}),
    "defaults": {"size": "5", "trim": "start"},
}

DIALOG_DESCRIPTION: ComponentStyles = {**TEXT, "defaults": {"size": "3"}}
