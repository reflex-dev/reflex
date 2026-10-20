import reflex as rx
import reflex_components_internal as ui

from reflex_docs.pages.docs_landing.views.layout import FOCUS


def faded_borders() -> rx.Component:
    """Keep the former decoration hook without drawing beyond the content frame.

    Returns:
        An empty fragment for existing section callers.
    """
    return rx.fragment()


def link_item(
    icon: str, title: str, description: str, href: str, has_padding_left: bool = False
) -> rx.Component:
    """Render a guide as one readable, keyboard-accessible card.

    Args:
        icon: Shared icon name.
        title: Guide name.
        description: Guide summary.
        href: Existing destination.
        has_padding_left: Retained for callers; all cards now use equal insets.

    Returns:
        A single native navigation target.
    """
    return rx.el.a(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-5 shrink-0 text-foreground",
                stroke_width=1.5,
                aria_hidden=True,
            ),
            rx.el.h3(
                title,
                class_name="min-w-0 font-heading text-2xl font-normal leading-7 tracking-[-0.025em] text-foreground",
            ),
            ui.icon(
                "ArrowRight01Icon",
                class_name="ml-auto mt-1 size-4 shrink-0 text-muted-foreground",
                aria_hidden=True,
            ),
            class_name="flex items-start gap-3",
        ),
        rx.el.p(
            description,
            class_name="max-w-xl text-sm font-normal leading-6 text-muted-foreground",
        ),
        to=href,
        aria_label=title,
        class_name=f"group flex min-w-0 flex-col gap-4 rounded-[20px] bg-muted p-6 text-left transition-colors hover:bg-accent-hover motion-reduce:transition-none sm:p-8 {FOCUS}",
    )
