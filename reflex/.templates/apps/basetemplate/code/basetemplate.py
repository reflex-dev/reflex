"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import reflex as rx
from .state import State
from .sidebar import sidebar
from .styles import *


def content():
    return rx.box(
        rx.vstack(
            rx.heading(
                "Dashboard",
                size="3em",
            ),
            rx.text(
                "Welcome to Reflex!",
            ),
            rx.text(
                "You can use this template to get started with Reflex.",
            ),
            width="100%",
            align_items="flex-start",
            height="90%",
            box_shadow="0px 0px 0px 1px rgba(84, 82, 95, 0.14)",
            border_radius=border_radius,
            padding="1em",
        ),
        height="100vh",
        width="100%",
        padding_top="5em",
        padding_x="2em",
    )


def menu_button():
    return rx.box(
        rx.menu(
            rx.menu_button(
                rx.icon(
                    tag="hamburger",
                    size="4em",
                    color=text_color,
                ),
            ),
            rx.menu_list(
                rx.menu_item("Home"),
                rx.menu_divider(),
                rx.menu_item("About"),
                rx.menu_item("Contact"),
            ),
        ),
        position="fixed",
        right="1.5em",
        top="1.5em",
        z_index="500",
    )


def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        content(),
        rx.spacer(),
        menu_button(),
        align_items="flex-start",
    )


# Add state and page to the app.
app = rx.App(style=base_style)
app.add_page(index)
app.compile()
