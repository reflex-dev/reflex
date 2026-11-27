"""The look of a block quotation: text with a rule beside it."""

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.text import TEXT_BASE
from reflex_components_ui.styles.typography import (
    COLOR,
    COLOR_HIGH_CONTRAST,
    SIZE,
    WEIGHT,
)

BLOCKQUOTE: ComponentStyles = {
    "base": {
        **TEXT_BASE,
        "box_sizing": "border-box",
        "border_left_width": f"max({tokens.space[1]}, 0.25em)",
        "border_left_style": "solid",
        "border_left_color": tokens.accent.a[6],
        "padding_left": f"min({tokens.space[5]}, max({tokens.space[3]}, 0.5em))",
    },
    "variants": {
        "size": SIZE,
        "weight": WEIGHT,
        **COLOR,
    },
    "compound": [COLOR_HIGH_CONTRAST],
}
