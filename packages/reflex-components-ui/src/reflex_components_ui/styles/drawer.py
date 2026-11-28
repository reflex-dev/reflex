"""The look of a drawer: a native ``dialog`` whose panel slides in from an edge."""

from __future__ import annotations

from typing import Any

from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.dialog import OPEN, SURFACE

_DURATION = "0.5s"
_EASING = "cubic-bezier(0.32, 0.72, 0, 1)"

# What a drawer hands its panel: where it comes from and goes back to, and
# where it is now.
_AWAY = "--rx-drawer-away"
_PLACE = "--rx-drawer-place"

# The overlay is the element before or after the drawer it belongs to.
_BESIDE_OPEN = ":is(:has(~ dialog[open]), dialog[open] ~ *)"

# How far a panel is moved out of the page on each side, and where what
# continues it past its edge is.
_AWAYS = {
    "bottom": "translate3d(0, 100%, 0)",
    "top": "translate3d(0, -100%, 0)",
    "left": "translate3d(-100%, 0, 0)",
    "right": "translate3d(100%, 0, 0)",
}
_BEYOND: dict[str, dict[str, Any]] = {
    "bottom": {"top": "100%", "left": "0", "right": "0", "height": "200%"},
    "top": {"bottom": "100%", "left": "0", "right": "0", "height": "200%"},
    "left": {"right": "100%", "top": "0", "bottom": "0", "width": "200%"},
    "right": {"left": "100%", "top": "0", "bottom": "0", "width": "200%"},
}

# The element around the parts of a drawer, which is nothing to the layout.
# It reads the direction, which is the edge the drawer comes from and not
# the direction of a flex container.
DRAWER_ROOT: ComponentStyles = {
    "base": {"display": "contents"},
    "variants": {"direction": {}},
}

# The dialog covers the page and is nothing to see: its panel is what an
# app styles. A drawer that is not modal lets the pointer through to the
# page beside its panel.
DRAWER: ComponentStyles = {
    "base": unchecked({
        **SURFACE,
        "position": "fixed",
        "inset": "0",
        "width": "100%",
        "height": "100%",
        "z_index": 50,
        "display": {"default": "none", OPEN: "block"},
        # A moment longer than its panel, which says when it has slid out.
        "transition_duration": "0.55s",
        _PLACE: {"default": f"var({_AWAY})", OPEN: "none"},
    }),
    "variants": {
        "_direction": {side: unchecked({_AWAY: away}) for side, away in _AWAYS.items()},
        "_modal": {"false": {"pointer_events": "none"}},
    },
    "defaults": {"_direction": "bottom"},
}

DRAWER_CONTENT: ComponentStyles = {
    "base": unchecked({
        "left": "0",
        "right": "0",
        "bottom": "0",
        "top": "0",
        "position": "fixed",
        "z_index": 50,
        "display": "flex",
        "pointer_events": "auto",
        "touch_action": "none",
        "will_change": "transform",
        "@media (hover: hover) and (pointer: fine)": {"user_select": "none"},
        "transform": {
            "default": f"var({_PLACE})",
            "@starting-style": f"var({_AWAY})",
        },
        "transition_property": "transform",
        "transition_duration": _DURATION,
        "transition_timing_function": _EASING,
        # The panel goes on past the edge it came from, in its own color.
        "_after": {
            "content": "''",
            "position": "absolute",
            "background_color": "inherit",
            "background_image": "inherit",
        },
    }),
    "variants": {
        "_direction": {side: {"_after": beyond} for side, beyond in _BEYOND.items()},
    },
    "defaults": {"_direction": "bottom"},
}

DRAWER_OVERLAY: ComponentStyles = {
    "base": unchecked({
        "position": "fixed",
        "left": "0",
        "right": "0",
        "bottom": "0",
        "top": "0",
        "z_index": 50,
        "background_color": "rgba(0, 0, 0, 0.5)",
        "transition_property": "opacity, display",
        "transition_duration": _DURATION,
        "transition_timing_function": _EASING,
    }),
    "variants": {
        "_modal": {
            "true": {
                "display": {"default": "none", _BESIDE_OPEN: "block"},
                "opacity": {
                    "default": 0,
                    _BESIDE_OPEN: {"default": 1, "@starting-style": 0},
                },
            },
            # A drawer that is not modal has no overlay.
            "false": {"display": "none"},
        },
    },
    "defaults": {"_modal": "true"},
}

DRAWER_TITLE: ComponentStyles = {
    "base": {
        "margin": "0",
        "font_size": "1.125rem",
        "font_weight": "600",
        "line_height": "1",
        "letter_spacing": "-0.05em",
    },
}

DRAWER_DESCRIPTION: ComponentStyles = {
    "base": {"margin": "0", "font_size": "0.875rem"},
}

DRAWER_HANDLE: ComponentStyles = {
    "base": {
        "display": "block",
        "position": "relative",
        "opacity": {"default": 0.7, ":hover": 1, ":active": 1},
        "background_color": "#e2e2e4",
        "margin_left": "auto",
        "margin_right": "auto",
        "height": "5px",
        "width": "32px",
        "border_radius": "1rem",
        "touch_action": "pan-y",
    },
    "parts": {
        "hitarea": {
            "base": {
                "position": "absolute",
                "left": "50%",
                "top": "50%",
                "transform": "translate(-50%, -50%)",
                "width": "max(100%, 2.75rem)",
                "height": "max(100%, 2.75rem)",
                "touch_action": "inherit",
            },
        },
    },
}
