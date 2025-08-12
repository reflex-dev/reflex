"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from .views.navbar import navbar
from .views.table import table
from .views.stats import stats
import reflex as rx


def index() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.flex(
            rx.box(table(), width=["100%", "100%", "100%", "50%"]),
            stats(),
            spacing="9",
            width="100%",
            flex_direction=["column", "column", "column", "row"],
        ),
        width="100%",
        spacing="6",
        padding_x=["1.5em", "1.5em", "3em"],
        padding_y=["1em", "1em", "2em"],
    )


# base_stylesheets = [
#     "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
# ]

# font_default = "Inter"

# base_style = {
#     "font_family": font_default,
#     rx.text: {
#         "font_family": font_default,
#     },
#     rx.heading: {
#         "font_family": font_default,
#     },
#     rx.link: {
#         "font_family": font_default,
#     },
#     rx.input: {
#         "font_family": font_default,
#     },
#     rx.button: {
#         "font_family": font_default,
#     },
# }
app = rx.App(
    # style=base_style, stylesheets=base_stylesheets,
    theme=rx.theme(
        appearance="light", has_background=True, radius="large", accent_color="orange"
    ),
)
app.add_page(
    index,
    title="NBA Data App",
    description="Generate personalized sales emails.",
)
