"""Minimal repro: does one rx.moment(locale=...) change the language of the others?"""

import reflex as rx


class S(rx.State):
    """State holding the locale of the single localized moment."""

    loc: str = "fr"

    @rx.event
    def next_locale(self):
        """Rotate the localized moment between fr, es and de."""
        order = ["fr", "es", "de"]
        self.loc = order[(order.index(self.loc) + 1) % len(order)]


@rx.memo
def memo_moment(date: rx.Var[str]) -> rx.Component:
    """A memoized moment, forcing a separate app_components module.

    Args:
        date: The date to render.

    Returns:
        The component.
    """
    return rx.moment(date, format="dddd D MMMM YYYY", id="memoed")


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
        rx.text("explicit locale='es':"),
        rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="es", id="spanish"),
        rx.text("explicit locale='fr':"),
        rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="fr", id="french"),
        rx.text("tz probe (pulls in moment-timezone):"),
        rx.moment("2024-03-14T15:09:26Z", tz="America/New_York", format="dddd D MMMM YYYY HH:mm z", id="tzprobe"),
        rx.text("state locale:"),
        rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale=S.loc, id="stateloc"),
        rx.text("memoed (no locale prop):"),
        memo_moment(date="2024-03-14T15:09:26"),
        rx.button("next locale", on_click=S.next_locale, id="next"),
        rx.text("ready", id="ready"),
        spacing="2",
        padding="1em",
        align="start",
    )


app = rx.App()
app.add_page(index, route="/")
