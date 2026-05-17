"""Box with a `style` prop passed as a dict."""

import reflex as rx


ROUTE = "/style_dict"
IDENT = "StyleDict"


def build():
    return rx.box(
        "styled",
        style={"color": "red", "padding": "4px"},
    )
