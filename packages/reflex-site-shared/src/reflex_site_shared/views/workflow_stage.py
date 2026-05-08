"""Workflow stage visuals (animated arrows) used in marketing mega-menus."""

from typing import Literal
from urllib.parse import quote

import reflex_components_internal as ui

import reflex as rx

ArrowSize = Literal["large", "small"]

_ARROW_VARIANTS: dict[ArrowSize, tuple[int, int]] = {
    "large": (26, 136),
    "small": (24, 126),
}

# Total animated groups; delay per group = duration / _ARROW_SWEEP_GROUPS so
# the four sweeps chain end-to-end across one animation cycle.
_ARROW_SWEEP_GROUPS = 4


def _arrow_paths(count: int) -> str:
    return "".join(
        f'<path d="M{3 + i * 5} 1L{7 + i * 5} 5L{3 + i * 5} 9" '
        f'stroke="currentColor" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
        for i in range(count)
    )


def _arrow_row_svg(count: int, width: int, *, inline_style: bool = False) -> str:
    style_attr = ' style="display:block;height:100%;width:auto"' if inline_style else ""
    return (
        f'<svg width="{width}" height="10" viewBox="0 0 {width} 10" '
        f'fill="none" xmlns="http://www.w3.org/2000/svg"{style_attr}>'
        f"{_arrow_paths(count)}</svg>"
    )


def _arrow_mask_data_url(count: int, width: int) -> str:
    # Percent-encode the SVG body so Firefox/Safari accept the data URL
    # in mask-image; raw `<`, `>`, and spaces are not reliably parsed.
    encoded = quote(_arrow_row_svg(count, width), safe="")
    return f'url("data:image/svg+xml,{encoded}")'


def workflow_stage_image(
    wrapper_class_name: str = "",
    size: ArrowSize = "large",
    sweep_index: int = 0,
) -> rx.Component:
    """Animated arrow strip with a phased sweep highlight.

    Returns:
        The component.
    """
    count, width = _ARROW_VARIANTS[size]
    mask_url = _arrow_mask_data_url(count, width)

    return rx.el.div(
        rx.html(
            _arrow_row_svg(count, width, inline_style=True),
            class_name="block h-full w-auto text-secondary-7",
        ),
        rx.el.div(
            rx.el.div(
                class_name="absolute -top-[7px] left-0 h-[24px] w-1/2 bg-primary-9 blur-[8px] animate-arrow-sweep",
                style={
                    "animationDelay": (
                        f"calc(var(--arrow-sweep-duration) / {_ARROW_SWEEP_GROUPS} "
                        f"* {sweep_index})"
                    ),
                },
            ),
            class_name=ui.cn(
                "absolute inset-0 pointer-events-none overflow-hidden",
                "[mask-repeat:no-repeat] [-webkit-mask-repeat:no-repeat]",
                "[mask-size:100%_100%] [-webkit-mask-size:100%_100%]",
                "[mask-position:left_center] [-webkit-mask-position:left_center]",
            ),
            style={
                "maskImage": mask_url,
                "WebkitMaskImage": mask_url,
            },
        ),
        class_name=ui.cn(
            "relative flex h-[10px] w-auto shrink-0 items-center justify-start overflow-hidden max-lg:hidden",
            wrapper_class_name,
        ),
        custom_attrs={"aria-hidden": "true"},
    )


def workflow_stage_row(
    title: str,
    *,
    left: rx.Component | None = None,
    right: rx.Component | None = None,
) -> rx.Component:
    """Three-column row: optional left graphic, centered title, optional right graphic.

    Returns:
        The component.
    """
    left_cell = (
        rx.el.div(
            left,
            class_name="pointer-events-none flex min-w-0 items-center justify-self-start px-2",
        )
        if left is not None
        else rx.el.div(class_name="min-w-0 justify-self-start")
    )
    right_cell = (
        rx.el.div(
            right,
            class_name="pointer-events-none flex min-w-0 items-center justify-self-end px-2",
        )
        if right is not None
        else rx.el.div(class_name="min-w-0 justify-self-end")
    )
    return rx.el.div(
        left_cell,
        rx.el.span(title, class_name="shrink-0 justify-self-center text-center"),
        right_cell,
        class_name="grid h-12 w-full shrink-0 grid-cols-[1fr_auto_1fr] items-center bg-secondary-1 font-mono text-xs font-[415] uppercase text-secondary-12 lg:border-b border-secondary-4",
    )
