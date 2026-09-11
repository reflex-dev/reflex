import reflex as rx


def layout(*children, size="2", **props):
    return rx.container(
        rx.vstack(
            *children,
            **props,
        ),
        stack_children_full_width=True,
        size=size,
    )
