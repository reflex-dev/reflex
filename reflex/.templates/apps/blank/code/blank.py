"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    ...


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex ✨", size="9"),
            rx.text(
                "You can edit this page by modifying the code in the file below.",
            ),
            rx.text("Need help? 🤔 Check out the documentation."),
            rx.code(f"{config.app_name}/{config.app_name}.py"),
            rx.text("Happy coding! 🎉"),
            rx.card(
                rx.link(
                    rx.flex(
                        rx.avatar(src="https://reflex.dev/reflex_banner.png"),
                        rx.box(
                            rx.heading("Quick Start 🚀"),
                            rx.text("Get started with Reflex before your coffee ☕"),
                        ),
                        spacing="3",
                    ),
                    href="https://reflex.dev/docs/getting-started/introduction/",
                    target="_blank",
                    underline="none",
                ),
                as_child=True,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
        rx.logo(),
    )


app = rx.App()
app.add_page(index)
