"""The look of a tooltip: a small dark popup beside what it describes."""

from __future__ import annotations

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.popup import OPEN, POPUP, placements
from reflex_components_ui.styles.typography import SIZE

_MOTION = "@media (prefers-reduced-motion: no-preference)"

# How far a tooltip is from what it describes unless it says, and the room
# Radix Themes leaves between the two for its arrow, in pixels: a tooltip
# here has no arrow, and is where the one of Radix is.
OFFSET_DEFAULT = 4
ARROW = 5

TOOLTIP: ComponentStyles = {
    "base": unchecked({
        **POPUP,
        "overflow": "visible",
        "box_sizing": "border-box",
        "padding": f"{tokens.space[1]} {tokens.space[2]}",
        "background_color": tokens.gray[12],
        "border_radius": tokens.radius[2],
        "max_width": "min(360px, calc(100vw - 20px))",
        # It comes in, and is gone at once.
        "transition_duration": {
            "default": "0s",
            _MOTION: {"default": "0s", OPEN: "140ms"},
        },
    }),
    "variants": {
        # A tooltip the pointer cannot rest on lets it through.
        "disable_hoverable_content": {"true": {"pointer_events": "none"}},
    },
    "defaults": {"side": "top", "align": "center"},
    "compound": placements(f"{OFFSET_DEFAULT + ARROW}px"),
    "parts": {
        "text": {
            "base": unchecked({
                "margin": "0",
                "line_height": f"var(--line-height, {tokens.default.line_height})",
                "letter_spacing": "var(--letter-spacing, inherit)",
                **SIZE["1"],
                "color": tokens.gray[1],
                "user_select": "none",
                "cursor": "default",
            }),
        },
    },
}
