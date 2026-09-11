"""Minimal locale-bleed verification app (independent rewrite of the claimed repro)."""

import reflex as rx


def index() -> rx.Component:
    """The repro page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.text("plain (no locale prop) -> expected English:"),
        rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", id="plain"),
        rx.text("from_now (no locale prop) -> expected English:"),
        rx.moment("2020-01-01T00:00:00", from_now=True, id="fromnow"),
        rx.text("explicit locale='fr':"),
        rx.moment(
            "2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="fr", id="french"
        ),
        rx.text("ready", id="ready"),
        spacing="2",
        padding="1em",
        align="start",
    )


app = rx.App()
app.add_page(index, route="/")
