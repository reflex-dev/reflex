"""The look of an accordion: items that open, drawn as the Radix wrapper draws them."""

from __future__ import annotations

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, StyleProps, unchecked

accent, gray, black = tokens.accent, tokens.gray, tokens.black

# What the accordion hands its parts: how thick the line between two items
# is, and how its panels move.
DIVIDER = "--divider-px"
DURATION = "--animation-duration"
EASING = "--animation-easing"
# What an item hands its icon, which a rule of base.css reads: an open item
# turns it over.
_TURN = "--rx-accordion-turn"

_RADIUS = tokens.radius[4]
_LINE = gray.a[6]
_FIRST = ":first-of-type"
_LAST = ":last-child"

_OUTLINED = {
    "border_width": "1px",
    "border_style": "solid",
    "border_color": accent[6],
}

ACCORDION: ComponentStyles = {
    "base": {
        "border_radius": _RADIUS,
        "box_shadow": f"0 2px 10px {black.a[1]}",
    },
    "variants": {
        "variant": {
            "classic": {
                "background_color": accent[9],
                "box_shadow": f"0 2px 10px {black.a[4]}",
            },
            "soft": {"background_color": accent[3]},
            "outline": unchecked({**_OUTLINED, DIVIDER: "1px"}),
            "surface": unchecked({
                **_OUTLINED,
                "background_color": accent.surface,
                DIVIDER: "1px",
            }),
            "ghost": {"box_shadow": "none"},
        },
    },
    "defaults": {"variant": "classic"},
}

# The line above an item, where the accordion says how thick it is, and
# the corners of the first and the last item. A ghost has neither corner,
# and a line above its first item and below its last.
ACCORDION_ITEM: ComponentStyles = {
    "base": unchecked({
        "overflow": "hidden",
        "width": "100%",
        "margin_top": {"default": "1px", _FIRST: "0"},
        ":focus-within": {"position": "relative", "z_index": 1},
        _TURN: {"default": "none", "[open]": "rotate(180deg)"},
    }),
    "variants": {
        "_ghost": {
            "false": {
                "border_top_left_radius": {_FIRST: _RADIUS},
                "border_top_right_radius": {_FIRST: _RADIUS},
                "border_bottom_left_radius": {_LAST: _RADIUS},
                "border_bottom_right_radius": {_LAST: _RADIUS},
            },
        },
    },
    "compound": [
        # Without a line an item has no border, whatever a reset gives it.
        {
            "props": {"_ghost": "false", "_divided": "false"},
            "style": {"border_top_style": "none"},
        },
        {
            "props": {"_ghost": "true", "_divided": "false"},
            "style": {
                "border_top_style": "none",
                "border_bottom_style": {_LAST: "none"},
            },
        },
        {
            "props": {"_ghost": "false", "_divided": "true"},
            "style": unchecked({
                "border_top_width": {"default": f"var({DIVIDER})", _FIRST: "0"},
                "border_top_style": {"default": "solid", _FIRST: "none"},
                "border_top_color": {"default": _LINE, _FIRST: "currentcolor"},
            }),
        },
        {
            "props": {"_ghost": "true", "_divided": "true"},
            "style": unchecked({
                "border_top_width": f"var({DIVIDER})",
                "border_top_style": "solid",
                "border_top_color": _LINE,
                "border_bottom_width": {_LAST: f"var({DIVIDER})"},
                "border_bottom_style": {_LAST: "solid"},
                "border_bottom_color": {_LAST: _LINE},
            }),
        },
    ],
    "defaults": {"_ghost": "false", "_divided": "false"},
}

# The summary of the item: what opens it, with nothing of the look the
# browser gives one.
ACCORDION_HEADER: ComponentStyles = {
    "base": unchecked({
        "display": "flex",
        "margin": "0",
        "list_style_type": "none",
        "::-webkit-details-marker": {"display": "none"},
        # A disabled item does not open: the pointer goes through its header.
        "pointer_events": {"[aria-disabled='true']": "none"},
    }),
}

ACCORDION_TRIGGER: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "margin": "0",
        "border_style": "none",
        "cursor": "default",
        "font_size": "1.1em",
        "font_weight": "inherit",
        "line_height": 1,
        "text_align": "center",
        "color": accent[11],
        "display": "flex",
        "justify_content": "space-between",
        "align_items": "center",
        "flex_grow": 1,
        "flex_shrink": 1,
        "flex_basis": "0%",
        "padding_top": tokens.space[3],
        "padding_bottom": tokens.space[3],
        "padding_left": tokens.space[4],
        "padding_right": tokens.space[4],
        "width": "100%",
        "background_color": {":hover": accent[4]},
    },
    "variants": {
        "_classic": {
            "true": {
                "color": accent.contrast,
                "background_color": {":hover": accent[10]},
            },
        },
        "_divided": {
            "true": unchecked({"box_shadow": f"0 var({DIVIDER}) 0 {_LINE}"}),
        },
    },
}

_PAD: StyleProps = {
    "content": "' '",
    "display": "block",
    "height": tokens.space[3],
}

ACCORDION_CONTENT: ComponentStyles = {
    "base": {
        "overflow": "hidden",
        "color": accent[11],
        "padding_left": tokens.space[4],
        "padding_right": tokens.space[4],
        # Room above and below what the panel holds, which opens with it.
        "_before": _PAD,
        "_after": _PAD,
    },
    "variants": {"_classic": {"true": {"color": accent.contrast}}},
}
