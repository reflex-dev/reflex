"""The look of a spinner: eight leaves that fade in turn."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, StyleProps, keyframes, unchecked

# How long a turn takes, and how see-through the spinner is: an app may set
# either, and a disabled button sets the second for the spinner inside it.
DURATION = "var(--spinner-animation-duration, 800ms)"
OPACITY = "--spinner-opacity"

_FADE = keyframes({"from": {"opacity": 1}, "to": {"opacity": 0.25}})

SPINNER_BASE: StyleProps = unchecked({
    "display": "block",
    "position": "relative",
    "opacity": f"var({OPACITY}, 0.65)",
})

SPINNER_SIZE: dict[str, StyleProps] = {
    "1": {"width": tokens.space[3], "height": tokens.space[3]},
    "2": {"width": tokens.space[4], "height": tokens.space[4]},
    "3": {
        "width": f"calc(1.25 * {tokens.space[4]})",
        "height": f"calc(1.25 * {tokens.space[4]})",
    },
}

# The leaves are the same element eight times: each one is turned, and
# starts its fade, by its place.
_PLACES = range(1, 9)

LEAF: Any = unchecked({
    "position": "absolute",
    "top": "0",
    "left": "calc(50% - 12.5% / 2)",
    "width": "12.5%",
    "height": "100%",
    "animation_name": _FADE,
    "animation_duration": DURATION,
    "animation_timing_function": "linear",
    "animation_iteration_count": "infinite",
    "transform": {
        f":nth-child({place})": f"rotate({(place - 1) * 45}deg)" for place in _PLACES
    },
    "animation_delay": {
        f":nth-child({place})": f"calc(-{9 - place} / 8 * {DURATION})"
        for place in _PLACES
    },
    "_before": {
        "content": "''",
        "display": "block",
        "width": "100%",
        "height": "30%",
        "border_radius": tokens.radius[1],
        "background_color": "currentColor",
    },
})

# Around the children a spinner stands in for: they keep their place and are
# not shown, and the spinner is centered over them.
HIDDEN_CONTENT: StyleProps = {"display": "contents", "visibility": "hidden"}
CENTERED: StyleProps = {
    "box_sizing": "border-box",
    "display": "flex",
    "align_items": "center",
    "justify_content": "center",
    "position": "absolute",
    "inset": "0",
}

SPINNER: ComponentStyles = {
    "base": SPINNER_BASE,
    "variants": {"size": SPINNER_SIZE},
    "defaults": {"size": "2"},
    "parts": {"leaf": {"base": LEAF}},
}

# The element around the children a spinner stands in for.
SPINNER_WRAPPER: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "flex",
        "position": "relative",
        "align_items": "center",
        "justify_content": "center",
    },
    "parts": {
        "content": {"base": HIDDEN_CONTENT},
        "overlay": {"base": CENTERED},
    },
}
