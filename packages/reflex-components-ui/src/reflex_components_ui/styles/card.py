"""The look of a card."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.tokens import Step12

gray, black, focus = tokens.gray, tokens.black, tokens.focus

# What a size and a variant set, and the rest of the card reads. An inset
# inside the card reads how far its edges are from the `--inset-*` ones.
_PADDING = "--card-padding"
_RADIUS = "--card-border-radius"
_BORDER = "--card-border-width"
_BACKGROUND = "--card-background-color"

# A card rendered as a link, a button or a label answers to the pointer.
_LINK = ":is(:any-link, button, label)"
_POINTER = "@media (hover: hover)"
_TOUCH = "@media (pointer: coarse)"
_OPEN = "[data-state='open']"
_HOVER = f"{_LINK}:hover:not(:active)"
_PRESSED = f":active:not({_OPEN})"
_ACTIVE = f"{_LINK}{_PRESSED}"


def _states(hover: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    """Make the styles of a card that is a link, in each of its states.

    StyleX places a rule inside a media query after the others, so the card
    under the pointer is not the pressed one: no two of the states apply
    together, but for an open card under the pointer, which looks the same.

    Args:
        hover: The styles under the pointer, and of an open card.
        active: The styles of a pressed card.

    Returns:
        The styles, by state.
    """
    return {
        _POINTER: {_HOVER: hover},
        f"{_LINK}{_OPEN}": hover,
        _ACTIVE: active,
    }


def _mix(step: Step12) -> str:
    """Mix the color of a border, which stays visible over any background.

    Args:
        step: The step of the gray.

    Returns:
        The color.
    """
    return f"color-mix(in oklab, {gray.a[step]}, {gray[step]} 25%)"


Layer = tuple[str, str, str]

# The spread of a layer on the card, by its spread on the pseudo-element.
_SMALLER = {
    "1px": "0",
    "0.5px": "0",
    "0": "-1px",
    "-1px": "-2px",
    "-2px": "-3px",
    "-4px": "-5px",
    "-8px": "-9px",
}


def _classic(light: tuple[Layer, ...], dark: tuple[Layer, ...]) -> tuple[str, str]:
    """Make the two shadows of a classic card, in both appearances.

    The shadow is on a pseudo-element that is smaller than the card by the
    border, and the card itself repeats every layer with a spread one pixel
    smaller: what reaches outside the card is not clipped with its content.

    Args:
        light: The layers in the light appearance, the border first: each
            one as its offsets and blur, its spread and its color.
        dark: The same in the dark appearance.

    Returns:
        The shadow of the card and the shadow of the pseudo-element.
    """
    outer, inner = (
        by_appearance(
            *(
                ", ".join(
                    f"{offsets} {spreads.get(spread, spread)} {color}"
                    for offsets, spread, color in layers
                )
                for layers in (light, dark)
            )
        )
        for spreads in (_SMALLER, {})
    )
    return outer, inner


_NONE = tokens.color.transparent

_CLASSIC_OUTER, _CLASSIC_INNER = _classic(
    (
        ("0 0 0", "1px", _mix(3)),
        ("0 0 0", "1px", _NONE),
        ("0 0 0", "0.5px", black.a[1]),
        ("0 1px 1px", "0", gray.a[2]),
        ("0 2px 1px", "-1px", black.a[1]),
        ("0 1px 3px", "0", black.a[1]),
    ),
    (
        ("0 0 0", "1px", _mix(6)),
        ("0 0 0", "1px", _NONE),
        ("0 0 0", "0.5px", black.a[3]),
        ("0 1px 1px", "0", black.a[6]),
        ("0 2px 1px", "-1px", black.a[6]),
        ("0 1px 3px", "0", black.a[5]),
    ),
)
_CLASSIC_HOVER_OUTER, _CLASSIC_HOVER_INNER = _classic(
    (
        ("0 0 0", "1px", _mix(4)),
        ("0 1px 1px", "1px", black.a[1]),
        ("0 2px 1px", "-1px", gray.a[3]),
        ("0 2px 3px", "-2px", black.a[1]),
        ("0 3px 12px", "-4px", gray.a[3]),
        ("0 4px 16px", "-8px", black.a[1]),
    ),
    (
        ("0 0 0", "1px", _mix(6)),
        ("0 0 1px", "1px", gray.a[4]),
        ("0 0 1px", "-1px", gray.a[4]),
        ("0 0 3px", "-2px", gray.a[3]),
        ("0 0 12px", "-2px", gray.a[3]),
        ("0 0 16px", "-8px", gray.a[7]),
    ),
)
_CLASSIC_ACTIVE_OUTER, _CLASSIC_ACTIVE_INNER = _classic(
    (
        ("0 0 0", "1px", _mix(3)),
        ("0 0 0", "1px", _NONE),
        ("0 0 0", "0.5px", black.a[1]),
        ("0 1px 1px", "0", gray.a[4]),
        ("0 2px 1px", "-1px", black.a[1]),
        ("0 1px 3px", "0", black.a[1]),
    ),
    (
        ("0 0 0", "1px", _mix(6)),
        ("0 0 0", "1px", _NONE),
        ("0 0 0", "0.5px", black.a[3]),
        ("0 1px 1px", "0", black.a[6]),
        ("0 2px 1px", "-1px", black.a[6]),
        ("0 1px 3px", "0", black.a[5]),
    ),
)

# Behind the children, and over them: the background and the border.
_LAYER: dict[str, Any] = {
    "content": "''",
    "box_sizing": "border-box",
    "position": "absolute",
    "pointer_events": "none",
    "transition_property": "inherit",
    "transition_duration": "inherit",
    "transition_timing_function": "inherit",
    "transition_delay": "inherit",
    "border_radius": f"calc(var({_RADIUS}) - var({_BORDER}))",
    "inset": f"var({_BORDER})",
}

_PANEL: dict[str, Any] = {
    "background_color": f"var({_BACKGROUND})",
    "backdrop_filter": tokens.panel.backdrop_filter,
}

# The padding and the radius of each size.
_SIZES: dict[str, tuple[str, str]] = {
    "1": (tokens.space[3], tokens.radius[4]),
    "2": (tokens.space[4], tokens.radius[4]),
    "3": (tokens.space[5], tokens.radius[5]),
    "4": (tokens.space[6], tokens.radius[5]),
    "5": (tokens.space[8], tokens.radius[6]),
}

_INSET_PADDING = f"calc(var({_PADDING}) - var({_BORDER}))"
_GHOST_MARGIN = f"calc(0px - var({_PADDING}))"

# What everything a card does not set is, when it is rendered as a link or a
# button: Radix Themes unsets all of what the browser gives either.
_RESET: dict[str, Any] = {
    "margin": "0",
    "border_width": "0",
    # A reset of the page gives every element a border style, which is kept
    # where Radix Themes keeps it.
    "border_style": {":is(a, button)": "none"},
    "background_color": "transparent",
    "background_image": "none",
    "appearance": "none",
    "color": "inherit",
    "font_size": "inherit",
    # Radix Themes names a font weight that no token defines here, which
    # leaves the weight of what is around the card.
    "font_weight": "inherit",
    "line_height": "inherit",
    "letter_spacing": "inherit",
    "text_decoration_line": "none",
    "text_transform": "inherit",
    "text_indent": "initial",
    "text_shadow": "inherit",
    "word_spacing": "inherit",
    "cursor": {
        ":where(button):not(:disabled, [data-disabled])": tokens.cursor.button,
        ":any-link:not([data-disabled])": tokens.cursor.link,
        ":is(:disabled, [data-disabled])": tokens.cursor.disabled,
    },
    "outline_style": {"default": "none", ":focus-visible": "solid"},
    "WebkitTapHighlightColor": "transparent",
}

CARD: ComponentStyles = {
    "base": unchecked({
        **_RESET,
        "display": "block",
        "position": "relative",
        "overflow": "hidden",
        "border_radius": f"var({_RADIUS})",
        "font_family": tokens.default.font_family,
        "font_style": "normal",
        "text_align": "start",
        "padding": f"var({_PADDING})",
        "box_sizing": "border-box",
        # A stacking context, so that the background stays over what is
        # behind the card.
        "contain": "paint",
        "--inset-border-width": f"var({_BORDER})",
        "--inset-border-radius": f"var({_RADIUS})",
        "--inset-padding-top": _INSET_PADDING,
        "--inset-padding-right": _INSET_PADDING,
        "--inset-padding-bottom": _INSET_PADDING,
        "--inset-padding-left": _INSET_PADDING,
        "_before": {
            **_LAYER,
            "z_index": -1,
            f":focus-visible{_PRESSED}": {
                "background_image": f"linear-gradient({focus.a[2]}, {focus.a[2]})",
            },
            # Instead of the highlight of a tap, which is turned off.
            _TOUCH: {
                f"{_LINK}:active:not(:focus-visible, {_OPEN})": {
                    "background_image": f"linear-gradient({gray.a[4]}, {gray.a[4]})",
                },
            },
        },
        "_after": {
            **_LAYER,
            ":focus-visible": {
                "outline_width": "2px",
                "outline_style": "solid",
                "outline_color": focus[8],
            },
        },
        ":focus-visible": {
            "outline_width": "2px",
            "outline_color": focus[8],
            "outline_offset": "-1px",
        },
    }),
    "variants": {
        "size": {
            size: unchecked({
                _PADDING: padding,
                _RADIUS: radius,
            })
            for size, (padding, radius) in _SIZES.items()
        },
        "variant": {
            "surface": unchecked({
                _BORDER: "1px",
                _BACKGROUND: tokens.color.panel,
                "_before": _PANEL,
                "_after": {
                    "box_shadow": f"0 0 0 1px {_mix(5)}",
                    **_states(
                        {"box_shadow": f"0 0 0 1px {_mix(7)}"},
                        {"box_shadow": f"0 0 0 1px {_mix(6)}"},
                    ),
                },
            }),
            "classic": unchecked({
                _BORDER: "1px",
                _BACKGROUND: tokens.color.panel,
                "transition_property": "box-shadow",
                "transition_duration": "120ms",
                "box_shadow": _CLASSIC_OUTER,
                **_states(
                    {
                        "transition_duration": "40ms",
                        "box_shadow": _CLASSIC_HOVER_OUTER,
                    },
                    {
                        "transition_duration": "40ms",
                        "box_shadow": _CLASSIC_ACTIVE_OUTER,
                    },
                ),
                "_before": _PANEL,
                "_after": {
                    "box_shadow": _CLASSIC_INNER,
                    **_states(
                        {"box_shadow": _CLASSIC_HOVER_INNER},
                        {"box_shadow": _CLASSIC_ACTIVE_INNER},
                    ),
                },
            }),
            "ghost": unchecked({
                _BORDER: "0px",
                # It reaches as far out as its padding, so that what it
                # holds lines up with what is around it.
                "margin": _GHOST_MARGIN,
                "background_color": {
                    _POINTER: {
                        f"{_LINK}:hover:not(:active, :focus-visible)": gray.a[3],
                        f"{_LINK}:hover:focus-visible": focus.a[2],
                    },
                    f"{_LINK}{_OPEN}:not(:focus-visible)": gray.a[3],
                    f"{_LINK}:active:not({_OPEN}, :focus-visible)": gray.a[4],
                    f"{_LINK}:focus-visible:is(:active, {_OPEN})": focus.a[2],
                },
            }),
        },
    },
    "defaults": {"size": "1", "variant": "surface"},
}
