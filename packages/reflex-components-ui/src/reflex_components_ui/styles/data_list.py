"""The look of a data list: labels beside, or above, their values."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.text import TEXT_BASE
from reflex_components_ui.styles.typography import ACCENT_SCOPE, SIZE

# What the list tells its items, labels and values, which Radix Themes
# selects below the classes of the list: how an item lays out its label and
# its value, how far a value may reach out of its row, and how narrow a label
# may be.
_ITEM_DISPLAY = "--rx-data-list-item-display"
_ITEM_DIRECTION = "--rx-data-list-item-direction"
_ITEM_COLUMNS = "--rx-data-list-item-columns"
_ITEM_SPAN = "--rx-data-list-item-span"
_ITEM_ALIGN = "--rx-data-list-item-align"
_ITEM_GAP = "--rx-data-list-item-gap"
_VALUE_TRIM = "--rx-data-list-value-trim"
_LABEL_MIN_WIDTH = "--rx-data-list-label-min-width"

# The margins of the value of an item, as Radix Themes names them.
_VALUE_TOP = "--data-list-value-margin-top"
_VALUE_BOTTOM = "--data-list-value-margin-bottom"

_GAP = {
    "1": tokens.space[3],
    "2": tokens.space[4],
    "3": f"calc({tokens.space[4]} * 1.25)",
}

_TRIM = f"var({_VALUE_TRIM}, 0px)"


def _value_margins(start: str, end: str, first: str, last: str) -> dict[str, Any]:
    """Make the margins of the value of an item.

    Args:
        start: The margin above the value.
        end: The margin below it.
        first: The margin above the value of the first item.
        last: The margin below the value of the last item.

    Returns:
        The custom properties the value reads its margins from.
    """
    return {
        _VALUE_TOP: {"default": start, ":first-child": first},
        _VALUE_BOTTOM: {"default": end, ":last-child": last},
    }


# A value reaches out of its row where the alignment lets it, and out of the
# list only when it is centered: its two margins are then always equal.
_ALIGN: dict[str, tuple[str, dict[str, Any]]] = {
    "baseline": ("baseline", _value_margins(_TRIM, _TRIM, "0px", "0px")),
    "start": ("flex-start", _value_margins("0px", _TRIM, "0px", "0px")),
    "center": ("center", _value_margins(_TRIM, _TRIM, _TRIM, _TRIM)),
    "end": ("flex-end", _value_margins(_TRIM, "0px", "0px", "0px")),
    "stretch": ("stretch", _value_margins("0px", "0px", "0px", "0px")),
}

# Zero-width joiner to establish a baseline: lets what a label or a value
# holds align with the text of the other.
_BASELINE: dict[str, Any] = {"_before": {"content": "'‍'"}}

_LEADING_TRIM_START = (
    f"calc({tokens.default.leading_trim_start} - var(--line-height) / 2)"
)
_LEADING_TRIM_END = f"calc({tokens.default.leading_trim_end} - var(--line-height) / 2)"

DATA_LIST_ROOT: ComponentStyles = {
    "base": {
        **TEXT_BASE,
        "overflow_wrap": "anywhere",
        "font_family": tokens.default.font_family,
        "font_style": "normal",
        "text_align": "start",
    },
    "variants": {
        "size": {
            # The longhands: a shorthand is only split when its value is a
            # token alone, and each size has to set the same properties.
            size: unchecked({**SIZE[size], "row_gap": gap, "column_gap": gap})
            for size, gap in _GAP.items()
        },
        "orientation": {
            "vertical": unchecked({
                "display": "flex",
                "flex_direction": "column",
                _ITEM_DISPLAY: "flex",
                _ITEM_DIRECTION: "column",
                _ITEM_COLUMNS: "none",
                _ITEM_SPAN: "auto",
                _ITEM_ALIGN: "normal",
                _ITEM_GAP: tokens.space[1],
                _VALUE_TRIM: "0px",
                _LABEL_MIN_WIDTH: "0px",
            }),
            "horizontal": unchecked({
                "display": "grid",
                "grid_template_columns": "auto 1fr",
                _ITEM_DISPLAY: "grid",
                _ITEM_DIRECTION: "row",
                _ITEM_COLUMNS: "subgrid",
                _ITEM_SPAN: "span 2",
                _ITEM_ALIGN: "baseline",
                # None: an item then has the gap of the list, whatever sets it.
                _ITEM_GAP: "initial",
                _VALUE_TRIM: "-0.25em",
                _LABEL_MIN_WIDTH: "120px",
            }),
        },
        # The margins are those of the first and of the last item.
        "trim": {
            "normal": unchecked({
                "--leading-trim-start": "initial",
                "--leading-trim-end": "initial",
            }),
            "start": unchecked({
                "--leading-trim-start": _LEADING_TRIM_START,
                "--leading-trim-end": "initial",
            }),
            "end": unchecked({
                "--leading-trim-start": "initial",
                "--leading-trim-end": _LEADING_TRIM_END,
            }),
            "both": unchecked({
                "--leading-trim-start": _LEADING_TRIM_START,
                "--leading-trim-end": _LEADING_TRIM_END,
            }),
        },
    },
    "defaults": {"size": "2", "orientation": "horizontal"},
}

DATA_LIST_ITEM: ComponentStyles = {
    "base": unchecked({
        "display": f"var({_ITEM_DISPLAY}, block)",
        "flex_direction": f"var({_ITEM_DIRECTION}, row)",
        "grid_template_columns": f"var({_ITEM_COLUMNS}, none)",
        "grid_column_start": f"var({_ITEM_SPAN}, auto)",
        "align_items": f"var({_ITEM_ALIGN}, normal)",
        "row_gap": f"var({_ITEM_GAP}, inherit)",
        "column_gap": f"var({_ITEM_GAP}, inherit)",
        "margin_top": {":first-child": "var(--leading-trim-start)"},
        "margin_bottom": {":last-child": "var(--leading-trim-end)"},
        **_ALIGN["baseline"][1],
    }),
    "variants": {
        "align": {
            align: unchecked({"align_items": align_items, **margins})
            for align, (align_items, margins) in _ALIGN.items()
        },
    },
}

DATA_LIST_LABEL: ComponentStyles = {
    "base": unchecked({
        "display": "flex",
        "color": tokens.gray.a[11],
        "min_width": f"var({_LABEL_MIN_WIDTH})",
        **_BASELINE,
    }),
    "variants": {
        "color_scheme": {
            "true": unchecked({**ACCENT_SCOPE, "color": tokens.accent.a[11]}),
        },
    },
}

DATA_LIST_VALUE: ComponentStyles = {
    "base": unchecked({
        "display": "flex",
        "margin_left": "0",
        "margin_right": "0",
        "margin_top": f"var({_VALUE_TOP}, 0px)",
        "margin_bottom": f"var({_VALUE_BOTTOM}, 0px)",
        # A value can be truncated.
        "min_width": "0px",
        **_BASELINE,
    }),
}
