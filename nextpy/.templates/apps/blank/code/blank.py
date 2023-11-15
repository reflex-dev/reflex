"""Welcome to Nextpy! This file outlines the steps to create a basic app."""
from xtconfig import config

import nextpy as xt

docs_url = "https://docs.dotagent.dev/nextpy/getting-started/introduction"
filename = f"{config.app_name}/{config.app_name}.py"


class State(xt.State):
    """The app state."""

    pass


def index() -> xt.Component:
    return xt.fragment(
        xt.color_mode_button(xt.color_mode_icon(), float="right"),
        xt.vstack(
            xt.heading("Welcome to Nextpy!", font_size="2em"),
            xt.box("Get started by editing ", xt.code(filename, font_size="1em")),
            xt.link(
                "Check out our docs!",
                href=docs_url,
                border="0.1em solid",
                padding="0.5em",
                border_radius="0.5em",
                _hover={
                    "color": xt.color_mode_cond(
                        light="rgb(107,99,246)",
                        dark="rgb(179, 175, 255)",
                    )
                },
            ),
            spacing="1.5em",
            font_size="2em",
            padding_top="10%",
        ),
    )


# Add state and page to the app.
app = xt.App()
app.add_page(index)
app.compile()
