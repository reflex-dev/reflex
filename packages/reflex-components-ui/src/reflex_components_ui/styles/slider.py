"""The look of a slider: a track, the part of it that is filled, and its thumbs."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.appearance import by_appearance

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

_TRACK = "--slider-track-size"
_THUMB = "--slider-thumb-size"
# Where the filled part of the track starts and ends, which the slider sets
# from its values and its script moves with its thumbs.
START = "--rx-slider-start"
END = "--rx-slider-end"

_DISABLED = ":has(:disabled)"
# The side of the thumb that is drawn: larger than the one that says how far
# a thumb travels, so that it reaches a little past the filled part.
_DRAWN = f"calc(var({_THUMB}) + var({_TRACK}) * 0.5)"
_PAST = f"calc(var({_TRACK}) * -0.25)"

_THUMB_SHADOWS = {
    "surface": f"0 0 0 1px {black.a[4]}",
    "classic": (
        f"0 0 0 1px {black.a[3]}, 0 1px 3px {black.a[1]}, 0 2px 4px -1px {black.a[1]}"
    ),
    "soft": (
        f"0 0 0 1px {black.a[3]}, 0 0 0 1px {gray.a[2]}, 0 0 0 1px {accent.a[2]}, "
        f"0 1px 2px {gray.a[4]}, 0 1px 3px -0.5px {gray.a[3]}"
    ),
}
_THUMB_DISABLED = {"surface": gray[6], "classic": gray[6], "soft": gray[5]}

# What darkens the filled part of a high contrast slider, where it is light.
_HIGH_CONTRAST = by_appearance(f"linear-gradient({black.a[8]}, {black.a[8]})", "none")


def _thumb(variant: str) -> dict[str, Any]:
    """Make the thumb the browser draws for a range input, in one variant.

    Args:
        variant: The variant.

    Returns:
        The styles of the thumb, for every state of the input.
    """
    shadow = _THUMB_SHADOWS[variant]
    return {
        "appearance": "none",
        "box_sizing": "border-box",
        "width": _DRAWN,
        "height": _DRAWN,
        "border_width": "0",
        "border_style": "none",
        "pointer_events": "auto",
        "background_color": {"default": "white", ":disabled": gray[1]},
        "border_radius": f"max({tokens.radius[1]}, {tokens.radius.thumb})",
        "box_shadow": {
            "default": shadow,
            ":focus-visible": (
                f"{shadow}, 0 0 0 3px {accent[3]}, 0 0 0 5px {tokens.focus[8]}"
            ),
            ":disabled": f"0 0 0 1px {_THUMB_DISABLED[variant]}",
        },
        "cursor": {
            "default": tokens.cursor.slider_thumb,
            ":active": tokens.cursor.slider_thumb_active,
            ":disabled": tokens.cursor.disabled,
        },
    }


def _input(variant: str) -> dict[str, Any]:
    """Make the range input of a thumb, in one variant.

    Args:
        variant: The variant.

    Returns:
        The styles of the input: only its thumb is drawn, in each engine.
    """
    clear = {"background_color": "transparent", "height": "100%"}
    return {
        "::-webkit-slider-runnable-track": clear,
        "::-webkit-slider-thumb": _thumb(variant),
        "::-moz-range-track": clear,
        "::-moz-range-thumb": _thumb(variant),
    }


def _range(fill: dict[str, Any], disabled: bool) -> dict[str, Any]:
    """Make the filled part of a track.

    Args:
        fill: Its styles in a slider that can be moved.
        disabled: Whether the slider is disabled, which empties it.

    Returns:
        The styles.
    """
    if not disabled:
        return fill
    return {
        "background_color": "transparent",
        "background_image": "none",
        "box_shadow": "none",
    }


_CLASSIC_RANGE = (
    f"inset 0 0 0 1px {gray.a[3]}, inset 0 0 0 1px {accent.a[4]}, "
    f"inset 0 0 0 1px {black.a[1]}, inset 0 1.5px 2px 0 {black.a[2]}"
)
_CLASSIC_RANGE_HIGH_CONTRAST = (
    f"inset 0 0 0 1px {gray.a[3]}, inset 0 0 0 1px {black.a[2]}, "
    f"inset 0 1.5px 2px 0 {black.a[2]}"
)


def _fill(variant: str, high_contrast: bool) -> dict[str, Any]:
    """Make the filled part of the track of one variant.

    Args:
        variant: The variant.
        high_contrast: Whether the slider is high contrast.

    Returns:
        The styles of the filled part of a slider that can be moved.
    """
    overlay = _HIGH_CONTRAST if high_contrast else "none"
    if variant == "soft":
        tint = f"linear-gradient({accent.a[5]}, {accent.a[5]})"
        return {
            "background_color": accent[6],
            "background_image": f"{tint}, {overlay}",
        }
    shadow = f"inset 0 0 0 1px {gray.a[5]}"
    if variant == "classic":
        shadow = _CLASSIC_RANGE_HIGH_CONTRAST if high_contrast else _CLASSIC_RANGE
    return {
        "background_color": accent.track,
        "background_image": overlay,
        "box_shadow": shadow,
    }


_VARIANTS = ("classic", "surface", "soft")

_TRACKS: dict[str, dict[str, Any]] = {
    "surface": {
        "background_color": gray.a[3],
        "box_shadow": f"inset 0 0 0 1px {gray.a[5]}",
    },
    "classic": {
        "background_color": gray.a[3],
        "_before": {
            "content": "''",
            "inset": "0",
            "position": "absolute",
            "border_radius": "inherit",
            "box_shadow": tokens.shadow[1],
        },
    },
    "soft": {
        "background_color": gray.a[4],
        # Blended with white for more contrast in the dark.
        "background_image": f"linear-gradient({white.a[1]}, {white.a[1]})",
    },
}
_TRACKS_DISABLED: dict[str, dict[str, Any]] = {
    "surface": {"box_shadow": f"inset 0 0 0 1px {gray.a[4]}"},
    "classic": {"_before": {"opacity": 0.5}},
    "soft": {"background_image": "none"},
}

SLIDER: ComponentStyles = {
    "base": unchecked({
        "box_sizing": "border-box",
        _THUMB: f"calc(var({_TRACK}) + {tokens.space[1]})",
        "position": "relative",
        "display": "flex",
        "align_items": "center",
        "flex_grow": 1,
        "border_radius": (
            f"max(calc({tokens.radius.factor} * var({_TRACK}) / 3), "
            f"calc({tokens.radius.factor} * {tokens.radius.thumb}))"
        ),
        "user_select": "none",
        "touch_action": "none",
        "cursor": {_DISABLED: tokens.cursor.disabled},
        "mix_blend_mode": {_DISABLED: by_appearance("multiply", "screen")},
    }),
    "variants": {
        "size": {
            "1": unchecked({_TRACK: f"calc({tokens.space[2]} * 0.75)"}),
            "2": unchecked({_TRACK: tokens.space[2]}),
            "3": unchecked({_TRACK: f"calc({tokens.space[2]} * 1.25)"}),
        },
        "orientation": {
            "horizontal": {"width": "stretch", "height": f"var({_TRACK})"},
            "vertical": {
                "height": "stretch",
                "flex_direction": "column",
                "width": f"var({_TRACK})",
            },
        },
    },
    "defaults": {"size": "2", "variant": "surface", "orientation": "horizontal"},
    "parts": {
        "track": {
            "base": {
                "overflow": "hidden",
                "position": "relative",
                "flex_grow": 1,
                "border_radius": "inherit",
            },
            "variants": {
                "orientation": {
                    "horizontal": {"height": f"var({_TRACK})"},
                    "vertical": {"width": f"var({_TRACK})"},
                },
                "variant": {
                    variant: unchecked(_TRACKS[variant]) for variant in _VARIANTS
                },
            },
            "defaults": {"variant": "surface", "orientation": "horizontal"},
            "compound": [
                {
                    "props": {"variant": variant, "disabled": "true"},
                    "style": unchecked(_TRACKS_DISABLED[variant]),
                }
                for variant in _VARIANTS
            ],
        },
        # The filled part: between the first thumb and the last, or from the
        # start of the track to the only one.
        "range": {
            "base": {"position": "absolute", "border_radius": "inherit"},
            "variants": {
                "orientation": {
                    "horizontal": unchecked({
                        "height": "100%",
                        "left": f"var({START})",
                        "right": f"calc(100% - var({END}))",
                    }),
                    "vertical": unchecked({
                        "width": "100%",
                        "bottom": f"var({START})",
                        "top": f"calc(100% - var({END}))",
                    }),
                },
                "variant": {
                    variant: unchecked(_fill(variant, False)) for variant in _VARIANTS
                },
            },
            "defaults": {"variant": "surface", "orientation": "horizontal"},
            "compound": [
                *(
                    {
                        "props": {"variant": variant, "high_contrast": "true"},
                        "style": unchecked(_fill(variant, True)),
                    }
                    for variant in _VARIANTS
                ),
                {
                    "props": {"disabled": "true"},
                    "style": unchecked(_range({}, True)),
                },
            ],
        },
        # A thumb: a range input of which only the thumb is drawn. It is
        # wider than the track by what the drawn thumb reaches past it, so
        # that the thumb travels as far as the one of Radix Themes.
        "thumb": {
            "base": unchecked({
                "appearance": "none",
                "position": "absolute",
                "margin": "0",
                "padding": "0",
                "border_width": "0",
                "border_style": "none",
                "background_color": "transparent",
                "outline_style": "none",
                "cursor": "inherit",
            }),
            "variants": {
                "orientation": {
                    "horizontal": {
                        "width": f"calc(100% + var({_TRACK}) * 0.5)",
                        "height": _DRAWN,
                        "left": _PAST,
                        "top": f"calc(50% - {_DRAWN} / 2)",
                    },
                    "vertical": {
                        "height": f"calc(100% + var({_TRACK}) * 0.5)",
                        "width": _DRAWN,
                        "top": _PAST,
                        "left": f"calc(50% - {_DRAWN} / 2)",
                        # From the bottom up.
                        "writing_mode": "vertical-lr",
                        "direction": "rtl",
                    },
                },
                "variant": {
                    variant: unchecked(_input(variant)) for variant in _VARIANTS
                },
                # With several thumbs a pointer goes through an input to the
                # ones below it, but for its thumb.
                "_several": {"true": {"pointer_events": "none"}},
            },
            "defaults": {"variant": "surface", "orientation": "horizontal"},
        },
    },
}
