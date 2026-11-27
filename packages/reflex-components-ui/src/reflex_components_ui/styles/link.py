"""The look of a link."""

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.text import TEXT_BASE
from reflex_components_ui.styles.typography import (
    ACCENT_LINK,
    ACCENT_LINK_LINE,
    ACCENT_LINK_LINE_COLOR,
    ACCENT_SCOPE,
    LINK_CODE_OUTLINE,
    LINK_CODE_SOFT,
    LINK_CODE_SOLID,
    SIZE,
    TRIM,
    WEIGHT,
    underline_color,
)

# A line is hard to see under code with a background, when that is all the
# link holds.
_ONLY_CODE = ':has(code[data-variant]:not([data-variant="ghost"]):only-child)'


def _line_color(color: str) -> dict[str, str]:
    """Make the color of the line under a link.

    Args:
        color: The color.

    Returns:
        The color, unless the line is hidden.
    """
    return {"default": color, _ONLY_CODE: "transparent"}


def _line(rest: str, hover: str) -> dict[str, Any]:
    """Make the line of a link: never under the ring of the keyboard's focus.

    Args:
        rest: The line at rest.
        hover: The line under the pointer.

    Returns:
        The line in each state.
    """
    return {
        "default": rest,
        ":focus-visible": "none",
        "@media (hover: hover)": {":hover": hover, ":focus-visible": "none"},
    }


LINK: ComponentStyles = {
    "base": {
        **TEXT_BASE,
        # Without a color of its own, inside an element that has one.
        "color": f"var({ACCENT_LINK}, {tokens.accent.a[11]})",
        "WebkitTapHighlightColor": "transparent",
        ":any-link": {"cursor": tokens.cursor.link},
        "[data-disabled]": {"cursor": tokens.cursor.disabled},
        "text_decoration_style": "solid",
        "text_decoration_thickness": "min(2px, max(1px, 0.05em))",
        "text_underline_offset": "calc(0.025em + 2px)",
        "text_decoration_color": _line_color(underline_color(5)),
        ":focus-visible": {
            "border_radius": f"calc(0.07em * {tokens.radius.factor})",
            "outline_color": tokens.focus[8],
            "outline_width": "2px",
            "outline_style": "solid",
            "outline_offset": "2px",
        },
        "@media (pointer: coarse)": {
            ":active:not(:focus-visible, [data-state='open'])": {
                "outline_width": "0.75em",
                "outline_style": "solid",
                "outline_color": tokens.accent.a[4],
                "outline_offset": "-0.6em",
            },
        },
        LINK_CODE_SOLID: tokens.accent[10],
        LINK_CODE_SOFT: tokens.accent.a[4],
        LINK_CODE_OUTLINE: tokens.accent.a[2],
    },
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        "trim": TRIM,
        "underline": {
            "auto": {
                "text_decoration_line": _line(
                    f"var({ACCENT_LINK_LINE}, none)", "underline"
                ),
                "text_decoration_color": _line_color(
                    f"var({ACCENT_LINK_LINE_COLOR}, {underline_color(5)})"
                ),
            },
            "hover": {"text_decoration_line": _line("none", "underline")},
            "always": {"text_decoration_line": _line("underline", "underline")},
            "none": {"text_decoration_line": "none"},
        },
        "color_scheme": {"true": {**ACCENT_SCOPE, "color": tokens.accent.a[11]}},
        "high_contrast": {"true": {"color": tokens.accent[12]}},
    },
    "defaults": {"underline": "auto"},
    "compound": [
        {
            "props": {"underline": "auto", "color_scheme": "true"},
            "style": {
                "text_decoration_line": _line("none", "underline"),
                "text_decoration_color": _line_color(underline_color(5)),
            },
        },
        {
            "props": {"underline": "auto", "high_contrast": "true"},
            "style": {
                "text_decoration_line": _line("underline", "underline"),
                "text_decoration_color": _line_color(underline_color(6)),
            },
        },
    ],
}
