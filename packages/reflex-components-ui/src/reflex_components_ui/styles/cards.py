"""The look of radio cards and of checkbox cards: a grid of cards to choose from."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.card import (
    _CLASSIC_HOVER_INNER,
    _CLASSIC_HOVER_OUTER,
    _CLASSIC_INNER,
    _CLASSIC_OUTER,
    _mix,
)

accent, gray, focus = tokens.accent, tokens.gray, tokens.focus

_POINTER = "@media (hover: hover)"
_TOUCH = "@media (pointer: coarse)"

# What says how a card is, on the label that is the card: the input inside.
CHECKED = ":has(:checked)"
FOCUSED = ":has(:focus-visible)"
DISABLED = ":has(:disabled)"


def _root(columns: str, sizes: dict[str, dict[str, str]]) -> ComponentStyles:
    """Make the table of a grid of cards.

    Args:
        columns: The columns of a grid that is given none.
        sizes: What each size hands its cards, by custom property.

    Returns:
        The table.
    """
    return {
        "base": {
            "box_sizing": "border-box",
            "display": "grid",
            "align_items": "stretch",
            "justify_content": "flex-start",
            "grid_template_columns": columns,
            "grid_template_rows": "none",
            "gap": tokens.space[4],
            "line_height": "var(--line-height)",
            "letter_spacing": "var(--letter-spacing)",
            "cursor": "default",
        },
        "variants": {
            "size": {
                size: unchecked({
                    "font_size": tokens.font_size[step],
                    "--line-height": tokens.line_height[step],
                    "--letter-spacing": tokens.letter_spacing[step],
                    **sizes[size],
                })
                for size, step in (("1", 2), ("2", 2), ("3", 3))
            },
        },
        "defaults": {"size": "2"},
    }


def _item(
    padding: tuple[str, str, str, str],
    radius: str,
    base: dict[str, Any],
    hover: str,
    after: dict[str, Any],
) -> ComponentStyles:
    """Make the table of a card: a label around the input that is its state.

    Args:
        padding: The padding of the card, from the top clockwise.
        radius: The radius of its corners.
        base: What the kind of card adds to the card itself.
        hover: The state of a card under the pointer that answers to it.
        after: What the kind of card adds to its border.

    Returns:
        The table.
    """
    border = "1px"
    layer: dict[str, Any] = {
        "content": "''",
        "position": "absolute",
        "pointer_events": "none",
        "transition_property": "inherit",
        "transition_duration": "inherit",
        "transition_timing_function": "inherit",
        "transition_delay": "inherit",
        "border_radius": f"calc({radius} - {border})",
        "inset": border,
    }
    top, right, bottom, left = padding
    return {
        "base": unchecked({
            "display": "flex",
            "align_items": "center",
            "gap": tokens.space[2],
            "position": "relative",
            "overflow": "hidden",
            "border_radius": radius,
            "font_family": tokens.default.font_family,
            "font_style": "normal",
            "text_align": "start",
            "padding_top": top,
            "padding_right": right,
            "padding_bottom": bottom,
            "padding_left": left,
            "box_sizing": "border-box",
            # A stacking context, so that the background stays over what is
            # behind the card.
            "contain": "paint",
            "--inset-border-width": border,
            "--inset-border-radius": radius,
            "--inset-padding-top": f"calc({top} - {border})",
            "--inset-padding-right": f"calc({right} - {border})",
            "--inset-padding-bottom": f"calc({bottom} - {border})",
            "--inset-padding-left": f"calc({left} - {border})",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": tokens.cursor.button,
                DISABLED: tokens.cursor.disabled,
            },
            **base,
            # Behind the children, and over them: the background and the
            # border.
            "_before": {
                **layer,
                "z_index": -1,
                "background_color": tokens.color.surface,
                **base.get("_before", {}),
            },
            "_after": {**layer, **after},
        }),
        "variants": {
            "_variant": {
                "surface": unchecked({
                    "_after": {
                        "box_shadow": {
                            "default": f"0 0 0 1px {_mix(5)}",
                            _POINTER: {hover: f"0 0 0 1px {_mix(7)}"},
                        },
                    },
                }),
                "classic": unchecked({
                    "transition_property": "box-shadow",
                    "transition_duration": {
                        "default": "120ms",
                        _POINTER: {hover: "40ms"},
                    },
                    "box_shadow": {
                        "default": _CLASSIC_OUTER,
                        _POINTER: {hover: _CLASSIC_HOVER_OUTER},
                    },
                    "_after": {
                        "box_shadow": {
                            "default": _CLASSIC_INNER,
                            _POINTER: {hover: _CLASSIC_HOVER_INNER},
                        },
                    },
                }),
            },
        },
        "defaults": {"_variant": "surface"},
    }


_DISABLED_FILL = f"linear-gradient({gray.a[2]}, {gray.a[2]})"

_RADIO_X = "var(--radio-cards-item-padding-x)"
_RADIO_Y = "var(--radio-cards-item-padding-y)"

RADIO_CARDS: ComponentStyles = _root(
    "repeat(auto-fit, minmax(160px, 1fr))",
    {
        "1": {
            "--radio-cards-item-padding-x": tokens.space[3],
            "--radio-cards-item-padding-y": f"calc({tokens.space[3]} / 1.2)",
            "--radio-cards-item-border-radius": tokens.radius[3],
        },
        "2": {
            "--radio-cards-item-padding-x": tokens.space[4],
            "--radio-cards-item-padding-y": f"calc({tokens.space[4]} * 0.875)",
            "--radio-cards-item-border-radius": tokens.radius[3],
        },
        "3": {
            "--radio-cards-item-padding-x": tokens.space[5],
            "--radio-cards-item-padding-y": f"calc({tokens.space[5]} / 1.2)",
            "--radio-cards-item-border-radius": tokens.radius[4],
        },
    },
)

# A radio card: the ring of the checked card, and the one of the focus over it.
RADIO_CARDS_ITEM: ComponentStyles = _item(
    (_RADIO_Y, _RADIO_X, _RADIO_Y, _RADIO_X),
    "var(--radio-cards-item-border-radius)",
    {
        "justify_content": "center",
        "color": {"default": "inherit", DISABLED: gray.a[9]},
        # As the button a card of Radix Themes is has none.
        "border_width": "0",
        "border_style": "none",
        "_before": {
            "background_image": {
                f"{CHECKED}{FOCUSED}": f"linear-gradient({focus.a[3]}, {focus.a[3]})",
                DISABLED: _DISABLED_FILL,
            },
        },
    },
    f":hover:not({CHECKED}, {DISABLED})",
    {
        "outline_offset": "-1px",
        "outline_style": {CHECKED: "solid", FOCUSED: "solid"},
        "outline_width": {CHECKED: "2px", FOCUSED: "2px"},
        "outline_color": {
            f"{CHECKED}:not({FOCUSED}, {DISABLED})": accent.indicator,
            f"{FOCUSED}:not({CHECKED})": focus[8],
            f"{CHECKED}{FOCUSED}": focus[10],
            DISABLED: gray[8],
        },
    },
)

RADIO_CARDS_ITEM_HIGH_CONTRAST: dict[str, Any] = {
    "_after": {
        "outline_color": {
            f"{CHECKED}:not({FOCUSED}, {DISABLED})": accent[12],
            f"{FOCUSED}:not({CHECKED})": focus[8],
            f"{CHECKED}{FOCUSED}": focus[10],
            DISABLED: gray[8],
        },
    },
}
RADIO_CARDS_ITEM["compound"] = [
    {
        "props": {"_high_contrast": "true"},
        "style": unchecked(RADIO_CARDS_ITEM_HIGH_CONTRAST),
    }
]

# The radio button of a card: there for the keyboard and for forms, not seen.
CARD_INPUT: ComponentStyles = {
    "base": {
        "appearance": "none",
        "position": "absolute",
        "inset": "0",
        "margin": "0",
        "opacity": 0,
        "pointer_events": "none",
    },
}

_CHECKBOX_LEFT = "var(--checkbox-cards-item-padding-left)"
_CHECKBOX_SIZE = "--checkbox-cards-item-checkbox-size"
_FOCUS_RING: dict[str, Any] = {
    "outline_width": {FOCUSED: "2px"},
    "outline_style": {FOCUSED: "solid"},
    "outline_color": {FOCUSED: focus[8]},
    "outline_offset": {FOCUSED: "-1px"},
}

CHECKBOX_CARDS: ComponentStyles = _root(
    "repeat(auto-fit, minmax(200px, 1fr))",
    {
        "1": {
            "--checkbox-cards-item-padding-top": f"calc({tokens.space[3]} / 1.2)",
            "--checkbox-cards-item-padding-bottom": f"calc({tokens.space[3]} / 1.2)",
            "--checkbox-cards-item-padding-left": tokens.space[3],
            "--checkbox-cards-item-border-radius": tokens.radius[3],
            _CHECKBOX_SIZE: f"calc({tokens.space[4]} * 0.875)",
        },
        "2": {
            "--checkbox-cards-item-padding-top": f"calc({tokens.space[4]} * 0.875)",
            "--checkbox-cards-item-padding-bottom": (
                f"calc({tokens.space[4]} * 0.875)"
            ),
            "--checkbox-cards-item-padding-left": tokens.space[4],
            "--checkbox-cards-item-border-radius": tokens.radius[3],
            _CHECKBOX_SIZE: tokens.space[4],
        },
        "3": {
            "--checkbox-cards-item-padding-top": f"calc({tokens.space[5]} / 1.2)",
            "--checkbox-cards-item-padding-bottom": f"calc({tokens.space[5]} / 1.2)",
            "--checkbox-cards-item-padding-left": tokens.space[5],
            "--checkbox-cards-item-border-radius": tokens.radius[4],
            _CHECKBOX_SIZE: f"calc({tokens.space[4]} * 1.25)",
        },
    },
)

# A checkbox card: room at its end for the checkbox, and the ring of the focus.
CHECKBOX_CARDS_ITEM: ComponentStyles = _item(
    (
        "var(--checkbox-cards-item-padding-top)",
        f"calc({_CHECKBOX_LEFT} * 2 + var({_CHECKBOX_SIZE}))",
        "var(--checkbox-cards-item-padding-bottom)",
        _CHECKBOX_LEFT,
    ),
    "var(--checkbox-cards-item-border-radius)",
    {
        "color": {DISABLED: gray.a[9]},
        **_FOCUS_RING,
        "_before": {
            "background_image": {
                # Instead of the highlight of a tap, which is turned off.
                _TOUCH: {
                    f":active:not({FOCUSED}, {DISABLED})": (
                        f"linear-gradient({gray.a[4]}, {gray.a[4]})"
                    ),
                },
                DISABLED: _DISABLED_FILL,
            },
        },
    },
    f":hover:not({DISABLED})",
    # The ring again on the border, which does not take its offset.
    {key: value for key, value in _FOCUS_RING.items() if key != "outline_offset"},
)
