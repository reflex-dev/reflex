"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(
                "Get started by editing ",
                rx.code(f"{config.app_name}/{config.app_name}.py"),
                size="5",
            ),
            rx.link(
                rx.button("Check out our docs!"),
                href="https://reflex.dev/docs/getting-started/introduction/",
                is_external=True,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)


# QA (a3_upgrade, #7428): with QA_CHATTY=1 the backend worker prints numbered lines from a thread as fast as the
# output pipe accepts them (throttled to ~QA_CHATTY_RATE lines/s) and records the last printed sequence number in
# QA_CHATTY_SEQ_FILE, so a slow `reflex run --json` consumer can tell which lines were lost at shutdown.
import os as _os
import threading as _threading
import time as _time


def _qa_chatty_lifespan():
    if _os.environ.get("QA_CHATTY") != "1":
        return
    seq_file = _os.environ.get("QA_CHATTY_SEQ_FILE", "chatty.seq")
    delay = 1.0 / float(_os.environ.get("QA_CHATTY_RATE", "400"))
    pad = "x" * 240

    def run():
        n = 0
        while True:
            print(f"QA-SEQ {n:07d} {pad}", flush=True)
            with open(seq_file, "w") as f:
                f.write(str(n))
            n += 1
            _time.sleep(delay)

    _threading.Thread(target=run, daemon=True, name="qa-chatty").start()


app.register_lifespan_task(_qa_chatty_lifespan)
