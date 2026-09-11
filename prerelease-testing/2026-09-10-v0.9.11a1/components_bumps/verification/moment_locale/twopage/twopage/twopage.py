"""Two-page probe: does a locale= on one page change dates on another page?"""

import reflex as rx


def index() -> rx.Component:
    """Home page: no locale prop anywhere.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.text("home: no locale prop on this page at all"),
        rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", id="plain"),
        rx.moment("2020-01-01T00:00:00", from_now=True, id="fromnow"),
        rx.link("go to /fr", href="/fr", id="tofr"),
        rx.text("ready", id="ready"),
        spacing="2",
        padding="1em",
        align="start",
    )


def fr_page() -> rx.Component:
    """A page that uses locale="fr" on one component.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.text("fr page"),
        rx.moment(
            "2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="fr", id="french"
        ),
        rx.link("back home", href="/", id="tohome"),
        rx.text("ready", id="ready"),
        spacing="2",
        padding="1em",
        align="start",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(fr_page, route="/fr")
