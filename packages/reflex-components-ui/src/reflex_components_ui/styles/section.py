"""The look of a section of a page."""

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles

SECTION: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "flex_shrink": "0",
    },
    "variants": {
        "size": {
            "1": {"padding_top": tokens.space[5], "padding_bottom": tokens.space[5]},
            "2": {"padding_top": tokens.space[7], "padding_bottom": tokens.space[7]},
            "3": {"padding_top": tokens.space[9], "padding_bottom": tokens.space[9]},
        },
    },
}
