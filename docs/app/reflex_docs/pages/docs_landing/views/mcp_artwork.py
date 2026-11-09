"""Theme-aware MCP diagram for the docs landing page."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.icons import get_icon


def _node(
    label: str, graphic: rx.Component, left: float, top: float, width: float
) -> rx.Component:
    """Render a diagram node at its percentage position.

    Args:
        label: Caption below the graphic.
        graphic: Icon or logo group.
        left: Horizontal position as a percentage.
        top: Vertical position as a percentage.
        width: Node width as a percentage.

    Returns:
        A positioned diagram node.
    """
    return rx.el.div(
        graphic,
        rx.el.span(label),
        class_name="absolute flex flex-col items-center justify-center gap-[2cqw] rounded-[3cqw] border border-border bg-background text-foreground text-[3cqw] leading-none",
        style={
            "left": f"{left}%",
            "top": f"{top}%",
            "width": f"{width}%",
            "height": "30%",
        },
    )


def mcp_artwork() -> rx.Component:
    """Render assistant logos connected to Reflex MCP and its resources.

    Returns:
        A responsive, decorative MCP diagram.
    """
    return rx.el.div(
        rx.html(
            '<svg viewBox="0 0 360 220" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M113 110H148M212 110H234Q244 110 244 100V65Q244 55 254 55H270M244 100V155Q244 165 254 165H270" '
            'stroke="var(--ai-accent)" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            class_name="absolute inset-0 [&_svg]:size-full",
        ),
        _node(
            "AI assistant",
            rx.el.div(
                *[
                    get_icon(name, class_name="size-[5cqw] [&_svg]:size-full")
                    for name in ("claude", "openai", "cursor")
                ],
                class_name="flex items-center gap-[2cqw] text-muted-foreground",
            ),
            6,
            35,
            26,
        ),
        _node(
            "MCP",
            rx.image(src=rx.asset("favicon.svg"), alt="", class_name="size-[8cqw]"),
            41,
            35,
            18,
        ),
        _node(
            "Docs",
            ui.icon(
                "File02Icon", size="7cqw", color="var(--ai-accent)", stroke_width=1.5
            ),
            74,
            12,
            20,
        ),
        _node(
            "Components",
            ui.icon(
                "DashboardSquare01Icon",
                size="7cqw",
                color="var(--ai-accent)",
                stroke_width=1.5,
            ),
            72,
            62,
            25,
        ),
        class_name="pointer-events-none relative aspect-[360/220] w-full @container",
        aria_hidden=True,
    )
