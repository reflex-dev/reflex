"""Shared spacing and typography for the documentation overview."""

import reflex as rx

CONTAINER = "mx-auto w-full max-w-[1176px] px-4 sm:px-8"
SECTION = f"{CONTAINER} py-12 sm:py-16"
FOCUS = (
    "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
)
HEADING = "font-heading text-3xl font-light leading-[1.12] tracking-[-0.035em] text-foreground sm:text-4xl"


def section_heading(title: str, description: str) -> rx.Component:
    """Introduce a documentation group with its purpose.

    Args:
        title: Name of the documentation group.
        description: Supporting explanation of the guides.

    Returns:
        A responsive section introduction.
    """
    return rx.el.div(
        rx.el.h2(title, class_name=HEADING),
        rx.el.p(
            description,
            class_name="max-w-lg text-base font-normal leading-7 text-muted-foreground",
        ),
        class_name="mb-8 flex flex-col gap-4 sm:mb-10 lg:flex-row lg:items-end lg:justify-between lg:gap-12",
    )
