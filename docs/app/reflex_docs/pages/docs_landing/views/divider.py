import reflex as rx
import reflex_ui as ui


def divider(class_name: str = "") -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="absolute top-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
        rx.el.div(
            class_name="absolute top-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
        class_name=ui.cn(
            "w-full h-[1px] bg-m-slate-4 dark:bg-m-slate-10 relative max-w-(--docs-layout-max-width) mx-auto",
            class_name,
        ),
    )
