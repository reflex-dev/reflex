"""Theme-aware versions of the documentation illustrations."""

from pathlib import Path

import reflex as rx


def artwork(name: str, class_name: str = "") -> rx.Component:
    """Inline a trusted local SVG so its colors follow the page theme."""
    return rx.html(
        Path(__file__).with_name(f"{name}.svg").read_text(encoding="utf-8"),
        aria_hidden=True,
        class_name=f"pointer-events-none [&_svg]:h-auto [&_svg]:w-full {class_name}",
    )
