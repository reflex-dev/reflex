"""The look of a popup: a native popover, placed beside what opens it."""

from __future__ import annotations

from typing import Any

# A popup that is open, and the element before it that opens it. A style
# of that element selects on the second: no script says that it is open.
OPEN = ":popover-open"
OPENS = ":is([data-state='open'], :has(+ :popover-open))"

# How far a popup stays from the edge of the viewport, as in Radix.
_EDGE = "10px"

# Where a popup goes for each side of its anchor and each alignment along
# that side: the part of the page the browser lays it out in.
_AREAS = {
    ("bottom", "start"): "bottom span-right",
    ("bottom", "center"): "bottom span-all",
    ("bottom", "end"): "bottom span-left",
    ("top", "start"): "top span-right",
    ("top", "center"): "top span-all",
    ("top", "end"): "top span-left",
    ("left", "start"): "left span-bottom",
    ("left", "center"): "left span-all",
    ("left", "end"): "left span-top",
    ("right", "start"): "right span-bottom",
    ("right", "center"): "right span-all",
    ("right", "end"): "right span-top",
}

# What a table sets on a popup: how far it is from its anchor, how far
# along it, and where it comes from when it opens.
OFFSET = "--rx-popup-offset"
SHIFT = "--rx-popup-shift"
_FROM = "--rx-popup-from"

_MOTION = "@media (prefers-reduced-motion: no-preference)"

# Where a popup on each side comes from, as in Radix Themes.
_ENTRY = {
    "bottom": "translateY(-4px) scale(0.97)",
    "top": "translateY(4px) scale(0.97)",
    "left": "translateX(4px) scale(0.97)",
    "right": "translateX(-4px) scale(0.97)",
}
_OPPOSITE = {"bottom": "top", "top": "bottom", "left": "right", "right": "left"}

# What a popover is before a table draws it: nothing of the box the browser
# gives one, and placed by its anchor instead of in the middle of the page.
POPUP: dict[str, Any] = {
    "position": "fixed",
    "inset": "auto",
    "margin": "0",
    "padding": "0",
    "border_width": "0",
    "border_style": "none",
    "box_sizing": "border-box",
    "width": "max-content",
    "height": "auto",
    "max_width": f"calc(100vw - {_EDGE} * 2)",
    # It turns over where it would leave the viewport.
    "position_try_fallbacks": "flip-block, flip-inline",
    # It comes in when it opens, and goes out before it leaves the top
    # layer, for whoever has not asked for less motion.
    "opacity": {"default": 0, OPEN: {"default": 1, "@starting-style": 0}},
    "transform": {
        "default": f"var({_FROM})",
        OPEN: {"default": "none", "@starting-style": f"var({_FROM})"},
    },
    "transition_property": "opacity, transform, display, overlay",
    "transition_duration": {
        "default": "0s",
        _MOTION: {"default": "100ms", OPEN: "160ms"},
    },
    "transition_timing_function": "cubic-bezier(0.16, 1, 0.3, 1)",
}


def placement(side: str, align: str, default_offset: str = "0px") -> dict[str, Any]:
    """Make the styles that place a popup beside its anchor.

    Args:
        side: The side of the anchor the popup is on.
        align: Where along that side: at its start, its center or its end.
        default_offset: How far from the anchor, for a popup that does not say.

    Returns:
        The styles: the popup is no taller, or no wider, than the room the
        viewport leaves on that side.
    """
    vertical = side in ("top", "bottom")
    before, after = ("top", "bottom") if vertical else ("left", "right")
    start, end = ("left", "right") if vertical else ("top", "bottom")
    offset = f"var({OFFSET}, {default_offset})"
    style: dict[str, Any] = {
        "position_area": _AREAS[side, align],
        f"margin_{before}": offset,
        f"margin_{after}": offset,
        ("max_height" if vertical else "max_width"): (
            f"calc(100% - {offset} - {_EDGE})"
        ),
        _FROM: _ENTRY[side],
        "transform_origin": (
            f"{_OPPOSITE[side]} "
            f"{'center' if align == 'center' else start if align == 'start' else end}"
        ),
    }
    if align == "center":
        style["justify_self" if vertical else "align_self"] = "anchor-center"
    else:
        style[f"margin_{start if align == 'start' else end}"] = f"var({SHIFT}, 0px)"
    return style


def placements(default_offset: str = "0px") -> list[dict[str, Any]]:
    """Make the compound variants that place a popup by its side and alignment.

    Args:
        default_offset: How far from the anchor, for a popup that does not say.

    Returns:
        One compound variant for each side and each alignment along it.
    """
    return [
        {
            "props": {"side": side, "align": align},
            "style": placement(side, align, default_offset),
        }
        for side, align in _AREAS
    ]
