"""App styling."""

import reflex as rx
import reflex_ui_shared.styles.fonts as fonts
from reflex_ui_shared.styles.colors import c_color

font_weights = {
    "bold": "800",
    "heading": "700",
    "subheading": "600",
    "section": "600",
}


def get_code_style(color: str):
    """Get code style.

    Returns:
        The component.
    """
    return {
        "color": c_color(color, 9),  # type: ignore[arg-type]
        "border_radius": "4px",
        "border": f"1px solid {c_color(color, 4)}",  # type: ignore[arg-type]
        "background": c_color(color, 3),  # type: ignore[arg-type]
        **fonts.code,
        "line_height": "1.5",
    }


def get_code_style_rdx(color: str):  # type: ignore[reportArgumentType]
    """Get code style rdx.

    Returns:
        The component.
    """
    return {
        "color": rx.color(color, 11),  # type: ignore[reportArgumentType]
        "border_radius": "0.25rem",
        "border": f"1px solid {rx.color(color, 5)}",  # type: ignore[reportArgumentType]
        "background": rx.color(color, 3),  # type: ignore[reportArgumentType]
    }


cell_style = {
    **fonts.small,
    "color": c_color("slate", 11),
    "line_height": "1.5",
}


# General styles.
SANS = "Instrument Sans"
BOLD_WEIGHT = font_weights["bold"]

DOC_BORDER_RADIUS = "6px"

# The base application style.
BASE_STYLE = {
    "background_color": "var(--c-slate-1)",
    "::selection": {
        "background_color": rx.color("accent", 5, True),
    },
    "font_family": SANS,
    rx.heading: {
        "font_family": SANS,
    },
    rx.divider: {"margin_bottom": "1em", "margin_top": "0.5em"},
    rx.vstack: {"align_items": "center"},
    rx.hstack: {"align_items": "center"},
    rx.markdown: {
        "background": "transparent",
    },
}

# Fonts to include.
STYLESHEETS = [
    "fonts.css",
    "custom-colors.css",
    "tailwind-theme.css",
]
