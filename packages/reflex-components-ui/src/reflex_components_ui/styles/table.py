"""The look of a table."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.scroll_area import SCROLL_BOX, SCROLL_CONTENT

gray = tokens.gray

# What the root sets and the cells read, as in Radix Themes.
_RADIUS = "--table-border-radius"
_CELL_PADDING = "--table-cell-padding"
_CELL_MIN_HEIGHT = "--table-cell-min-height"
_ROW_BACKGROUND = "--table-row-background-color"
_ROW_SHADOW = "--table-row-box-shadow"

# What Radix Themes selects by ancestor, handed down instead: the background
# of the header of a surface table, and the line under the last row of its
# body, which a surface table does not draw.
_HEADER_BACKGROUND = "--rx-table-header-background"
_BODY_LAST_ROW_SHADOW = "--rx-table-body-last-row-shadow"
_LAST_ROW_SHADOW = "--rx-table-last-row-shadow"

_LINE = f"inset 0 -1px {gray.a[5]}"

# The radius, the padding and the least height of a cell, and the text.
_SIZES: dict[str, tuple[str, str, str, str, str]] = {
    "1": (
        tokens.radius[3],
        tokens.space[2],
        f"calc(36px * {tokens.scaling})",
        tokens.font_size[2],
        tokens.line_height[2],
    ),
    "2": (
        tokens.radius[4],
        tokens.space[3],
        f"calc(44px * {tokens.scaling})",
        tokens.font_size[2],
        tokens.line_height[2],
    ),
    "3": (
        tokens.radius[4],
        f"{tokens.space[3]} {tokens.space[4]}",
        tokens.space[8],
        tokens.font_size[3],
        tokens.line_height[3],
    ),
}

TABLE_ROOT: ComponentStyles = {
    "variants": {
        "size": {
            size: unchecked({
                _RADIUS: radius,
                _CELL_PADDING: padding,
                _CELL_MIN_HEIGHT: height,
            })
            for size, (radius, padding, height, _, _) in _SIZES.items()
        },
        "variant": {
            "surface": unchecked({
                "box_sizing": "border-box",
                "border_width": "1px",
                "border_style": "solid",
                # Half see-through, to blend with what is behind the table.
                "border_color": f"color-mix(in oklab, {gray.a[5]}, {gray[6]})",
                "border_radius": f"var({_RADIUS})",
                "background_color": tokens.color.panel,
                "backdrop_filter": tokens.panel.backdrop_filter,
                "background_clip": "padding-box",
                "position": "relative",
                _HEADER_BACKGROUND: gray.a[2],
                _BODY_LAST_ROW_SHADOW: "none",
            }),
        },
    },
    "defaults": {"size": "2", "variant": "ghost"},
    "parts": {
        # The table scrolls sideways when it is wider than its place: the
        # box of a scroll area, which scrolls natively.
        "scroll": {
            "base": {
                **SCROLL_BOX,
                "overflow_x": "auto",
                "overflow_y": "auto",
                "overscroll_behavior_x": "contain",
            },
        },
        "content": SCROLL_CONTENT,
        "table": {
            "base": unchecked({
                _ROW_BACKGROUND: "transparent",
                _ROW_SHADOW: _LINE,
                "width": "100%",
                "text_align": "left",
                "vertical_align": "top",
                "border_collapse": "collapse",
                "border_radius": f"calc(var({_RADIUS}) - 1px)",
                "border_spacing": "0",
                "box_sizing": "border-box",
                # Lets a height of 100% work inside a cell.
                "height": "0",
            }),
            "variants": {
                "size": {
                    size: {"font_size": font_size, "line_height": line_height}
                    for size, (_, _, _, font_size, line_height) in _SIZES.items()
                },
                "variant": {"surface": {"overflow": "hidden"}},
            },
            "defaults": {"size": "2"},
        },
    },
}

TABLE_HEADER: ComponentStyles = {
    "base": unchecked({
        "vertical_align": "inherit",
        _ROW_BACKGROUND: f"var({_HEADER_BACKGROUND}, transparent)",
    }),
}

TABLE_BODY: ComponentStyles = {
    "base": unchecked({
        "vertical_align": "inherit",
        _LAST_ROW_SHADOW: f"var({_BODY_LAST_ROW_SHADOW}, {_LINE})",
    }),
}

TABLE_ROW: ComponentStyles = {
    "base": unchecked({
        "vertical_align": "inherit",
        "color": gray[12],
        _ROW_SHADOW: {":last-child": f"var({_LAST_ROW_SHADOW}, {_LINE})"},
    }),
    "variants": {
        "align": {
            "start": {"vertical_align": "top"},
            "center": {"vertical_align": "middle"},
            "end": {"vertical_align": "bottom"},
            "baseline": {"vertical_align": "baseline"},
        },
    },
}


def cell_styles(font_weight: str | None) -> ComponentStyles:
    """Make the style table of a cell.

    Args:
        font_weight: The weight of a header cell, which the browser would
            otherwise choose.

    Returns:
        The table.
    """
    base: dict[str, Any] = {
        "background_color": f"var({_ROW_BACKGROUND})",
        "box_shadow": f"var({_ROW_SHADOW})",
        "box_sizing": "border-box",
        "vertical_align": "inherit",
        "padding": f"var({_CELL_PADDING})",
        # Works as a least height.
        "height": f"var({_CELL_MIN_HEIGHT})",
    }
    if font_weight is not None:
        base["font_weight"] = font_weight
    return {
        "base": unchecked(base),
        "variants": {
            "justify": {
                "start": {"text_align": "left"},
                "center": {"text_align": "center"},
                "end": {"text_align": "right"},
            },
        },
    }


TABLE_CELL: ComponentStyles = cell_styles(None)
TABLE_COLUMN_HEADER_CELL: ComponentStyles = cell_styles("bold")
TABLE_ROW_HEADER_CELL: ComponentStyles = cell_styles("normal")
