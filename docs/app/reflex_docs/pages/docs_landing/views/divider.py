import reflex as rx
import reflex_components_internal as ui


def divider(class_name: str = "") -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="absolute top-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-border-subtle"
        ),
        rx.el.div(
            class_name="absolute top-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-border-subtle"
        ),
        class_name=ui.cn(
            "w-full h-[1px] bg-border-subtle relative max-w-(--landing-layout-max-width) mx-auto",
            class_name,
        ),
    )
