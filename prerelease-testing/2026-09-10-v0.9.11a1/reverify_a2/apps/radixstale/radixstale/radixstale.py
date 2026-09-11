"""Toggle between a Radix-using page and a Radix-free page via RADIX=0/1.

Exercises reflex-components-radix 0.9.9a2: "Avoid retaining stale Radix Themes
library registrations when recompiling an app that no longer uses Radix components."
"""

import os

import reflex as rx

USE_RADIX = os.environ.get("RADIX", "1") == "1"


def index() -> rx.Component:
    """Index page, with or without Radix components."""
    if USE_RADIX:
        return rx.vstack(
            rx.heading("radix on", id="mode"),
            rx.button("radix button", id="btn"),
            rx.badge("radix badge"),
        )
    return rx.el.div(
        rx.el.h1("radix off", id="mode"),
        rx.el.button("plain button", id="btn"),
    )


app = rx.App()
app.add_page(index)
