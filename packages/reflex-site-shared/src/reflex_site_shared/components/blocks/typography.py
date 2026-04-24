"""Typography blocks for doc pages."""

import reflex as rx
from reflex_site_shared.styles import fonts


def definition(title: str, *children) -> rx.Component:
    """Create a definition for a doc page.

    Args:
        title: The title of the definition.
        children: The children to display.

    Returns:
        The styled definition.
    """
    return rx.vstack(
        rx.heading(
            title,
            as_="h3",
            font_size="1em",
            font_weight="bold",
            color=rx.color("mauve", 12),
        ),
        *children,
        color=rx.color("mauve", 10),
        padding="1em",
        border=f"1px solid {rx.color('mauve', 4)}",
        background_color=rx.color("mauve", 2),
        border_radius="8px",
        _hover={
            "border": f"1px solid {rx.color('mauve', 5)}",
            "background_color": rx.color("mauve", 3),
        },
        align_items="start",
    )


@rx.memo
def text_comp(text: rx.Var[str]) -> rx.Component:
    """Text comp.

    Returns:
        The component.
    """
    return rx.text(text, class_name="font-normal text-secondary-11 mb-4 leading-7")


@rx.memo
def text_comp_2(text: rx.Var[str]) -> rx.Component:
    """Text comp 2.

    Returns:
        The component.
    """
    return rx.text(
        text,
        class_name="font-normal text-secondary-11 max-w-[80%] mb-10",
    )


@rx.memo
def list_comp(text: rx.Var[str]) -> rx.Component:
    """List comp.

    Returns:
        The component.
    """
    return rx.list_item(text, class_name="font-normal text-secondary-11 mb-4")


@rx.memo
def unordered_list_comp(items: rx.Var[list[str]]) -> rx.Component:
    """Unordered list comp.

    Returns:
        The component.
    """
    return rx.list.unordered(items, class_name="mb-6")


@rx.memo
def ordered_list_comp(items: rx.Var[list[str]]) -> rx.Component:
    """Ordered list comp.

    Returns:
        The component.
    """
    return rx.list.ordered(items, class_name="mb-6")


@rx.memo
def code_comp(text: rx.Var[str]) -> rx.Component:
    """Code comp.

    Returns:
        The component.
    """
    return rx.code(text, class_name="code-style")


def doclink(text: str, href: str, **props) -> rx.Component:
    """Create a styled link for doc pages.

    Args:
        text: The text to display.
        href: The link to go to.
        props: Props to apply to the link.

    Returns:
        The styled link.
    """
    return rx.link(
        text,
        underline="always",
        href=href,
        **props,
        class_name="!text-m-slate-12 dark:!text-m-slate-3 !decoration-m-slate-12 dark:!decoration-m-slate-3",
    )


def doclink2(text: str, **props) -> rx.Component:
    """Create a styled link for doc pages.

    Args:
        text: The text to display.
        href: The link to go to.
        props: Props to apply to the link.

    Returns:
        The styled link.
    """
    return rx.link(
        text,
        underline="always",
        **props,
        style=fonts.base,
        class_name="!text-m-slate-12 dark:!text-m-slate-3 !decoration-m-slate-12 dark:!decoration-m-slate-3",
    )
