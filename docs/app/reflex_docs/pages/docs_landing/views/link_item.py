import reflex as rx
import reflex_components_internal as ui


def faded_borders() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            class_name="absolute bottom-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-border-subtle"
        ),
        rx.el.div(
            class_name="absolute -top-px -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-border-subtle"
        ),
        rx.el.div(
            class_name="absolute bottom-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-border-subtle"
        ),
        rx.el.div(
            class_name="absolute right-0 -top-24 h-24 w-px bg-gradient-to-b from-transparent to-current text-border-subtle"
        ),
    )


def link_item(
    icon: str, title: str, description: str, href: str, has_padding_left: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-6 shrink-0 group-hover:text-primary-hover group-hover:dark:text-muted-foreground",
                stroke_width=1.5,
            ),
            rx.el.span(
                title,
                class_name="text-foreground text-xl font-[575] group-hover:text-primary-hover group-hover:dark:text-muted-foreground",
            ),
            ui.icon(
                "ArrowRight01Icon",
                class_name="size-4 ml-auto group-hover:text-primary-hover group-hover:dark:text-muted-foreground shrink-0",
            ),
            class_name="flex flex-row gap-3 items-center max-lg:text-start",
        ),
        rx.el.span(
            description,
            class_name="text-muted-foreground text-sm font-[475] text-start",
        ),
        rx.el.a(
            to=href,
            aria_label=title,
            class_name="absolute inset-0 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary",
        ),
        class_name=ui.cn(
            "flex flex-col gap-2 pr-8 py-8 group border-r border-b border-border-subtle relative max-lg:p-6 hover:bg-[linear-gradient(243deg,var(--muted)_0%,var(--background)_100%)]",
            "lg:pl-8 pl-6" if has_padding_left else "",
        ),
    )
