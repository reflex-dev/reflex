"""Locale-isolation matrix for FINDING-033 / moment #7110.

Routes:
  /          French first, then un-localed siblings, relative date, title attr, duration
  /reverse   the same set with the un-localed moments BEFORE the French one
  /english   only un-localed moments (a route that never imports a locale)
  /en        explicit locale="en"
  /reactive  a Var-driven locale the user switches between fr / en / "" / None
"""

import reflex as rx

D1 = "2024-03-14T15:09:26"
D2 = "2020-01-01T00:00:00"


class LocaleState(rx.State):
    """Reactive locale for the /reactive route."""

    loc: str = "fr"

    @rx.event
    def set_fr(self):
        """Switch to French."""
        self.loc = "fr"

    @rx.event
    def set_en(self):
        """Switch to English."""
        self.loc = "en"

    @rx.event
    def set_empty(self):
        """Switch to the empty string."""
        self.loc = ""


def nav() -> rx.Component:
    """Links between every route."""
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("reverse", href="/reverse", id="nav-reverse"),
        rx.link("english", href="/english", id="nav-english"),
        rx.link("en", href="/en", id="nav-en"),
        rx.link("reactive", href="/reactive", id="nav-reactive"),
    )


def plain_set(prefix: str) -> list[rx.Component]:
    """The un-localed moments, plus a relative date, a title attribute and a duration."""
    return [
        rx.moment(D1, format="dddd D MMMM YYYY", id=f"{prefix}-plain"),
        rx.moment(D2, from_now=True, id=f"{prefix}-fromnow"),
        rx.moment(D2, to_now=True, id=f"{prefix}-tonow"),
        rx.moment(D1, format="dddd", with_title=True, title_format="dddd D MMMM YYYY",
                  id=f"{prefix}-title"),
        rx.moment(duration=D2, date=D1, id=f"{prefix}-duration"),
    ]


@rx.page(route="/")
def index() -> rx.Component:
    """French moment first, then the un-localed set."""
    return rx.vstack(
        nav(),
        rx.moment(D1, format="dddd D MMMM YYYY", locale="fr", id="home-french"),
        *plain_set("home"),
        rx.text("ready", id="ready"),
    )


@rx.page(route="/reverse")
def reverse() -> rx.Component:
    """Un-localed set first, French moment last."""
    return rx.vstack(
        nav(),
        *plain_set("rev"),
        rx.moment(D1, format="dddd D MMMM YYYY", locale="fr", id="rev-french"),
        rx.text("ready", id="ready"),
    )


@rx.page(route="/english")
def english() -> rx.Component:
    """A route with no locale anywhere."""
    return rx.vstack(nav(), *plain_set("eng"), rx.text("ready", id="ready"))


@rx.page(route="/en")
def explicit_en() -> rx.Component:
    """Explicit locale="en" must not request a nonexistent locale module."""
    return rx.vstack(
        nav(),
        rx.moment(D1, format="dddd D MMMM YYYY", locale="en", id="en-explicit"),
        *plain_set("en"),
        rx.text("ready", id="ready"),
    )


@rx.page(route="/reactive")
def reactive() -> rx.Component:
    """A Var-driven locale beside un-localed siblings."""
    return rx.vstack(
        nav(),
        rx.moment(D1, format="dddd D MMMM YYYY", locale=LocaleState.loc, id="react-var"),
        *plain_set("react"),
        rx.hstack(
            rx.button("fr", on_click=LocaleState.set_fr, id="btn-fr"),
            rx.button("en", on_click=LocaleState.set_en, id="btn-en"),
            rx.button("empty", on_click=LocaleState.set_empty, id="btn-empty"),
        ),
        rx.text(LocaleState.loc, id="loc"),
        rx.text("ready", id="ready"),
    )


app = rx.App()
