"""The home page of the app."""
import nextpy as xt

from ..styles import *


def home_page() -> xt.Component:
    """The UI for the home page.

    Returns:
        xt.Component: The UI for the home page.
    """
    return xt.box(
        xt.vstack(
            xt.heading(
                "Welcome to Nextpy! 👋",
                font_size="3em",
            ),
            xt.text(
                "Nextpy is an open-source app framework built specifically to allow you to build web apps in pure python. 👈 Select a demo from the sidebar to see some examples of what Nextpy can do!",
            ),
            xt.heading(
                "Things to check out:",
                font_size="2em",
            ),
            xt.unordered_list(
                xt.list_item(
                    "Take a look at ",
                    xt.link(
                        "dotagent.dev",
                        href="https://dotagent.dev",
                        color="rgb(107,99,246)",
                    ),
                ),
                xt.list_item(
                    "Check out our ",
                    xt.link(
                        "docs",
                        href="https://docs.dotagent.dev/nextpy/getting-started/introduction/",
                        color="rgb(107,99,246)",
                    ),
                ),
                xt.list_item(
                    "Ask a question in our ",
                    xt.link(
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
