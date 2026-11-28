"""The look of a select: a trigger, and the list it opens."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.styles.button import _CLASSIC_DISABLED_SHADOW
from reflex_components_ui.styles.popup import OPENS, POPUP, placements
from reflex_components_ui.tokens import Step9

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

_HEIGHT = "--select-trigger-height"
_GHOST_X = "--select-trigger-ghost-padding-x"
_GHOST_Y = "--select-trigger-ghost-padding-y"
_PADDING = "--select-content-padding"
_ITEM_HEIGHT = "--select-item-height"
_INDICATOR = "--select-item-indicator-width"
_SEPARATOR = "--select-separator-margin-right"

# What the trigger hands the elements inside it: the color of a placeholder
# and of the icon of a disabled select.
_SHOWN_COLOR = "--rx-select-shown-color"
_SHOWN_OPACITY = "--rx-select-shown-opacity"
_ICON_COLOR = "--rx-select-icon-color"
# What the list hands its items: how large their text is, and how the one
# that has the focus is marked.
_FONT_SIZE = "--rx-select-font-size"
_LINE_HEIGHT = "--rx-select-line-height"
_LETTER_SPACING = "--rx-select-letter-spacing"
_LABEL_SIZE = "--rx-select-label-font-size"
_LABEL_SPACING = "--rx-select-label-letter-spacing"
_ITEM_RADIUS = "--rx-select-item-radius"
_CHECK = "--rx-select-check-size"
_MARK = "--rx-select-highlight"
_MARK_COLOR = "--rx-select-highlight-color"

_POINTER = "@media (hover: hover)"
_HOVER = ":hover:not(:disabled)"
_DISABLED = ":disabled"
_FOCUS = ":focus-visible"
_EMPTY = "[data-placeholder]"
_OPEN = f"{OPENS}:not(:disabled)"

_CLASSIC_SHADOW = by_appearance(
    f"inset 0 0 0 1px {gray.a[5]}, inset 0 2px 1px {white.a[11]}, "
    f"inset 0 -2px 1px {gray.a[4]}",
    f"inset 0 0 0 1px {white.a[4]}, inset 0 1px 1px {white.a[4]}, "
    f"inset 0 -1px 1px {black.a[9]}",
)
_CLASSIC_RAISED = f"inset 0 0 0 1px {gray.a[3]}, {_CLASSIC_SHADOW}"
_CLASSIC_FILL = (
    f"linear-gradient({black.a[1]} -20%, transparent, {white.a[1]} 130%), "
    f"linear-gradient({tokens.color.surface}, transparent)"
)
_CLASSIC_FILL_RAISED = (
    f"linear-gradient({black.a[1]} -15%, transparent, {white.a[1]} 120%), "
    f"linear-gradient({gray[2]}, {gray[1]})"
)


def _trigger_size(height: str, gap: str, step: Step9, radius: str) -> dict[str, Any]:
    """Make the styles of a trigger of one size.

    Args:
        height: Its height.
        gap: The gap between its text and its icon.
        step: The step of the type scale.
        radius: The radius of its corners.

    Returns:
        The styles.
    """
    return {
        _HEIGHT: height,
        "gap": gap,
        "font_size": tokens.font_size[step],
        "line_height": tokens.line_height[step],
        "letter_spacing": tokens.letter_spacing[step],
        "border_radius": f"max({radius}, {tokens.radius.full})",
    }


def _states(rest: Any, raised: Any, disabled: Any = None) -> dict[str, Any]:
    """Make the value of a property of a trigger, by its state.

    Args:
        rest: The value at rest.
        raised: The value under the pointer, and while the list is open.
        disabled: The value of a disabled trigger, when it differs.

    Returns:
        The value under a condition for each state.
    """
    value = {"default": rest, _POINTER: {_HOVER: raised}, _OPEN: raised}
    if disabled is not None:
        value[_DISABLED] = disabled
    return value


_PLACEHOLDER_GRAY = {_SHOWN_COLOR: {_EMPTY: gray.a[10]}}
_PLACEHOLDER_ACCENT = {
    _SHOWN_COLOR: {_EMPTY: accent[12]},
    _SHOWN_OPACITY: {_EMPTY: 0.6},
}
_BOXED = {"box_sizing": "border-box", "height": f"var({_HEIGHT})"}

_TRIGGER_VARIANTS: dict[str, Any] = {
    "surface": {
        **_BOXED,
        **_PLACEHOLDER_GRAY,
        "color": {"default": gray[12], _DISABLED: gray.a[11]},
        "background_color": {"default": tokens.color.surface, _DISABLED: gray.a[2]},
        "box_shadow": _states(
            f"inset 0 0 0 1px {gray.a[7]}",
            f"inset 0 0 0 1px {gray.a[8]}",
            f"inset 0 0 0 1px {gray.a[6]}",
        ),
    },
    "classic": {
        **_BOXED,
        **_PLACEHOLDER_GRAY,
        "color": {"default": gray[12], _DISABLED: gray.a[11]},
        "background_color": {_DISABLED: gray[2]},
        "background_image": {
            "default": f"linear-gradient({gray[2]}, {gray[1]})",
            _DISABLED: "none",
        },
        "box_shadow": _states(
            _CLASSIC_SHADOW, _CLASSIC_RAISED, _CLASSIC_DISABLED_SHADOW
        ),
        "position": "relative",
        "z_index": 0,
        "_before": {
            "content": "''",
            "position": "absolute",
            "z_index": -1,
            "inset": "0",
            "border_width": "2px",
            "border_style": "solid",
            "border_color": "transparent",
            "background_clip": "content-box",
            "border_radius": "inherit",
            "pointer_events": "none",
            "background_color": {_DISABLED: gray.a[2]},
            "background_image": _states(
                _CLASSIC_FILL,
                _CLASSIC_FILL_RAISED,
                f"linear-gradient({black.a[1]} -20%, transparent, {white.a[1]})",
            ),
        },
    },
    "soft": {
        **_BOXED,
        **_PLACEHOLDER_ACCENT,
        "color": {"default": accent[12], _DISABLED: gray.a[11]},
        "background_color": _states(accent.a[3], accent.a[4], gray.a[3]),
        # A gray ring for a gray select.
        "outline_color": {_FOCUS: accent[8]},
    },
    "ghost": {
        **_PLACEHOLDER_ACCENT,
        "box_sizing": "content-box",
        "height": "fit-content",
        "padding_top": f"var({_GHOST_Y})",
        "padding_bottom": f"var({_GHOST_Y})",
        "padding_left": f"var({_GHOST_X})",
        "padding_right": f"var({_GHOST_X})",
        # It reaches as far out as its padding, so that its text lines up
        # with what is around it.
        "margin_top": f"calc(0px - var({_GHOST_Y}))",
        "margin_bottom": f"calc(0px - var({_GHOST_Y}))",
        "margin_left": f"calc(0px - var({_GHOST_X}))",
        "margin_right": f"calc(0px - var({_GHOST_X}))",
        "color": {"default": accent[12], _DISABLED: gray.a[11]},
        "background_color": _states("transparent", accent.a[3], "transparent"),
    },
}

_TRIGGER_PADDING = {"1": tokens.space[2], "2": tokens.space[3], "3": tokens.space[4]}
_GHOST_PADDING = {
    "1": (tokens.space[2], tokens.space[1]),
    "2": (tokens.space[2], tokens.space[1]),
    "3": (tokens.space[3], f"calc({tokens.space[1]} * 1.5)"),
}

SELECT_TRIGGER: ComponentStyles = {
    "base": unchecked({
        "appearance": "none",
        "margin": "0",
        "padding": "0",
        "border_width": "0",
        "border_style": "none",
        "background_color": "transparent",
        "background_image": "none",
        "text_transform": "inherit",
        "text_indent": "initial",
        "word_spacing": "inherit",
        "cursor": {"default": tokens.cursor.button, _DISABLED: tokens.cursor.disabled},
        "WebkitTapHighlightColor": "transparent",
        "display": "inline-flex",
        "align_items": "center",
        "justify_content": "space-between",
        "flex_shrink": 0,
        "user_select": "none",
        "vertical_align": "top",
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.regular,
        "font_style": "normal",
        "text_align": "start",
        "outline_style": {"default": "none", _FOCUS: "solid"},
        "outline_width": {"default": "medium", _FOCUS: "2px"},
        "outline_color": {"default": "currentcolor", _FOCUS: tokens.focus[8]},
        "outline_offset": {"default": "0", _FOCUS: "-1px"},
        _ICON_COLOR: {_DISABLED: gray.a[9]},
    }),
    "variants": {
        "_size": {
            "1": unchecked(
                _trigger_size(tokens.space[5], tokens.space[1], 1, tokens.radius[1])
            ),
            "2": unchecked(
                _trigger_size(
                    tokens.space[6],
                    f"calc({tokens.space[1]} * 1.5)",
                    2,
                    tokens.radius[2],
                )
            ),
            "3": unchecked(
                _trigger_size(tokens.space[7], tokens.space[2], 3, tokens.radius[3])
            ),
        },
        "variant": {
            variant: unchecked(style) for variant, style in _TRIGGER_VARIANTS.items()
        },
    },
    "defaults": {"_size": "2", "variant": "surface"},
    "compound": [
        *(
            {
                "props": {"_size": size, "variant": variant},
                "style": {"padding_left": padding, "padding_right": padding},
            }
            for size, padding in _TRIGGER_PADDING.items()
            for variant in ("surface", "classic", "soft")
        ),
        *(
            {
                "props": {"_size": size, "variant": "ghost"},
                "style": unchecked({_GHOST_X: x, _GHOST_Y: y}),
            }
            for size, (x, y) in _GHOST_PADDING.items()
        ),
    ],
    "parts": {
        # The text of the chosen option, or the placeholder.
        "shown": {
            "base": unchecked({
                "overflow": "hidden",
                "text_overflow": "ellipsis",
                "white_space": "nowrap",
                "color": f"var({_SHOWN_COLOR}, inherit)",
                "opacity": f"var({_SHOWN_OPACITY}, 1)",
            }),
        },
        "icon": {
            "base": unchecked({
                "flex_shrink": 0,
                "color": f"var({_ICON_COLOR}, inherit)",
            }),
            "variants": {
                "variant": {
                    "surface": {"opacity": 0.9},
                    "classic": {"opacity": 0.9},
                    "soft": {"opacity": 0.9},
                    "ghost": {},
                },
                "_size": {"3": {"width": "11px", "height": "11px"}},
            },
            "defaults": {"variant": "surface"},
        },
    },
}


def _content_size(
    padding: str,
    height: str,
    indicator: str,
    separator: str,
    radius: str,
    step: Step9,
    label_step: Step9,
    item_radius: str,
    check: str,
) -> dict[str, Any]:
    """Make the styles of a list of one size.

    Args:
        padding: The room around its items.
        height: The height of an item.
        indicator: The room before the text of an item, for its check.
        separator: The room after a separator.
        radius: The radius of the corners of the list.
        step: The step of the type scale of an item.
        label_step: The one of the label of a group, and of the height of
            the lines of both: no larger than the text of size 2.
        item_radius: The radius of the corners of an item.
        check: The side of the check of the chosen item.

    Returns:
        The styles.
    """
    return {
        _PADDING: padding,
        _ITEM_HEIGHT: height,
        _INDICATOR: indicator,
        _SEPARATOR: separator,
        "border_radius": radius,
        _FONT_SIZE: tokens.font_size[step],
        _LINE_HEIGHT: tokens.line_height[label_step],
        _LETTER_SPACING: tokens.letter_spacing[step],
        _LABEL_SIZE: tokens.font_size[label_step],
        _LABEL_SPACING: tokens.letter_spacing[label_step],
        _ITEM_RADIUS: item_radius,
        _CHECK: f"calc({check} * {tokens.scaling})",
    }


_LARGE = (
    tokens.space[2],
    tokens.space[6],
    tokens.space[5],
    tokens.space[3],
    tokens.radius[4],
)

_ROW: dict[str, Any] = {
    "display": "flex",
    "align_items": "center",
    "height": f"var({_ITEM_HEIGHT})",
    "padding_left": f"var({_INDICATOR})",
    "padding_right": f"var({_INDICATOR})",
    "user_select": "none",
    "font_size": f"var({_FONT_SIZE})",
    "line_height": f"var({_LINE_HEIGHT})",
    "letter_spacing": f"var({_LETTER_SPACING})",
}

SELECT_CONTENT: ComponentStyles = {
    "base": unchecked({
        **POPUP,
        "color": gray[12],
        "font_family": tokens.default.font_family,
        "font_weight": tokens.font_weight.regular,
        "font_style": "normal",
        "text_align": "start",
        "background_color": tokens.color.panel_solid,
        "box_shadow": tokens.shadow[5],
        "min_width": "anchor-size(width)",
        "outline_style": "none",
        "padding": f"var({_PADDING})",
        "overflow_y": "auto",
        "scrollbar_width": "thin",
        "scrollbar_color": f"{gray.a[8]} transparent",
    }),
    "variants": {
        "_size": {
            "1": unchecked(
                _content_size(
                    tokens.space[1],
                    tokens.space[5],
                    f"calc({tokens.space[5]} / 1.2)",
                    tokens.space[2],
                    tokens.radius[3],
                    1,
                    1,
                    tokens.radius[1],
                    "8px",
                )
            ),
            "2": unchecked(_content_size(*_LARGE, 2, 2, tokens.radius[2], "10px")),
            "3": unchecked(_content_size(*_LARGE, 3, 2, tokens.radius[2], "10px")),
        },
        "variant": {
            "solid": unchecked({_MARK: accent[9], _MARK_COLOR: accent.contrast}),
            "soft": unchecked({_MARK: accent.a[4]}),
        },
        "side": {"top": {}, "right": {}, "bottom": {}, "left": {}},
        "align": {"start": {}, "center": {}, "end": {}},
    },
    "defaults": {"_size": "2", "variant": "solid", "side": "bottom", "align": "start"},
    "compound": [
        *(
            {"props": place["props"], "style": unchecked(place["style"])}
            for place in placements("4px")
        ),
        {
            "props": {"variant": "solid", "high_contrast": "true"},
            "style": unchecked({_MARK: accent[12], _MARK_COLOR: accent[1]}),
        },
    ],
}

SELECT_ITEM: ComponentStyles = {
    "base": unchecked({
        **_ROW,
        "position": "relative",
        "box_sizing": "border-box",
        "outline_style": "none",
        "scroll_margin_top": f"var({_PADDING})",
        "scroll_margin_bottom": f"var({_PADDING})",
        "border_radius": f"var({_ITEM_RADIUS})",
        "cursor": {
            "default": tokens.cursor.menu_item,
            "[aria-disabled='true']": "default",
        },
        "color": {
            "default": "inherit",
            ":focus": f"var({_MARK_COLOR}, inherit)",
            "[aria-disabled='true']": gray.a[8],
        },
        "background_color": {":focus": f"var({_MARK})"},
        "--rx-select-check": {
            "default": "none",
            "[aria-selected='true']": "inline-flex",
        },
    }),
    "parts": {
        # The check of the chosen option.
        "indicator": {
            "base": unchecked({
                "position": "absolute",
                "left": "0",
                "width": f"var({_INDICATOR})",
                "display": "var(--rx-select-check)",
                "align_items": "center",
                "justify_content": "center",
            }),
        },
        "check": {
            "base": unchecked({
                "width": f"var({_CHECK})",
                "height": f"var({_CHECK})",
            }),
        },
    },
}

SELECT_LABEL: ComponentStyles = {
    "base": unchecked({
        **_ROW,
        "font_size": f"var({_LABEL_SIZE})",
        "letter_spacing": f"var({_LABEL_SPACING})",
        "color": gray.a[10],
        "cursor": "default",
    }),
}

SELECT_SEPARATOR: ComponentStyles = {
    "base": unchecked({
        "height": "1px",
        "margin_top": tokens.space[2],
        "margin_bottom": tokens.space[2],
        "margin_left": f"var({_INDICATOR})",
        "margin_right": f"var({_SEPARATOR})",
        "background_color": gray.a[6],
    }),
}

# The input that holds the value of a select, for a form: not seen, and not
# in the way of the pointer.
SELECT_VALUE: ComponentStyles = {
    "base": {
        "position": "absolute",
        "width": "1px",
        "height": "1px",
        "margin": "0",
        "padding": "0",
        "border_width": "0",
        "opacity": 0,
        "pointer_events": "none",
    },
}

SELECT: ComponentStyles = {"base": {"display": "contents"}}
