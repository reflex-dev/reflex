import reflex as rx


def navbar():
    return rx.box(
        rx.hstack(
            rx.hstack(
                rx.image(src="/nba.png", width="50px"),
                rx.heading("NBA Data", size="8"),
                rx.flex(
                    rx.badge("2015-2016 Season"),
                ),
                align="center",
            ),
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        "Menu", color="white", size="3", radius="medium", px=4, py=2
                    ),
                ),
                rx.menu.content(
                    rx.menu.item("Graph"),
                    rx.menu.separator(),
                    rx.menu.item(
                        rx.link(
                            rx.hstack(rx.text("20Dataset"), rx.icon(tag="download")),
                            href="https://media.geeksforgeeks.org/wp-content/uploads/nba.csv",
                        ),
                    ),
                ),
            ),
            justify="between",
            border_bottom="0.2em solid #F0F0F0",
            padding_inline_start="2em",
            padding_inline_end="2em",
            padding_top="1em",
            padding_bottom="1em",
            bg="rgba(255,255,255, 0.97)",
        ),
        position="fixed",
        width="100%",
        top="0px",
        z_index="500",
    )
