"""The home page of the app."""

import reflex as rx

from ..styles import *


def home_page() -> rx.Component:
    """The UI for the home page.

    Returns:
        rx.Component: The UI for the home page.
    """
    return rx.chakra.box(
        rx.chakra.vstack(
            rx.chakra.heading(
                "Welcome to Reflex! 👋",
                font_size="3em",
            ),
            rx.chakra.text(
                "Reflex is an open-source app framework built specifically to allow you to build web apps in pure python. 👈 Select a demo from the sidebar to see some examples of what Reflex can do!",
            ),
            rx.chakra.heading(
                "Things to check out:",
                font_size="2em",
            ),
            rx.chakra.unordered_list(
                rx.chakra.list_item(
                    "Take a look at ",
                    rx.chakra.link(
                        "reflex.dev",
                        href="https://reflex.dev",
                        color="rgb(107,99,246)",
                    ),
                ),
                rx.chakra.list_item(
                    "Check out our ",
                    rx.chakra.link(
                        "docs",
                        href="https://reflex.dev/docs/getting-started/introduction/",
                        color="rgb(107,99,246)",
                    ),
                ),
                rx.chakra.list_item(
                    "Ask a question in our ",
                    rx.chakra.link(
                        "community",
                        href="https://discord.gg/T5WSbC2YtQ",
                        color="rgb(107,99,246)",
                    ),
                ),
            ),
            style=template_content_style,
        ),
        style=template_page_style,
    )
