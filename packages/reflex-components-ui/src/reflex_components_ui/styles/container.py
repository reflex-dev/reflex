"""The look of the container that bounds the width of a page."""

from reflex_components_ui.style import ComponentStyles

CONTAINER: ComponentStyles = {
    "base": {
        "display": "flex",
        "box_sizing": "border-box",
        "flex_direction": "column",
        "align_items": "center",
        "flex_shrink": "0",
        "flex_grow": "1",
    },
    "parts": {
        "inner": {
            "base": {"width": "100%"},
            # The widths Radix Themes declares beside its container: they are
            # not design tokens, and no theme changes them.
            "variants": {
                "size": {
                    "1": {"max_width": "448px"},
                    "2": {"max_width": "688px"},
                    "3": {"max_width": "880px"},
                    "4": {"max_width": "1136px"},
                },
            },
        },
    },
}
