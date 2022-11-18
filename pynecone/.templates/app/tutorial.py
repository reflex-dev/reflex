"""Welcome to Pynecone! This file outlines the steps to create a basic app."""

# Import pynecone.
import pcconfig

import pynecone as pc

docs_url = "https://pynecone.io/docs/getting-started/introduction"
title = "Welcome to Pynecone!"
filename = f"{pcconfig.APP_NAME}/{pcconfig.APP_NAME}.py"


class State(pc.State):
    """The app state."""

    # The colors to cycle through.
    colors = ["black", "red", "orange", "yellow", "green", "blue", "purple"]

    # The index of the current color.
    index = 0

    def next_color(self):
        """Cycle to the next color."""
        self.index = (self.index + 1) % len(self.colors)

    @pc.var
    def color(self):
        return self.colors[self.index]


# Define views.
def welcome_text():
    return pc.heading(
        title,
        font_size="2.5em",
        on_click=State.next_color,
        color=State.color,
        _hover={"cursor": "pointer"},
    )


def instructions():
    return pc.box(
        "Get started by editing ",
        pc.code(
            filename,
            font_size="0.8em",
        ),
    )


def doclink():
    return pc.link(
        "Check out our docs!",
        href=docs_url,
        border="0.1em solid",
        padding="0.5em",
        _hover={
            "border_color": State.color,
            "color": State.color,
        },
    )


def index():
    return pc.container(
        pc.vstack(
            welcome_text(),
            instructions(),
            doclink(),
            spacing="2em",
        ),
        padding_y="5em",
        font_size="2em",
        text_align="center",
        height="100vh",
    )


# Add state and page to the app.
app = pc.App(state=State)
app.add_page(index, title=title)
app.compile()
