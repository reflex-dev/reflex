"""The look of a box that keeps the ratio of its width to its height."""

from reflex_components_ui.style import ComponentStyles

# The frame takes its height from a padding in proportion to its width, which
# the component sets: the content fills it.
ASPECT_RATIO_FRAME: ComponentStyles = {
    "base": {
        "position": "relative",
        "width": "100%",
    },
}

ASPECT_RATIO: ComponentStyles = {
    "base": {
        "position": "absolute",
        "top": "0",
        "right": "0",
        "bottom": "0",
        "left": "0",
    },
}
