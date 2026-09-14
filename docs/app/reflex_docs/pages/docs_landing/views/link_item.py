import reflex as rx
import reflex_components_internal as ui


def faded_borders() -> rx.Component:
    return rx.fragment()


def link_item(
    icon: str, title: str, description: str, href: str, has_padding_left: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-6 shrink-0 group-hover:text-primary-10 group-hover:dark:text-secondary-11",
                stroke_width=1.5,
            ),
            rx.el.span(
                title,
                class_name="text-secondary-12 text-xl font-book tracking-tight group-hover:text-primary-10 group-hover:dark:text-secondary-11",
            ),
            ui.icon(
                "ArrowRight01Icon",
                class_name="size-4 ml-auto group-hover:text-primary-10 group-hover:dark:text-secondary-11 shrink-0",
            ),
            class_name="flex flex-row gap-3 items-center max-lg:text-start",
        ),
        rx.el.span(
            description,
            class_name="text-secondary-11 text-sm font-normal text-start",
        ),
        rx.el.a(
            to=href,
            aria_label=title,
            class_name="absolute inset-0 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary-9",
        ),
        class_name=ui.cn(
            "flex flex-col gap-2 pr-8 py-8 group border-b border-border-subtle relative max-lg:p-6 hover:bg-accent transition-colors motion-reduce:transition-none",
            "lg:pl-8 pl-6" if has_padding_left else "",
        ),
    )
