"""The look of a popover: a panel beside what opens it."""

from __future__ import annotations

from typing import Any

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, unchecked
from reflex_components_ui.styles.popup import POPUP, placements

_PADDING = "--popover-content-padding"


def _size(padding: str, radius: str) -> dict[str, Any]:
    """Make the styles of a popover of one size.

    Args:
        padding: The room around what the popover holds.
        radius: The radius of its corners.

    Returns:
        The styles.
    """
    return {_PADDING: padding, "border_radius": radius}


POPOVER_CONTENT: ComponentStyles = {
    "base": unchecked({
        **POPUP,
        # The text of the page around it, not the one of a native popover.
        "color": "inherit",
        "background_color": tokens.color.panel_solid,
        "box_shadow": tokens.shadow[5],
        # At least as wide as what opens it, and no wider than the page.
        "min_width": "anchor-size(width)",
        "max_width": "min(480px, calc(100vw - 20px))",
        "outline_style": "none",
        "overflow": "auto",
        "--inset-padding-top": f"var({_PADDING})",
        "--inset-padding-right": f"var({_PADDING})",
        "--inset-padding-bottom": f"var({_PADDING})",
        "--inset-padding-left": f"var({_PADDING})",
        "padding": f"var({_PADDING})",
        "box_sizing": "border-box",
    }),
    "variants": {
        "size": {
            "1": unchecked(_size(tokens.space[3], tokens.radius[4])),
            "2": unchecked(_size(tokens.space[4], tokens.radius[4])),
            "3": unchecked(_size(tokens.space[5], tokens.radius[5])),
            "4": unchecked(_size(tokens.space[6], tokens.radius[5])),
        },
    },
    "defaults": {"size": "2", "side": "bottom", "align": "start"},
    "compound": placements("8px"),
}
