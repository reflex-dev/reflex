"""Collapsible accordion box used by alert and video blocks."""

from collections.abc import Sequence

from reflex_base.constants.colors import ColorType

import reflex as rx


def collapsible_box(
    trigger_children: Sequence[rx.Component],
    body: rx.Component,
    color: ColorType,
    *,
    item_border_radius: str = "12px",
    background_shade: int = 3,
    background_override: str | None = None,
    border_override: str | None = None,
) -> rx.Component:
    """Collapsible accordion wrapper shared by alert and video directives.

    Returns:
        The component.
    """
    bg = background_override or f"{rx.color(color, background_shade)}"
    border_color = border_override or f"{rx.color(color, 4)}"
    return rx.box(
        rx.accordion.root(
            rx.accordion.item(
                rx.accordion.header(
                    rx.accordion.trigger(
                        rx.hstack(
                            *trigger_children,
                            rx.spacer(),
                            rx.accordion.icon(color=f"{rx.color(color, 11)}"),
                            align_items="center",
                            justify_content="left",
                            text_align="left",
                            spacing="2",
                            width="100%",
                        ),
                        padding="0px",
                        color=f"{rx.color(color, 11)} !important",
                        background_color="transparent !important",
                        border_radius="12px",
                        _hover={},
                    ),
                ),
                body,
                border_radius=item_border_radius,
                padding=["16px", "24px"],
                background_color=bg,
                border="none",
            ),
            background="transparent !important",
            border_radius="12px",
            box_shadow="none !important",
            collapsible=True,
            width="100%",
        ),
        border=f"1px solid {border_color}",
        border_radius="12px",
        background_color=f"{bg} !important",
        width="100%",
        margin_bottom="16px",
        margin_top="16px",
        overflow="hidden",
    )
