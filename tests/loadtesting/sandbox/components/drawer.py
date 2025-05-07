import reflex as rx
from reflex.components.radix.themes.base import LiteralAccentColor
from sandbox.states.queries import QueryAPI


def render_data(data: tuple[str, str]):
    return rx.vstack(
        rx.text(data[0], weight="bold"),
        rx.input(
            value=data[1],
            width="100%",
            on_change=lambda value: QueryAPI.update_data(value, data),
        ),
        width="100%",
        spacing="2",
    )


@rx.memo
def render_drawer_buttons(
    name: str, color: LiteralAccentColor, on_click: rx.EventHandler
):
    return rx.badge(
        rx.text(name, width="100%", text_align="center"),
        color_scheme=color,
        on_click=on_click,
        variant="surface",
        padding="0.75em 1.25em",
        width="100%",
        cursor="pointer",
    )


def render_drawer():
    return rx.drawer.root(
        rx.drawer.overlay(z_index="5"),
        rx.drawer.portal(
            rx.drawer.content(
                rx.vstack(
                    rx.foreach(QueryAPI.selected_entry, render_data),
                    rx.vstack(
                        render_drawer_buttons(
                            name="Commit",
                            color="grass",
                            on_click=QueryAPI.commit_changes,
                        ),
                        render_drawer_buttons(
                            name="Close", color="ruby", on_click=QueryAPI.delta_drawer
                        ),
                        padding="1em 0.5em",
                        width="inherit",
                    ),
                    background_color=rx.color_mode_cond("#faf9fb", "#1a181a"),
                    height="100%",
                    width="100%",
                    padding="1.25em",
                ),
                top="auto",
                left="auto",
                height="100%",
                width="25em",
                on_interact_outside=QueryAPI.delta_drawer(),
            ),
        ),
        direction="right",
        open=QueryAPI.is_open,
        on_open_change=QueryAPI.set_is_open,
    )
