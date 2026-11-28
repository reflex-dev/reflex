"""The look of a switch: a native checkbox drawn as a track and a thumb."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.styles.control import DISABLED, FOCUS, FOCUS_RING, RESET

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

_HEIGHT = "--switch-height"
_WIDTH = "--switch-width"
_RADIUS = "--switch-border-radius"
_INSET = "--switch-thumb-inset"
_THUMB = "--switch-thumb-size"
_TRAVEL = "--switch-thumb-translate-x"

_CHECKED = ":checked"
_CHECKED_ENABLED = f":checked:not({DISABLED})"
_PRESSED = f":active:not({DISABLED})"
_UNCHECKED_PRESSED = f":active:not(:checked, {DISABLED})"
_CHECKED_PRESSED = f":checked:active:not({DISABLED})"

# A pressed switch that is on, and one that is high contrast too.
_PRESSED_FILTER = by_appearance("brightness(0.92) saturate(1.1)", "brightness(1.08)")
_PRESSED_FILTER_HIGH_CONTRAST = by_appearance(
    "contrast(0.82) saturate(1.2) brightness(1.16)", "brightness(1.08)"
)
# What darkens the track of a high contrast switch that is on.
_OVERLAY = f"light-dark({black.a[8]}, transparent)"

_THUMB_DISABLED = f"0 0 0 1px {gray.a[2]}, 0 1px 3px {black.a[1]}"
_THUMB_CHECKED = (
    f"0 1px 3px {black.a[2]}, 0 2px 4px -1px {black.a[1]}, 0 0 0 1px {black.a[1]}, "
    f"0 0 0 1px {accent.a[4]}, -1px 0 1px {black.a[2]}"
)
_THUMB_CHECKED_HIGH_CONTRAST = (
    f"0 1px 3px {black.a[2]}, 0 2px 4px -1px {black.a[1]}, 0 0 0 1px {black.a[2]}, "
    f"-1px 0 1px {black.a[2]}"
)


def _fade(start: str, end: str = "transparent") -> str:
    """Make one layer of a track: a color that gives way where the thumb is.

    Args:
        start: The color under the part that is on.
        end: The color under the part that is off.

    Returns:
        The gradient.
    """
    return f"linear-gradient(to right, {start} 40%, {end} 60%)"


def _states(rest: Any, checked: Any = None, disabled: Any = None, **more: Any) -> Any:
    """Make the value of a property by the state of the input.

    Args:
        rest: The value of a switch that is off.
        checked: The value of one that is on, when it differs.
        disabled: The value of a disabled one, when it differs.
        **more: Values under further conditions.

    Returns:
        The value, under a condition for each state that has one of its own.
    """
    value = {"default": rest}
    if checked is not None:
        value[_CHECKED_ENABLED] = checked
    value.update(more)
    if disabled is not None:
        value[DISABLED] = disabled
    return value


def _thumb(rest: str, checked: str) -> dict[str, Any]:
    """Make the thumb of a variant.

    Args:
        rest: The shadows of the thumb of a switch that is off.
        checked: The shadows of one that is on.

    Returns:
        The styles of the thumb.
    """
    return {
        "background_color": _states("white", disabled=gray[2]),
        "box_shadow": _states(rest, checked, _THUMB_DISABLED),
    }


def _look(variant: str, high_contrast: bool) -> dict[str, Any]:
    """Make the track and the thumb of one variant.

    Args:
        variant: The variant.
        high_contrast: Whether the switch is high contrast.

    Returns:
        The styles of the two pseudo-elements, for every state of the input.
    """
    pressed = {"filter": _states("none", **{_CHECKED_PRESSED: _PRESSED_FILTER})}
    if high_contrast:
        pressed = {
            "filter": _states(
                "none", **{_CHECKED_PRESSED: _PRESSED_FILTER_HIGH_CONTRAST}
            )
        }
    checked = _THUMB_CHECKED_HIGH_CONTRAST if high_contrast else _THUMB_CHECKED
    overlay = [_fade(_OVERLAY)] if high_contrast else []
    if variant == "surface":
        track: dict[str, Any] = {
            "background_color": _states(gray.a[3], **{_PRESSED: gray.a[4]}),
            "background_image": _states(
                ", ".join([*overlay, _fade(accent.track)]), disabled="none"
            ),
            "box_shadow": _states(
                f"inset 0 0 0 1px {gray.a[5]}",
                disabled=f"inset 0 0 0 1px {gray.a[3]}",
            ),
            **pressed,
        }
        thumb = _thumb(
            f"0 0 1px 1px {black.a[2]}, 0 1px 1px {black.a[1]}, "
            f"0 2px 4px -1px {black.a[1]}",
            checked,
        )
    elif variant == "classic":
        track = {
            "background_color": _states(
                gray.a[4], disabled=gray.a[5], **{_UNCHECKED_PRESSED: gray.a[5]}
            ),
            "background_image": _states(
                ", ".join([*overlay, _fade(accent.track)]), disabled="none"
            ),
            "box_shadow": (
                _states(
                    f"inset 0 0 0 1px {gray.a[3]}, inset 0 0 0 1px {black.a[2]}, "
                    f"inset 0 1.5px 2px 0 {black.a[2]}",
                    disabled=tokens.shadow[1],
                )
                if high_contrast
                else _states(
                    tokens.shadow[1],
                    f"inset 0 0 0 1px {gray.a[3]}, inset 0 0 0 1px {accent.a[4]}, "
                    f"inset 0 0 0 1px {black.a[1]}, "
                    f"inset 0 1.5px 2px 0 {black.a[2]}",
                    tokens.shadow[1],
                )
            ),
            "opacity": _states(1, disabled=0.5),
            **pressed,
        }
        thumb = _thumb(
            f"0 1px 3px {black.a[3]}, 0 2px 4px -1px {black.a[1]}, "
            f"0 0 0 1px {black.a[2]}",
            checked,
        )
    else:
        step = accent.a[6] if high_contrast else accent.a[4]
        track = {
            "background_color": _states(
                gray.a[3], "transparent", gray.a[4], **{_PRESSED: gray.a[4]}
            ),
            "background_image": _states(
                ", ".join([
                    *overlay,
                    _fade(step),
                    _fade(step),
                    # Blended with white for more contrast in the dark.
                    _fade(step, white.a[1]),
                    _fade(accent.a[3] if high_contrast else gray.a[2], gray.a[3]),
                ]),
                disabled="none",
            ),
        }
        if high_contrast:
            track.update(pressed)
        thumb = {
            "background_color": _states("white", disabled=gray[2]),
            "box_shadow": _states(
                f"0 0 0 1px {black.a[1]}, 0 1px 3px {black.a[1]}, "
                f"0 1px 3px {black.a[1]}, 0 2px 4px -1px {black.a[1]}",
                f"0 0 0 1px {black.a[1]}, 0 1px 3px {black.a[2]}, "
                f"0 1px 3px {accent.a[3]}, 0 2px 4px -1px {accent.a[3]}",
                _THUMB_DISABLED,
            ),
            "filter": _states("saturate(0.45)", disabled="none"),
        }
    return {"_before": track, "_after": thumb}


_VARIANTS = ("classic", "surface", "soft")

SWITCH: ComponentStyles = {
    "base": unchecked({
        **RESET,
        "position": "relative",
        "display": "inline-flex",
        "align_items": "center",
        "vertical_align": "top",
        "flex_shrink": 0,
        # In a line of text it is as high as the line.
        "height": f"var(--line-height, var({_HEIGHT}))",
        _WIDTH: f"calc(var({_HEIGHT}) * 1.75)",
        _INSET: "1px",
        _THUMB: f"calc(var({_HEIGHT}) - var({_INSET}) * 2)",
        _TRAVEL: f"calc(var({_WIDTH}) - var({_HEIGHT}))",
        "cursor": {DISABLED: tokens.cursor.disabled},
        "mix_blend_mode": {DISABLED: by_appearance("multiply", "screen")},
        # The track: its gradient is the width of the part that is on, the
        # height of the thumb and the width of the part that is off, and
        # moves with the thumb.
        "_before": {
            "content": "''",
            "display": "block",
            "width": f"var({_WIDTH})",
            "height": f"var({_HEIGHT})",
            "border_radius": f"var({_RADIUS})",
            "transition_property": (
                "background-position, background-color, box-shadow, filter"
            ),
            "transition_timing_function": "linear, ease-in-out, ease-in-out, ease-in-out",
            "transition_duration": {
                "default": "120ms, 140ms, 140ms, 140ms",
                _CHECKED: "160ms, 140ms, 140ms, 140ms",
                ":active": "30ms",
            },
            "background_repeat": "no-repeat",
            "background_size": f"calc(var({_WIDTH}) * 2 + var({_HEIGHT})) 100%",
            "background_position_x": {"default": "100%", _CHECKED: "0%"},
            "background_position_y": "50%",
            "cursor": {
                "default": tokens.cursor.switch,
                DISABLED: tokens.cursor.disabled,
            },
            FOCUS: FOCUS_RING,
        },
        "_after": {
            "content": "''",
            "position": "absolute",
            "left": f"var({_INSET})",
            "width": f"var({_THUMB})",
            "height": f"var({_THUMB})",
            "border_radius": f"calc(var({_RADIUS}) - var({_INSET}))",
            "transition_property": {
                "default": "transform, box-shadow",
                DISABLED: "none",
            },
            "transition_duration": "140ms",
            "transition_timing_function": (
                "cubic-bezier(0.45, 0.05, 0.55, 0.95), ease-in-out"
            ),
            "transform": {_CHECKED: f"translateX(var({_TRAVEL}))"},
            "pointer_events": "none",
        },
    }),
    "variants": {
        "size": {
            "1": unchecked({
                _HEIGHT: tokens.space[4],
                _RADIUS: f"max({tokens.radius[1]}, {tokens.radius.thumb})",
            }),
            "2": unchecked({
                _HEIGHT: f"calc({tokens.space[5]} * 5 / 6)",
                _RADIUS: f"max({tokens.radius[2]}, {tokens.radius.thumb})",
            }),
            "3": unchecked({
                _HEIGHT: tokens.space[5],
                _RADIUS: f"max({tokens.radius[2]}, {tokens.radius.thumb})",
            }),
        },
        "variant": {variant: unchecked(_look(variant, False)) for variant in _VARIANTS},
    },
    "defaults": {"size": "2", "variant": "surface"},
    "compound": [
        {
            "props": {"variant": variant, "high_contrast": "true"},
            "style": unchecked(_look(variant, True)),
        }
        for variant in _VARIANTS
    ],
}
