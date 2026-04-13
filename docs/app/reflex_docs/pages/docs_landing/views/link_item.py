import reflex as rx
import reflex_ui as ui


def faded_borders() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            class_name="absolute bottom-0 -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
        rx.el.div(
            class_name="absolute -top-px -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
        rx.el.div(
            class_name="absolute bottom-0 -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
        rx.el.div(
            class_name="absolute right-0 -top-24 h-24 w-px bg-gradient-to-b from-transparent to-current text-m-slate-4 dark:text-m-slate-10"
        ),
    )


def link_item(
    icon: str, title: str, description: str, href: str, has_padding_left: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            ui.icon(
                icon,
                class_name="size-6 shrink-0 group-hover:text-primary-10 group-hover:dark:text-m-slate-5",
                stroke_width=1.5,
            ),
            rx.el.span(
                title,
                class_name="text-m-slate-12 dark:text-m-slate-3 text-xl font-[575] group-hover:text-primary-10 group-hover:dark:text-m-slate-5",
            ),
            ui.icon(
                "ArrowRight01Icon",
                class_name="size-4 ml-auto group-hover:text-primary-10 group-hover:dark:text-m-slate-5 shrink-0",
            ),
            class_name="flex flex-row gap-3 items-center max-lg:text-start",
        ),
        rx.el.span(
            description,
            class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475] text-start",
        ),
        rx.el.a(to=href, class_name="absolute inset-0"),
        class_name=ui.cn(
            "flex flex-col gap-2 pr-8 py-8 group border-r border-b border-m-slate-4 dark:border-m-slate-10 relative max-lg:p-6 hover:bg-[linear-gradient(243deg,var(--m-slate-2,#F6F7F9)_0%,var(--m-slate-1,#FCFCFD)_100%)] dark:hover:bg-[linear-gradient(243deg,var(--m-slate-11,#1D2025)_0%,var(--m-slate-12,#151618)_63.63%)]",
            "lg:pl-8 pl-6" if has_padding_left else "",
        ),
    )
