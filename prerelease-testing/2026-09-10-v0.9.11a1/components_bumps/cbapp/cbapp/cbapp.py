"""Multi-page app exercising the 0.9.11a1 component library bumps."""

import reflex as rx

from .code_page import code_page
from .moment_page import moment_page
from .plotly_page import plotly_page
from .radix_page import radix_page
from .recharts_page import recharts_page
from .toast_page import ToastState, toast_page


def index() -> rx.Component:
    """The index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("component bumps 0.9.11a1", size="5"),
        rx.link("moment", href="/moment", id="nav-moment"),
        rx.link("code", href="/code", id="nav-code"),
        rx.link("plotly", href="/plotly", id="nav-plotly"),
        rx.link("recharts", href="/recharts", id="nav-recharts"),
        rx.link("toast", href="/toast", id="nav-toast"),
        rx.link("radix", href="/radix", id="nav-radix"),
        rx.text("ready", id="ready"),
        spacing="2",
        padding="1em",
        align="start",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(moment_page, route="/moment")
app.add_page(code_page, route="/code")
app.add_page(plotly_page, route="/plotly")
app.add_page(recharts_page, route="/recharts")
app.add_page(toast_page, route="/toast", on_load=ToastState.page_load)
app.add_page(radix_page, route="/radix")
