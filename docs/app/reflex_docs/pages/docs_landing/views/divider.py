import reflex as rx
import reflex_components_internal as ui


def divider(class_name: str = "") -> rx.Component:
    return rx.el.div(
        class_name=ui.cn(
            "mx-auto h-px w-full max-w-[1176px] bg-border-subtle",
            class_name,
        ),
    )
