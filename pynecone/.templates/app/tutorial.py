"""Welcome to Pynecone! This file outlines the steps to create a basic app."""
import pcconfig
import pynecone as pc

docs_url = "https://pynecone.io/docs/getting-started/introduction"
filename = f"{pcconfig.APP_NAME}/{pcconfig.APP_NAME}.py"


class State(pc.State):
    """The app state."""
    pass


def index():
    return pc.center(
        pc.vstack(
            pc.heading("Welcome to Pynecone!"),
            pc.box("Get started by editing ", pc.code(filename)),
            pc.link(
                "Check out our docs!",
                href=docs_url,
                border="0.1em solid",
                padding="0.5em",
                border_radius="0.5em"
            ),
        ),
        padding="5em"
    )


# Add state and page to the app.
app = pc.App(state=State)
app.add_page(index)
app.compile()

