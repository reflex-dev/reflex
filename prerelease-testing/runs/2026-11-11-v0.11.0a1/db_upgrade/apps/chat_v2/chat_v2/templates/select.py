import reflex as rx


def select_menu(
    icon: str,
    placeholder: str,
):
    return rx.hstack(
        rx.hstack(
            rx.icon(tag=icon, size=18),
            rx.text(placeholder, weight="medium", size="1"),
            align="center",
            width="100px",
            spacing="1",
        ),
        rx.icon(tag="chevron-down", size=18),
        color=rx.color("slate", 11),
        display="flex",
        align="center",
        justify="between",
        background=rx.color_mode_cond(
            rx.color("indigo", 1),
            rx.color("indigo", 2),
        ),
        border=rx.color_mode_cond(
            f"2px solid {rx.color('indigo', 3)}",
            f"1px solid {rx.color('slate', 7, True)}",
        ),
        box_shadow=rx.color_mode_cond("0px 1px 3px rgba(25, 33, 61, 0.1)", "none"),
        border_radius="8px",
        padding="12px",
    )
