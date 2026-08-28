"""Verifier app: custom component wrapping react-router-dom Link (repro for prod_export claim)."""

import reflex as rx


class BadDomLink(rx.Component):
    """Custom component declaring the removed react-router-dom library."""

    library = "react-router-dom"
    tag = "Link"
    to: rx.Var[str]


bad_dom_link = BadDomLink.create


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("verify index", id="idx-heading"),
        bad_dom_link("go to other", to="/other", id="bad-link"),
    )


def other() -> rx.Component:
    return rx.heading("other page", id="other-heading")


app = rx.App()
app.add_page(index)
app.add_page(other, route="/other")
