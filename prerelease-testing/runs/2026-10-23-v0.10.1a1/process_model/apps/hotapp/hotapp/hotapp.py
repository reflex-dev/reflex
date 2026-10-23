"""Hot-reload QA app (#7113): the driver edits this file, helper.py and rxconfig.py while `reflex run` runs."""

import os

import reflex as rx

from hotapp.helper import describe
from rxconfig import config

if os.environ.get("EXPECT_VENV"):  # venv guard
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

APP_VERSION = "v1"


class State(rx.State):
    """The app state."""

    count: int = 0
    label: str = ""
    pid: int = 0

    @rx.event
    def on_load(self):
        self.pid = os.getpid()
        self.label = describe()

    @rx.event
    def bump(self):
        self.count += 1
        self.label = f"{APP_VERSION} {describe()} env={os.environ.get('HOT_MARKER', '')} cfg={getattr(config, 'qa_marker', 'none')}"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("hotapp " + APP_VERSION, id="title"),
            rx.text("count: ", State.count, id="count"),
            rx.text("label: ", State.label, id="label"),
            rx.text("pid: ", State.pid, id="pid"),
            rx.button("bump", on_click=State.bump, id="bump"),
            rx.link("about", href="/about", id="about-link"),
        )
    )


app = rx.App()
app.add_page(index, on_load=State.on_load)
# MARKER: new pages / states get added below this line by the driver
