"""The look of a separator: a line between two things."""

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked

# The length of the line, which both orientations read.
_SIZE = "--separator-size"

SEPARATOR: ComponentStyles = {
    "base": {
        "display": "block",
        # Gray unless the separator has a color of its own.
        "background_color": tokens.gray.a[6],
    },
    "variants": {
        "orientation": {
            "horizontal": {"width": f"var({_SIZE})", "height": "1px"},
            "vertical": {"width": "1px", "height": f"var({_SIZE})"},
        },
        "size": {
            "1": unchecked({_SIZE: tokens.space[4]}),
            "2": unchecked({_SIZE: tokens.space[6]}),
            "3": unchecked({_SIZE: tokens.space[9]}),
            "4": unchecked({_SIZE: "100%"}),
        },
        "color_scheme": {"true": {"background_color": tokens.accent.a[6]}},
    },
    "defaults": {"orientation": "horizontal"},
}
