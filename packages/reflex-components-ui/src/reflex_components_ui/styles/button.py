"""The look of a button, which an icon button shares."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, CompoundStyle, unchecked
from reflex_components_ui.styles.appearance import by_appearance
from reflex_components_ui.styles.spinner import (
    CENTERED,
    HIDDEN_CONTENT,
    LEAF,
    OPACITY,
    SPINNER_BASE,
    SPINNER_SIZE,
)
from reflex_components_ui.styles.typography import ACCENT_SCOPE

accent, gray, white, black = tokens.accent, tokens.gray, tokens.white, tokens.black

# What a button tells the icons inside it, which the base stylesheet reads:
# Radix Themes dims every `svg` below a button that is not a ghost.
ICON_OPACITY = "--rx-icon-opacity"

# What the solid code inside a hovered link is filtered by, when it is high
# contrast: the filter of a high-contrast solid button under the pointer.
SOLID_HIGH_CONTRAST_HOVER_FILTER = by_appearance(
    "contrast(0.88) saturate(1.1) brightness(1.1)",
    "contrast(0.88) saturate(1.3) brightness(1.18)",
)

_HEIGHT = "--base-button-height"
_PRESSED_PADDING = "--base-button-classic-active-padding-top"

# The states. Under the pointer only where there is one, and not while
# pressed: StyleX places a rule inside a media query after the others, and a
# pressed button is not the one under the pointer. A disabled button is
# selected by attribute, which wins over every pseudo-class.
_POINTER = "@media (hover: hover)"
_HOVER = ":hover:not(:active)"
_ACTIVE = ":active:not([data-state='open'])"
_DISABLED = "[data-disabled]"
_FOCUS = ":focus-visible"
_TOUCH = "@media (pointer: coarse)"


def _hover(style: dict[str, Any]) -> dict[str, Any]:
    """Make the styles of a button under the pointer.

    Args:
        style: The styles.

    Returns:
        The styles, where a pointer can hover and the button is not pressed.
    """
    return {_POINTER: {_HOVER: style}}


def _ring(color: str, offset: str) -> dict[str, Any]:
    """Make the ring of the keyboard's focus.

    Args:
        color: The color of the ring.
        offset: How far from the edge of the button it is.

    Returns:
        The outline.
    """
    return {
        "outline_width": "2px",
        "outline_style": "solid",
        "outline_color": color,
        "outline_offset": offset,
    }


# Instead of the highlight of a tap, which is turned off.
_TAP: dict[str, Any] = {
    _TOUCH: {
        f"{_ACTIVE[:-1]}, {_DISABLED}, {_FOCUS})": {
            "outline_width": "0.5em",
            "outline_style": "solid",
            "outline_color": accent.a[4],
            "outline_offset": "0",
        }
    }
}

_DISABLED_FILL: dict[str, Any] = {"color": gray.a[8], "background_color": gray.a[3]}

_CLASSIC_TOP = by_appearance(
    f"inset 0 0 0 1px {gray.a[4]}, inset 0 -2px 1px {gray.a[3]}",
    f"inset 0 0 0 1px {white.a[2]}, inset 0 4px 2px -2px {white.a[3]}, "
    f"inset 0 1px 1px {white.a[6]}, inset 0 -1px 1px {black.a[6]}",
)
_CLASSIC_BOTTOM = by_appearance(
    f"inset 0 4px 2px -2px {white.a[9]}, inset 0 2px 1px -1px {white.a[9]}",
    "0 0 transparent",
)
_CLASSIC_DISABLED_SHADOW = by_appearance(
    f"inset 0 0 0 1px {gray.a[4]}, inset 0 -2px 1px {gray.a[3]}, "
    f"inset 0 4px 2px -2px {white.a[9]}, inset 0 2px 1px -1px {white.a[9]}",
    f"inset 0 0 0 1px {gray.a[5]}, inset 0 4px 2px -2px {gray.a[2]}, "
    f"inset 0 1px 1px {gray.a[5]}, inset 0 -1px 1px {black.a[3]}, "
    f"inset 0 0 0 1px {gray.a[2]}",
)
_CLASSIC_ACTIVE = f":active:not([data-state='open'], {_DISABLED})"


def _classic(color: str) -> dict[str, Any]:
    """Make the fill of a classic button.

    Args:
        color: The color of the button.

    Returns:
        The background and the shadows that make it look raised.
    """
    return {
        "background_color": color,
        "background_image": (
            f"linear-gradient(to bottom, transparent 50%, {gray.a[4]}), "
            f"linear-gradient(to bottom, transparent 50%, {color} 80%)"
        ),
        "box_shadow": f"{_CLASSIC_TOP}, inset 0 0 0 1px {color}, {_CLASSIC_BOTTOM}",
    }


_VARIANTS: dict[str, Any] = {
    "classic": {
        **_classic(accent[9]),
        "color": accent.contrast,
        "position": "relative",
        "z_index": 0,
        # The pseudo-element is the outermost block, with its states inside:
        # a style merged over this one keeps what it does not set for it.
        "_after": {
            "content": "''",
            "box_sizing": "border-box",
            "position": "absolute",
            "border_radius": "inherit",
            "pointer_events": "none",
            "inset": "0",
            "z_index": -1,
            "border_width": by_appearance("2px", "1px"),
            "border_style": "solid",
            "border_color": "transparent",
            "background_clip": "content-box",
            "background_color": "inherit",
            "background_image": (
                f"linear-gradient({black.a[1]}, transparent, {white.a[2]})"
            ),
            "box_shadow": f"inset 0 2px 3px -1px {white.a[4]}",
            **_hover({
                "background_color": accent[10],
                "background_image": (
                    f"linear-gradient({black.a[2]} -15%, transparent, {white.a[3]})"
                ),
            }),
            _CLASSIC_ACTIVE: {
                "box_shadow": "none",
                "background_color": "inherit",
                "background_image": (
                    f"linear-gradient({black.a[2]}, transparent, {white.a[3]})"
                ),
            },
            _DISABLED: {
                "box_shadow": "none",
                "background_color": gray.a[2],
                "background_image": (
                    f"linear-gradient({black.a[1]} -20%, transparent, {white.a[1]})"
                ),
            },
        },
        **_TAP,
        f"{_FOCUS}:not({_DISABLED})": _ring(tokens.focus[8], "2px"),
        _CLASSIC_ACTIVE: {
            "background_color": accent[9],
            "background_image": f"linear-gradient({black.a[1]}, transparent)",
            "padding_top": f"var({_PRESSED_PADDING})",
            "box_shadow": (
                f"inset 0 4px 2px -2px {gray.a[4]}, inset 0 1px 1px {gray.a[7]}, "
                f"inset 0 0 0 1px {gray.a[5]}, inset 0 0 0 1px {accent[9]}, "
                f"inset 0 3px 2px {gray.a[3]}, inset 0 0 0 1px {white.a[7]}, "
                f"inset 0 -2px 1px {white.a[5]}"
            ),
        },
        _DISABLED: {
            "color": gray.a[8],
            "background_color": gray[2],
            "background_image": "none",
            "box_shadow": _CLASSIC_DISABLED_SHADOW,
            "filter": "none",
        },
    },
    "solid": {
        "background_color": accent[9],
        "color": accent.contrast,
        **_hover({"background_color": accent[10]}),
        _ACTIVE: {
            "background_color": accent[10],
            "filter": by_appearance(
                "brightness(0.92) saturate(1.1)", "brightness(1.08)"
            ),
        },
        **_TAP,
        f"{_FOCUS}:not({_DISABLED})": _ring(tokens.focus[8], "2px"),
        _DISABLED: {**_DISABLED_FILL, "filter": "none"},
    },
    "soft": {
        "color": accent.a[11],
        "background_color": accent.a[3],
        _FOCUS: _ring(accent[8], "-1px"),
        **_hover({"background_color": accent.a[4]}),
        _ACTIVE: {"background_color": accent.a[5]},
        _DISABLED: _DISABLED_FILL,
    },
    "ghost": {
        "color": accent.a[11],
        **_hover({"background_color": accent.a[3]}),
        _FOCUS: _ring(tokens.focus[8], "-1px"),
        _ACTIVE: {"background_color": accent.a[4]},
        _DISABLED: {"color": gray.a[8], "background_color": "transparent"},
        "box_sizing": "content-box",
        # Not stretched by a flex or grid container.
        "height": "fit-content",
    },
    "outline": {
        "box_shadow": f"inset 0 0 0 1px {accent.a[8]}",
        "color": accent.a[11],
        **_hover({"background_color": accent.a[2]}),
        _ACTIVE: {"background_color": accent.a[3]},
        _FOCUS: _ring(tokens.focus[8], "-1px"),
        _DISABLED: {
            "color": gray.a[8],
            "box_shadow": f"inset 0 0 0 1px {gray.a[7]}",
            "background_color": "transparent",
        },
    },
    "surface": {
        "background_color": accent.surface,
        "box_shadow": f"inset 0 0 0 1px {accent.a[7]}",
        "color": accent.a[11],
        **_hover({"box_shadow": f"inset 0 0 0 1px {accent.a[8]}"}),
        _ACTIVE: {
            "background_color": accent.a[3],
            "box_shadow": f"inset 0 0 0 1px {accent.a[8]}",
        },
        _FOCUS: _ring(tokens.focus[8], "-1px"),
        _DISABLED: {
            "color": gray.a[8],
            "box_shadow": f"inset 0 0 0 1px {gray.a[6]}",
            "background_color": gray.a[2],
        },
    },
}

_HIGH_CONTRAST: dict[str, Any] = {
    "classic": {
        **_classic(accent[12]),
        "color": gray[1],
        "_after": {
            "background_image": (
                f"linear-gradient({black.a[3]}, transparent, {white.a[2]})"
            ),
            **_hover({
                "background_color": accent[12],
                "background_image": (
                    f"linear-gradient({black.a[5]}, transparent, {white.a[2]})"
                ),
            }),
            _CLASSIC_ACTIVE: {
                "background_image": (
                    f"linear-gradient({black.a[5]}, transparent, {white.a[3]})"
                ),
            },
        },
        **_hover({
            "filter": by_appearance(
                "contrast(0.88) saturate(1.1) brightness(1.1)",
                "contrast(0.88) saturate(1.3) brightness(1.14)",
            ),
        }),
        _CLASSIC_ACTIVE: {
            "background_color": accent[12],
            "filter": by_appearance(
                "contrast(0.82) saturate(1.2) brightness(1.16)",
                "brightness(0.95) saturate(1.2)",
            ),
            # Radix Themes names two custom properties here that nothing
            # defines, which leaves the pressed button without a shadow.
            "box_shadow": "none",
        },
    },
    "solid": {
        "background_color": accent[12],
        "color": gray[1],
        **_hover({
            "background_color": accent[12],
            "filter": SOLID_HIGH_CONTRAST_HOVER_FILTER,
        }),
        _ACTIVE: {
            "background_color": accent[12],
            "filter": by_appearance(
                "contrast(0.82) saturate(1.2) brightness(1.16)",
                "brightness(0.95) saturate(1.2)",
            ),
        },
    },
    "soft": {"color": accent[12]},
    "ghost": {"color": accent[12]},
    "outline": {
        "box_shadow": f"inset 0 0 0 1px {accent.a[7]}, inset 0 0 0 1px {gray.a[11]}",
        "color": accent[12],
    },
    "surface": {"color": accent[12]},
}


def _over(under: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    """Lay the rules of one selector over those of another, block by block.

    A compound style replaces the whole value of each property it sets, the
    conditions of the variant included, so the style of a high-contrast
    button is the one of its variant with the high-contrast rules written
    into the same blocks.

    Args:
        under: The styles of the variant.
        top: The styles that high contrast changes.

    Returns:
        The styles of the high-contrast variant.
    """
    merged = dict(under)
    for key, value in top.items():
        below: Any = merged.get(key)
        merged[key] = (
            _over(below, value)
            if value.__class__ is dict and below.__class__ is dict
            else value
        )
    return merged


# The size of the spinner of a loading button, by the size of the button.
_SPINNER_SIZE = {"1": "1", "2": "2", "3": "2", "4": "3"}

_PARTS: dict[str, ComponentStyles] = {
    # The children of a loading button keep their place and are not shown.
    "content": {"base": HIDDEN_CONTENT},
    # They are read out all the same.
    "label": {
        "base": {
            "position": "absolute",
            # All of the border, as the visually hidden label of Radix
            # Themes: a style left `solid` is still a computed difference.
            "border": "0",
            "width": "1px",
            "height": "1px",
            "padding": "0",
            "margin": "-1px",
            "overflow": "hidden",
            "clip": "rect(0, 0, 0, 0)",
            "white_space": "nowrap",
            "word_wrap": "normal",
        }
    },
    "overlay": {"base": CENTERED},
    "spinner": {
        "base": SPINNER_BASE,
        "variants": {
            "size": {
                size: SPINNER_SIZE[spinner] for size, spinner in _SPINNER_SIZE.items()
            }
        },
        "defaults": {"size": "2"},
    },
    "leaf": {"base": LEAF},
}

# The height, the radius and the padding on each side of each size.
_SIZES: dict[str, tuple[str, str, str]] = {
    "1": (tokens.space[5], tokens.radius[1], tokens.space[2]),
    "2": (tokens.space[6], tokens.radius[2], tokens.space[3]),
    "3": (tokens.space[7], tokens.radius[3], tokens.space[4]),
    "4": (tokens.space[8], tokens.radius[4], tokens.space[5]),
}

# The space between the children of a button of each size, and its text.
_TEXT: dict[str, dict[str, str]] = {
    "1": {
        "gap": tokens.space[1],
        "font_size": tokens.font_size[1],
        "line_height": tokens.line_height[1],
        "letter_spacing": tokens.letter_spacing[1],
    },
    "2": {
        "gap": tokens.space[2],
        "font_size": tokens.font_size[2],
        "line_height": tokens.line_height[2],
        "letter_spacing": tokens.letter_spacing[2],
    },
    "3": {
        "gap": tokens.space[3],
        "font_size": tokens.font_size[3],
        "line_height": tokens.line_height[3],
        "letter_spacing": tokens.letter_spacing[3],
    },
    "4": {
        "gap": tokens.space[3],
        "font_size": tokens.font_size[4],
        "line_height": tokens.line_height[4],
        "letter_spacing": tokens.letter_spacing[4],
    },
}

# What everything a button does not set is, as Radix Themes unsets it all:
# the look the browser gives a button, and what a reset of the page adds.
_RESET: dict[str, Any] = {
    "margin": "0",
    "padding": "0",
    "border_width": "0",
    "border_style": "none",
    "background_color": "transparent",
    "background_image": "none",
    "appearance": "none",
    "box_sizing": "border-box",
    "font_size": "inherit",
    "line_height": "inherit",
    "letter_spacing": "inherit",
    "font_weight": "normal",
    "text_transform": "inherit",
    "text_indent": "initial",
    "text_shadow": "inherit",
    "word_spacing": "inherit",
    "cursor": {
        "default": "inherit",
        ":where(button)": tokens.cursor.button,
        ":any-link": tokens.cursor.link,
        _DISABLED: tokens.cursor.disabled,
    },
    "outline_style": "none",
    "WebkitTapHighlightColor": "transparent",
}


def _ghost_box(y: str, x: str) -> dict[str, str]:
    """Make the padding of a ghost button, and the margins that take it back.

    A ghost button sits where its content would without the padding. Each
    side is written out: a size whose padding is a calculation would keep
    the shorthand whole where the other sizes are split, and a size per
    breakpoint would mix the two.

    Args:
        y: The padding above and below.
        x: The padding on each side.

    Returns:
        The paddings and the margins.
    """
    style = {}
    for side, padding in (("top", y), ("right", x), ("bottom", y), ("left", x)):
        style[f"padding_{side}"] = padding
        style[f"margin_{side}"] = f"calc(0px - {padding})"
    return style


def button_styles(icon: bool) -> ComponentStyles:
    """Make the style table of a button.

    Args:
        icon: Whether the button holds a single icon, and is as wide as it
            is tall.

    Returns:
        The table.
    """
    compound: list[CompoundStyle] = []
    sizes: dict[str, Any] = {
        size: {
            _PRESSED_PADDING: "1px" if size == "1" else "2px",
            _HEIGHT: height,
            "border_radius": f"max({radius}, {tokens.radius.full})",
        }
        for size, (height, radius, _) in _SIZES.items()
    }
    if icon:
        ghost_padding = {
            "1": tokens.space[1],
            "2": f"calc({tokens.space[1]} * 1.5)",
            "3": tokens.space[2],
            "4": tokens.space[3],
        }
        ghost = {
            size: _ghost_box(padding, padding)
            for size, padding in ghost_padding.items()
        }
        solid_size: dict[str, Any] = {
            size: {"height": f"var({_HEIGHT})", "width": f"var({_HEIGHT})"}
            for size in sizes
        }
    else:
        for size, text in _TEXT.items():
            sizes[size].update(text)
        ghost_paddings = {
            "1": (tokens.space[1], tokens.space[2], tokens.space[1]),
            "2": (tokens.space[1], tokens.space[2], tokens.space[1]),
            "3": (f"calc({tokens.space[1]} * 1.5)", tokens.space[3], tokens.space[2]),
            "4": (tokens.space[2], tokens.space[4], tokens.space[2]),
        }
        ghost = {
            size: {"gap": gap, **_ghost_box(y, x)}
            for size, (y, x, gap) in ghost_paddings.items()
        }
        solid_size = {
            size: {
                "height": f"var({_HEIGHT})",
                "padding_left": padding,
                "padding_right": padding,
                "font_weight": tokens.font_weight.medium,
                ICON_OPACITY: "0.9",
            }
            for size, (_, _, padding) in _SIZES.items()
        }
    for variant in _VARIANTS:
        by_size = ghost if variant == "ghost" else solid_size
        compound.extend(
            {"props": {"variant": variant, "size": size}, "style": unchecked(style)}
            for size, style in by_size.items()
        )
    for variant, style in _HIGH_CONTRAST.items():
        compound.append({
            "props": {"variant": variant, "high_contrast": "true"},
            "style": unchecked(_over(_VARIANTS[variant], style)),
        })
    return {
        "base": unchecked({
            **_RESET,
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "flex_shrink": 0,
            "user_select": "none",
            "vertical_align": "top",
            "font_family": tokens.default.font_family,
            "font_style": "normal",
            "text_align": "center",
            _DISABLED: {OPACITY: "1"},
        }),
        "variants": {
            "size": {size: unchecked(style) for size, style in sizes.items()},
            "variant": {
                variant: unchecked(style) for variant, style in _VARIANTS.items()
            },
            "loading": {"true": {"position": "relative"}},
            "color_scheme": {"true": unchecked(ACCENT_SCOPE)},
        },
        "defaults": {"size": "2", "variant": "solid"},
        "compound": compound,
        "parts": _PARTS,
    }


BUTTON: ComponentStyles = button_styles(icon=False)
ICON_BUTTON: ComponentStyles = button_styles(icon=True)
