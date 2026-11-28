"""The look of a progress bar: a track, and an indicator as wide as the value."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, keyframes, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.styles.typography import ACCENT_SCOPE

accent, gray, white = tokens.accent, tokens.gray, tokens.white

# What the element sets and the indicator reads, as with Radix Themes: how far
# the progress is, and how long a bar without a value takes to fill.
VALUE = "--progress-value"
MAX = "--progress-max"
DURATION = "--progress-duration"

# The color the `fill_color` prop gives the indicator, whatever its variant.
FILL = "--rx-progress-fill"

_HEIGHT = "--progress-height"

# A bar whose value is not known, or not one between zero and its maximum.
_INDETERMINATE = "[data-state='indeterminate']"

_GROW: dict[str, Any] = {
    "0%": {"transform": "scaleX(0.01)"},
    "20%": {"transform": "scaleX(0.1)"},
    "30%": {"transform": "scaleX(0.6)"},
    "40%": {"transform": "scaleX(0.9)"},
    "50%": {"transform": "scaleX(0.9)"},
    "100%": {"transform": "scaleX(1)"},
}

_SHINE = keyframes({
    "0%": {"transform": "translateX(-100%)"},
    "100%": {"transform": "translateX(0%)"},
})


def _fill(color: str) -> str:
    """Make the color of an indicator, which the ``fill_color`` prop replaces.

    Args:
        color: The color of the variant.

    Returns:
        The value of the background color.
    """
    return f"var({FILL}, {color})"


def _waiting(faded: dict[str, Any], back: dict[str, Any]) -> Any:
    """Make the animations of an indicator whose value is not known.

    It grows to the whole track, then fades to a color and pulses between
    that color and another for as long as it waits.

    Args:
        faded: What the indicator fades to once it has grown.
        back: What it pulses back to.

    Returns:
        The styles that play the three animations.
    """
    return {
        _INDETERMINATE: {
            "animation_name": keyframes(
                _GROW, {"100%": faded}, {"0%": faded, "100%": back}
            )
        }
    }


# The shine that crosses an indicator whose value is not known.
_SHINE_COLORS = by_appearance(
    f"{white.a[5]}, {white.a[9]}, {white.a[5]}",
    f"{white.a[3]}, {white.a[6]}, {white.a[3]}",
)

_INDICATOR: ComponentStyles = {
    "base": unchecked({
        "box_sizing": "border-box",
        "display": "block",
        "height": "100%",
        "width": "100%",
        "transform": f"scaleX(calc(var({VALUE}) / var({MAX})))",
        "transform_origin": "left center",
        "transition_property": "transform",
        "transition_duration": "120ms",
        _INDETERMINATE: {
            "animation_delay": (
                f"0s, calc(var({DURATION}) + 5s), calc(var({DURATION}) + 7.5s)"
            ),
            "animation_duration": f"var({DURATION}), 2.5s, 5s",
            "animation_iteration_count": "1, 1, infinite",
            "animation_fill_mode": "both, none, none",
            "animation_direction": "normal, normal, alternate",
        },
        "_after": {
            _INDETERMINATE: {
                "box_sizing": "border-box",
                "position": "absolute",
                "inset": "0",
                "content": "''",
                "width": "400%",
                "animation_name": _SHINE,
                "animation_delay": f"calc(var({DURATION}) + 5s)",
                "animation_duration": "5s",
                "animation_fill_mode": "backwards",
                "animation_iteration_count": "infinite",
                "background_image": (
                    "linear-gradient(to right, transparent 25%, "
                    f"{_SHINE_COLORS}, transparent 75%)"
                ),
            },
        },
    }),
    "variants": {
        "variant": {
            "surface": unchecked({
                "background_color": _fill(accent.track),
                **_waiting(
                    {"background_color": accent[7]}, {"background_color": accent.track}
                ),
            }),
            "classic": unchecked({
                "background_color": _fill(accent.track),
                **_waiting(
                    {"background_color": accent[7]}, {"background_color": accent.track}
                ),
            }),
            "soft": unchecked({
                "background_image": (f"linear-gradient({accent.a[5]}, {accent.a[5]})"),
                "background_color": _fill(accent[8]),
                "_after": {_INDETERMINATE: {"opacity": 0.75}},
                **_waiting(
                    {"background_color": accent[5]}, {"background_color": accent[7]}
                ),
            }),
        },
        "high_contrast": {
            "true": unchecked({
                "background_color": _fill(accent[12]),
                "_after": {_INDETERMINATE: {"opacity": 0.75}},
                **_waiting({"opacity": 0.8}, {"opacity": 1}),
            }),
        },
    },
    "defaults": {"variant": "surface"},
}

PROGRESS: ComponentStyles = {
    "base": unchecked({
        VALUE: "0",
        MAX: "100",
        DURATION: "5s",
        "box_sizing": "border-box",
        "pointer_events": "none",
        "position": "relative",
        "overflow": "hidden",
        "flex_grow": 1,
        "height": f"var({_HEIGHT})",
        "border_radius": (
            f"max(calc({tokens.radius.factor} * var({_HEIGHT}) / 3), "
            f"calc({tokens.radius.factor} * {tokens.radius.thumb}))"
        ),
        # Over the indicator, for the shadows of a variant.
        "_after": {
            "box_sizing": "border-box",
            "position": "absolute",
            "inset": "0",
            "content": "''",
            "border_radius": "inherit",
        },
    }),
    "variants": {
        "size": {
            "1": unchecked({_HEIGHT: tokens.space[1]}),
            "2": unchecked({_HEIGHT: f"calc({tokens.space[2]} * 0.75)"}),
            "3": unchecked({_HEIGHT: tokens.space[2]}),
        },
        "variant": {
            "surface": {
                "background_color": gray.a[3],
                "_after": {"box_shadow": f"inset 0 0 0 1px {gray.a[4]}"},
            },
            "classic": {
                "background_color": gray.a[3],
                "_after": {"box_shadow": tokens.shadow[1]},
            },
            "soft": {
                "background_color": gray.a[4],
                # Blended with white, for more contrast in the dark appearance.
                "background_image": f"linear-gradient({white.a[1]}, {white.a[1]})",
            },
        },
        "color_scheme": {"true": unchecked(ACCENT_SCOPE)},
    },
    "defaults": {"size": "2", "variant": "surface"},
    "parts": {"indicator": _INDICATOR},
}
